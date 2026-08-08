import os
import subprocess
from datetime import datetime

PJSIP_CONFIG_PATH = "/etc/asterisk/pjsip_users.conf"
EXTENSIONS_CONFIG_PATH = "/etc/asterisk/extensions_users.conf"
BACKUP_DIR = "/app/backups"

def save_pjsip_config(extensions_data):
    """
    Генерирует индивидуальные настройки pjsip для каждого номера с принудительным Caller ID
    """
    config_content = "; ==========================================\n"
    config_content += "; Auto-generated PJSIP configuration\n"
    config_content += "; ==========================================\n\n"

    for ext in extensions_data:
        ext_num = ext['extension']
        secret = ext['secret']
        transport = ext['transport']
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


def save_extensions_config(extensions_data):
    """
    Генерирует диалплан с отображением Имени и Номера в связке (например, Fedor <100>)
    """
    config_content = "; ==========================================\n"
    config_content += "; Auto-generated extensions configuration\n"
    config_content += "; ==========================================\n\n"
    config_content += "[default]\n"

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

        config_content += f"""same => n,Dial(PJSIP/{ext_num},30)
same => n,Hangup()
"""

    config_content += """
[add-connected-line]
exten => _.,1,NoOp()
same => n,Return()
"""

    try:
        os.makedirs(os.path.dirname(EXTENSIONS_CONFIG_PATH), exist_ok=True)
        with open(EXTENSIONS_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(config_content)
        return True, EXTENSIONS_CONFIG_PATH
    except Exception as e:
        return False, str(e)


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