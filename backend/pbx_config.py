import os
import subprocess
import dockerapi
from datetime import datetime

PJSIP_CONFIG_PATH = "/etc/asterisk/pjsip_users.conf"
EXTENSIONS_CONFIG_PATH = "/etc/asterisk/extensions_users.conf"
BACKUP_DIR = "/app/backups"

def save_pjsip_config(extensions_data):
    """
    Генерирует индивидуальные настройки pjsip для каждого номера с принудительным Caller ID
    и защитой от зависших (фантомных) каналов.
    """
    config_content = "; ==========================================\n"
    config_content += "; Auto-generated PJSIP configuration\n"
    config_content += "; ==========================================\n\n"

    for ext in extensions_data:
        ext_num = ext['extension']
        secret = ext['secret']
        transport = 'transport-udp'
        callerid = ext.get('callerid', f"User <{ext_num}>")

        config_content += f"""
[{ext_num}]
type=endpoint
transport={transport}
context=default
disallow=all
allow=ulaw
allow=alaw
auth=auth{ext_num}
aors={ext_num}
callerid={callerid}
send_pai=yes
send_rpid=yes
trust_id_inbound=yes
trust_id_outbound=yes
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no
rtp_timeout=30
rtp_timeout_hold=300

[auth{ext_num}]
type=auth
auth_type=userpass
username={ext_num}
password={secret}

[{ext_num}]
type=aor
max_contacts=1
"""

    try:
        os.makedirs(os.path.dirname(PJSIP_CONFIG_PATH), exist_ok=True)
        with open(PJSIP_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(config_content)
        return True, PJSIP_CONFIG_PATH
    except Exception as e:
        return False, str(e)

# Dial-опция U(): после ответа абонента вызывает подпрограмму rec-answer на ЕГО канале.
# Аргументы: номер звонящего и набранный номер (нужны для имени файла записи).
def rec_option(dialed="${EXTEN}"):
    return f"U(rec-answer^${{CALLERID(num)}}^{dialed})"


RECORDINGS_ASTERISK_DIR = "/usr/share/asterisk/sounds/custom/recordings"


def generate_recording_dialplan(recording_exts):
    """Контекст [rec-answer]: включает MixMonitor, если звонящий или ответивший выбран для записи."""
    lines = [
        "; ==========================================",
        "; Auto-generated call recording rules",
        "; ==========================================",
        "[rec-answer]",
        "exten => s,1,NoOp(Recording check: caller ${ARG1}, callee ${CHANNEL(endpoint)})",
    ]
    for number in sorted({int(n) for n in recording_exts}):
        lines.append(f'same => n,ExecIf($["${{ARG1}}"="{number}"]?Set(REC_ON=1))')
        lines.append(f'same => n,ExecIf($["${{CHANNEL(endpoint)}}"="{number}"]?Set(REC_ON=1))')
    lines += [
        'same => n,GotoIf($["${REC_ON}"!="1"]?done)',
        # Имя: дата-время(UTC)_звонящий_ответивший_uniqueid. Только безопасные символы, без "_".
        # Ответивший: имя PJSIP-эндпоинта (= номер); для транка - набранный номер (ARG2).
        'same => n,Set(REC_CALLER=${ARG1})',
        'same => n,Set(REC_CALLEE=${CHANNEL(endpoint)})',
        'same => n,ExecIf($["${REC_CALLEE}"=""]?Set(REC_CALLEE=${ARG2}))',
        'same => n,Set(REC_CALLER=${FILTER(0-9A-Za-z*#+,${REC_CALLER})})',
        'same => n,Set(REC_CALLEE=${FILTER(0-9A-Za-z*#+,${REC_CALLEE})})',
        'same => n,Set(REC_FILE=' + RECORDINGS_ASTERISK_DIR
            + '/${STRFTIME(${EPOCH},,%Y%m%d-%H%M%S)}_${REC_CALLER}_${REC_CALLEE}_${UNIQUEID})',
        'same => n,MixMonitor(${REC_FILE}.wav,b)',
        'same => n(done),Return()',
        "",
        "",
    ]
    return "\n".join(lines)


def generate_groups_dialplan(groups_db, extensions_db):
    """
    Генерирует контекст [groups] для файла extensions_users.conf
    """
    lines = [
        "\n; ==========================================",
        "; Auto-generated Groups configuration",
        "; ==========================================",
        "[groups]"
    ]

    for grp in groups_db:
        exten = grp['exten']
        strategy = grp['strategy']
        name = grp['name']
        member_ids = grp['members']
        
        # Находим реальные номера (extension) по их ID
        members = [ext['extension'] for ext in extensions_db if ext['id'] in member_ids]
        
        if not members:
            continue
            
        lines.append(f"\n; --- Group: {name} (Strategy: {strategy}) ---")
        lines.append(f"exten => {exten},1,NoOp(Call to Group {name})")
        
        # 1. Ring All (Звонят все)
        if strategy == 'ring_all':
            dial_str = "&".join([f"PJSIP/{m}" for m in members])
            lines.append(f"same => n,Dial({dial_str},45,{rec_option()})")
            
        # 2. Hunt / Round Robin (Поочередный вызов)
        elif strategy in ['hunt', 'round_robin']:
            for m in members:
                lines.append(f"same => n,Dial(PJSIP/{m},15,{rec_option()})")
                
        # 3. Page Group (Оповещение / Интерком громкой связи)
        elif strategy == 'page':
            page_str = "&".join([f"PJSIP/{m}" for m in members])
            lines.append(f"same => n,Page({page_str},i)")
            
        # 4. Pickup Group (Группа перехвата вызовов)
        elif strategy == 'pickup':
            pickup_str = "&".join([f"{m}@default" for m in members])
            lines.append(f"same => n,Pickup({pickup_str})")
            
        lines.append("same => n,Hangup()")

    return "\n".join(lines) + "\n\n"


def save_extensions_config(extensions_data, groups_data=None, recording_exts=()):
    """
    Генерирует диалплан с отображением Имени и Номера в связке (например, Fedor <100>)
    Также включает в себя генерацию групп вызова.
    """
    if groups_data is None:
        groups_data = []

    config_content = "; ==========================================\n"
    config_content += "; Auto-generated extensions configuration\n"
    config_content += "; ==========================================\n\n"
    config_content += generate_recording_dialplan(recording_exts)
    config_content += "[default]\n"
    config_content += "include => groups\n"
    config_content += "include => ivr_menus\n\n"

    names_map = {}
    for ext in extensions_data:
        ext_num = str(ext['extension'])
        clean_name = str(ext.get('callerid', ext_num)).replace('"', '').replace("'", "").replace('\\', '').strip()
        names_map[ext_num] = clean_name if clean_name else ext_num

    for ext in extensions_data:
        ext_num = str(ext['extension'])
        
        config_content += f"""
; --- Extension {ext_num} ---
exten => {ext_num},1,NoCDR()
"""
        # Динамически устанавливаем Caller ID: имя звонящего + его номер в угловых скобках
        for src_num, src_name in names_map.items():
            if src_num != ext_num:
                config_content += f'same => n,ExecIf($["${{CALLERID(num)}}" = "{src_num}"]?Set(CALLERID(all)="{src_name} <{src_num}>"))\n'

        config_content += f"""same => n,Dial(PJSIP/{ext_num},30,{rec_option(ext_num)})
same => n,Hangup()
"""

    config_content += """
[add-connected-line]
exten => _.,1,NoOp()
same => n,Return()
"""

    # --- ИНТЕГРАЦИЯ ГРУПП ---
    # Генерируем текст диалплана для групп и приклеиваем его в конец конфига
    # Контекст [groups] нужен всегда: в его конец дописываются маршруты исходящих вызовов
    config_content += generate_groups_dialplan(groups_data, extensions_data)

    try:
        os.makedirs(os.path.dirname(EXTENSIONS_CONFIG_PATH), exist_ok=True)
        with open(EXTENSIONS_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(config_content)
        return True, EXTENSIONS_CONFIG_PATH
    except Exception as e:
        return False, str(e)


def get_asterisk_endpoints_status():
    """
    Опрашивает Asterisk внутри Docker и возвращает словарь со статусами эндпоинтов
    """
    try:
        output = dockerapi.exec_output("asterisk-pbx", ["asterisk", "-rx", "pjsip show endpoints"])

        statuses = {}
        for line in output.splitlines():
            if line.strip().startswith("Endpoint:"):
                parts = line.split()
                if len(parts) >= 2:
                    ext = parts[1]
                    state = " ".join(parts[2:]) if len(parts) > 2 else "Unknown"
                    statuses[ext] = state
                    
        return statuses
    except Exception as e:
        return {"error": str(e)}


def create_postgres_backup(db_url: str):
    """
    Создает бэкап базы данных PostgreSQL с помощью pg_dump внутри бэкенда
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"pbx_backup_{timestamp}.sql")

        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        cmd = ["pg_dump", sync_url, "-f", backup_file]
        
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, backup_file
    except subprocess.CalledProcessError as e:
        return False, f"pg_dump error: {e.stderr}"
    except Exception as e:
        return False, str(e)