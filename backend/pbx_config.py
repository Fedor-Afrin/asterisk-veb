import os

ASTERISK_CONFIG_DIR = os.getenv("ASTERISK_CONFIG_DIR", "/etc/asterisk")

def generate_pjsip_config(pools_data):
    config_content = "; ==========================================\n"
    config_content += "; Auto-generated PJSIP configuration from Web UI\n"
    config_content += "; ==========================================\n\n"

    for pool in pools_data:
        start = int(pool['start_extension'])
        end = int(pool['end_extension'])
        username = pool['username']
        pool_transport = pool.get('transport', 'transport-tls')

        config_content += f"; --- Pool for user: {username} (Ext: {start}-{end}, Transport: {pool_transport}) ---\n"
        
        for ext in range(start, end + 1):
            config_content += f"""
[{ext}]
type=endpoint
transport={pool_transport}
context=default
disallow=all
allow=ulaw
allow=alaw
auth=auth{ext}
aors={ext}
; --- Настройки для обхода NAT и решения проблемы одностороннего звука ---
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no

[auth{ext}]
type=auth
auth_type=userpass
username={ext}
password=password_{ext}

[{ext}]
type=aor
max_contacts=1
"""
    return config_content

def generate_extensions_config(pools_data):
    config_content = "; ==========================================\n"
    config_content += "; Auto-generated extensions from Web UI\n"
    config_content += "; ==========================================\n\n"
    
    # Обязательный блок [default], без которого диалплан не сработает
    config_content += "[default]\n"
    config_content += "exten => _X.,1,NoOp(Call from ${CALLERID(num)} to ${EXTEN})\n"
    config_content += "same => n,Dial(PJSIP/${EXTEN},30)\n"
    config_content += "same => n,Hangup()\n\n"
    
    return config_content

def save_pjsip_config(pools_data):
    config_text = generate_pjsip_config(pools_data)
    file_path = os.path.join(ASTERISK_CONFIG_DIR, "pjsip_users.conf")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(config_text)
        return True, file_path
    except Exception as e:
        print(f"Error saving PJSIP config: {e}")
        return False, str(e)

def save_extensions_config(pools_data):
    config_text = generate_extensions_config(pools_data)
    file_path = os.path.join(ASTERISK_CONFIG_DIR, "extensions_users.conf")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(config_text)
        return True, file_path
    except Exception as e:
        print(f"Error saving Extensions config: {e}")
        return False, str(e)