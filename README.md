# Asterisk Web PBX

A Docker-based office phone system (PBX) built with **Asterisk**, **FastAPI**, and **PostgreSQL**. It provides a web interface and API for managing SIP extensions, call groups, trunks, IVR menus, and call recordings. The interface is available in **English, Russian, and Hebrew**.

## Contents

- [Philosophy](#philosophy)
- [Intended use](#intended-use)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Choosing the interface language](#choosing-the-interface-language)
- [After installation: verify that everything works](#after-installation-verify-that-everything-works)
- [Open the web interface](#open-the-web-interface)
- [Login and password reset](#login-and-password-reset)
- [Call recording](#call-recording)
- [Administration tab and backups](#administration-tab-and-backups)
- [Installer options](#installer-options)
- [Updating and removing](#updating-and-removing)
- [Manual installation from source](#manual-installation-from-source-advanced)
- [External lines and trunks](#external-lines-and-trunks)
- [Configuration and network ports](#configuration)
- [Security notes](#security-notes)
- [Roadmap](#roadmap)

## Philosophy

The goal of this project is **simplicity of use and deployment**. A person with minimal knowledge of Asterisk and telephony should be able to bring up a small office PBX in minutes: one command installs and starts everything, secrets are generated automatically, and all day-to-day configuration is done in the web interface.

## Intended use

This project is designed for **mini-office PBXs inside an office network (LAN)**:

- Run it on a server or computer **inside your office network, behind a firewall**.
- Phones and softphones register to the PBX over **SIP/UDP** on the local network.
- Connections to the outside world go through **external SIP lines from a SIP provider** or through **SIP gateways**. You can also link the PBX to **other Asterisk servers** using the **IAX2** protocol (Inter-Asterisk eXchange).
- It is **not recommended** to deploy this version in the cloud or on a host with a public IP address reachable from the Internet.

A separate edition for cloud use and deployment on the open Internet is planned as a future project.

## Features

- Asterisk PBX with SIP over UDP
- RTP audio for internal calls
- SIP trunks for provider lines and SIP gateways
- IAX2 trunks (Inter-Asterisk eXchange) for connecting to other Asterisk servers
- FastAPI backend for PBX configuration and status
- PostgreSQL persistence for extensions, groups, trunks, IVR menus, and the call-recording archive (the database is not used while calls are being handled)
- Password-protected web interface (one administrator, password created on first start)
- Call recording for selected extensions, with an archive: filters, audio player, download
- Administration tab: system status, container status, backup and restore of all settings, password change
- Web administration interface in English, Russian, and Hebrew (right-to-left layout)
- Docker Compose deployment
- One-command installation with automatically generated secrets

## Architecture

```text
SIP Phones / Softphones
          |
       SIP / UDP
       RTP / UDP
          |
      Asterisk PBX  ---- SIP provider / SIP gateway (SIP/UDP)
          |         ---- Other Asterisk servers (IAX2/UDP)
          |
   FastAPI Backend ---- PostgreSQL
          |
      Web Interface
```

## Repository layout

- `backend/` — FastAPI application and database models
- `frontend/` — browser-based administration interface, one folder per language (`en/`, `ru/`, `he/`)
- `asterisk/config/` — Asterisk configuration templates
- `asterisk/sounds/` — runtime location for custom IVR recordings
- `installer/` — one-command installer (bash script and installer container image)
- `docker-compose.yml` — local/source deployment
- `docker-compose.prod.yml` — container-image deployment

## Quick start

### Option 1 (recommended): one `docker run` command

This option assumes that **Docker and Docker Compose are already installed**. Check with:

```bash
docker --version
docker compose version
```

If Docker is not installed, follow the official instructions: [Install Docker Engine](https://docs.docker.com/engine/install/) (Docker Compose is included as a plugin; see also [Install Docker Compose](https://docs.docker.com/compose/install/linux/)).

Then run:

```bash
docker run --pull=always --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/asterisk-pbx:$HOME/asterisk-pbx -e APP_DIR=$HOME/asterisk-pbx \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  ghcr.io/fedor-afrin/asterisk-veb-installer:latest
```

The installer first asks which interface language you want (see [Choosing the interface language](#choosing-the-interface-language)); just press **Enter** for English. Everything else is automatic. No `git clone` is needed.

What the options in the command mean:

| Part | Purpose |
|---|---|
| `--pull=always` | always use the latest version of the installer image |
| `-it` | interactive mode, needed to answer the language question |
| `-v /var/run/docker.sock:...` | lets the installer start the PBX containers on your Docker |
| `-v ~/asterisk-pbx:$HOME/asterisk-pbx -e APP_DIR=...` | where to install; change the path if you prefer another location (both parts must use the same path) |
| `-e HOST_UID` / `-e HOST_GID` | the installed files belong to you, not to root |

When it finishes, the installer prints the address of the web interface:

```text
http://<server-ip>:8000
```

### Option 2: clone the repository and run the install script

Use this option if you prefer to work from a cloned repository. **If Docker is not installed, the script offers to install it for you** (using the official Docker installation script; `sudo` is required).

```bash
git clone https://github.com/Fedor-Afrin/asterisk-veb.git
cd asterisk-veb
bash installer/install.sh
```

The script also asks for the interface language. The PBX is installed into `~/asterisk-pbx` in the same way as in Option 1, using the files from your clone. After a fresh Docker installation, log out and back in so that your user can run Docker without `sudo`.

### What the installer does

Both options perform the same steps:

1. ask for the interface language (English by default);
2. create the installation directory (if it does not exist);
3. copy the project files and the web interface in the chosen language;
4. generate random `POSTGRES_PASSWORD` and `AMI_SECRET` values and write them to `.env`;
5. put the same AMI secret into `asterisk/config/manager.conf`;
6. pull the images and run `docker compose up -d`;
7. wait until the web interface answers and print its address.

> **Note:** the installer's own progress messages are currently shown in Russian; this does not affect the language of the web interface.

## Choosing the interface language

The web interface comes in three languages:

| Language | Code | Notes |
|---|---|---|
| English | `en` | default |
| Russian (Русский) | `ru` | |
| Hebrew (עברית) | `he` | right-to-left layout |

When you start the installer interactively, it shows a menu:

```text
Choose interface language / Выберите язык интерфейса / בחר שפת ממשק:
  1) English (en) [default]
  2) Русский (ru)
  3) עברית (he)
Enter choice [en/ru/he] (default: en):
```

| You type | Result |
|---|---|
| just **Enter** | English |
| `ru`, `RU` or `2` | Russian |
| `he`, `HE` or `3` | Hebrew |
| anything else | English |

To skip the question (for scripts and unattended installs), set the language in advance with `LANG_CHOICE`:

```bash
# container installer: add this option to the docker run command
-e LANG_CHOICE=ru

# script installer
LANG_CHOICE=he bash installer/install.sh
```

If no question is asked (`YES=1`, or the installer runs without a terminal, for example from a scheduled job), English is used unless `LANG_CHOICE` is set.

**Changing the language later:** run the installer again and pick another language. Your extensions, trunks, passwords, and database are not touched; only the web interface files are replaced. Then refresh the page in the browser with `Ctrl+F5`.

## After installation: verify that everything works

**1. Check the containers.** Go to the installation directory and list the stack:

```bash
cd ~/asterisk-pbx
docker compose ps
```

You should see three containers, all with the status `Up`:

| Container | Role |
|---|---|
| `asterisk-pbx-prod` | Asterisk PBX |
| `pbx_backend_prod` | FastAPI backend and web interface |
| `pbx_db_prod` | PostgreSQL database |

(`docker compose ls` shows the whole project and its status as `running(3)`.)

**2. Check the listening ports.** Show only the ports used by the PBX:

```bash
ss -tulnp | grep -E ':(5060|4569|5038|8000)\s'
```

You should see these four ports in the `LISTEN`/`UNCONN` state:

| Port | Protocol | Purpose |
|---:|---|---|
| 5060 | UDP | SIP |
| 4569 | UDP | IAX2 |
| 5038 | TCP | Asterisk AMI (used by the backend) |
| 8000 | TCP | Web interface and API |

The PostgreSQL port `5432/tcp` is internal to the Docker network and is intentionally not published on the host, so it does not appear in `ss`. RTP audio ports (UDP 10000-20000) are opened by Asterisk only while calls are in progress.

**3. Check Asterisk itself** (optional):

```bash
docker compose exec asterisk asterisk -rx "core show version"
```

**4. Check the logs** if something does not look right:

```bash
docker compose logs -f backend asterisk db
```

## Open the web interface

All PBX settings (extensions, groups, trunks, IVR) are configured in the web interface. Open it in a browser:

```text
http://<server-ip>:8000
```

where `<server-ip>` is the IP address of the computer or server where the PBX is installed (`hostname -I` shows it; on the same machine you can use `http://localhost:8000`). The installer also prints this address when it finishes.

On first start the interface asks you to **create the administrator password** (minimum 8 characters). After that you sign in with this password. Still restrict access to port `8000` to your office network (see [Security notes](#security-notes)): there is no HTTPS.

## Login and password reset

There is a single administrator account. The password is stored as a salted scrypt hash; the session is an HttpOnly cookie valid for 24 hours. Changing the password signs out all other sessions.

If you forgot the password, reset it on the server:

```bash
cd ~/asterisk-pbx
docker compose exec backend python reset_password.py          # asks for a new password
docker compose exec backend python reset_password.py --web    # back to the first-run screen
```

## Call recording

On the **Call Recordings** tab:

1. Open the dropdown, tick the extensions to record, press **Save Settings**, then press **Apply Configuration**.
2. Calls where a selected extension is the caller or the callee (incoming and outgoing, including calls through trunks, groups, and IVR) are recorded as WAV files.
3. The archive on the same tab lists recordings with filters (extension, date range, minimum duration), a built-in player, download, and delete.

Notes:

- Files are stored in `asterisk/sounds/recordings/` in the installation folder (owned by root). There is no automatic cleanup yet, so watch the disk space.
- The database is not touched during a call. Asterisk writes the file; the archive list is refreshed from the folder when you open the tab (recordings appear about 15 seconds after the call ends).
- File names contain the time in UTC; the interface shows times in your browser's time zone.
- Recordings are not included in backups. Check the laws on recording calls that apply to you.

## Administration tab and backups

The **Administration** tab shows CPU load, memory, disk, uptime, and the state of the containers (refreshed every 5 seconds), and lets you:

- **Download a backup**: one zip with all settings (extensions, groups, trunks, IVR menus, recording selection) and IVR greeting files. It contains SIP and trunk passwords, so keep it secret. Call recordings and the administrator password are not included.
- **Restore from a backup**: replaces all current settings in one transaction and applies them to Asterisk. If the file is invalid, the current settings stay unchanged.
- **Change the administrator password.**

## Installer options

Pass these as environment variables: `-e NAME=value` for the container, or `NAME=value` before the command for the script.

| Variable | Default | Purpose |
|---|---|---|
| `LANG_CHOICE` | ask (English if not asked) | Interface language: `en`, `ru` or `he`; skips the language question |
| `APP_DIR` | `~/asterisk-pbx` | Installation directory (required for the container; it must be the same path that is mounted with `-v`) |
| `BRANCH` | `main` | Repository branch the installer downloads |
| `RESET` | `0` | `1` deletes the existing database volume and starts from scratch |
| `YES` | `0` | `1` skips questions: no Docker installation prompt (script only) and no language prompt |

### Safe to re-run

The installer is idempotent. Running it again:

- does not recreate an existing directory;
- does **not** regenerate secrets if `.env` exists (PostgreSQL keeps the password it was first created with, so changing it would break the connection);
- does not overwrite `asterisk/config/`, where your extensions and trunks are stored;
- refreshes the application code and the web interface, and pulls the latest images.

If `.env` is missing but a database volume from a previous installation still exists, the installer stops and explains how to continue instead of failing later with an authentication error. To discard the old database, run it with `RESET=1`.

## Updating and removing

Update to the latest version by running the installer again (choose the same language as before, or a different one).

Stop the stack and keep the data:

```bash
cd ~/asterisk-pbx && docker compose down
```

Remove the stack **and the database**:

```bash
cd ~/asterisk-pbx && docker compose down -v
```

## Manual installation from source (advanced)

Use this if you want to build the images yourself and do not want to use the installer. A manual installation from source serves the **English** interface; to get Russian or Hebrew, use the installer (Option 1 or 2).

### 1. Prepare configuration

```bash
git clone https://github.com/Fedor-Afrin/asterisk-veb.git
cd asterisk-veb
cp .env.example .env
```

Edit `.env` and set unique secrets. Generate random values with:

```bash
openssl rand -hex 32
```

Use separate values for `POSTGRES_PASSWORD` and `AMI_SECRET`. Do not commit `.env`.

### 2. Configure Asterisk AMI

Edit `asterisk/config/manager.conf`:

- Replace `CHANGE_ME_USE_A_LONG_RANDOM_SECRET` with the same value as `AMI_SECRET` in `.env`.
- Set `permit` to cover the Docker networks of your host. `172.16.0.0/255.240.0.0` covers all default Docker bridge networks (172.16.0.0 – 172.31.255.255).
- Keep AMI access restricted to trusted networks.

### 3. Start the services

For a source deployment (builds the images locally):

```bash
docker compose up -d --build
```

For a deployment using the published images:

```bash
docker compose -f docker-compose.prod.yml up -d
```

The web administration interface and API are served by the backend on port `8000`.

## External lines and trunks

Trunks are added in the web interface (the trunk form lets you choose the protocol):

- **PJSIP (SIP)** — external lines from a SIP provider, or a connection to a SIP gateway.
- **IAX2** — a connection to another Asterisk server using the Inter-Asterisk eXchange protocol (UDP port 4569).

## Configuration

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` | PostgreSQL application user |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |
| `AMI_HOST` | Hostname or address used by the backend to reach Asterisk AMI |
| `AMI_PORT` | AMI TCP port (default: `5038`) |
| `AMI_USER` | AMI username (default: `pbx_api`) |
| `AMI_SECRET` | AMI password; must match `manager.conf` |

The `.env.example` file contains placeholders only. The installer replaces them automatically; with a manual installation, replace them yourself before deployment.

## Network ports

| Component | Protocol | Port |
|---|---|---:|
| Web UI / FastAPI | TCP | 8000 |
| SIP signaling | UDP | 5060 |
| Asterisk AMI | TCP | 5038 (internal/trusted network only) |
| RTP audio | UDP | 10000-20000 |
| IAX2 (links to other Asterisk servers) | UDP | 4569 |
| PostgreSQL | TCP | 5432 (internal Docker network) |

The Asterisk container uses host networking. Keep the PBX **inside the office network behind a firewall**: allow SIP and RTP only from office devices and from the addresses of your SIP provider or SIP gateway, allow IAX2 only from the Asterisk servers you link to, and do not forward these ports from the Internet.

## Runtime data

Database contents and user-created PBX objects are stored in the PostgreSQL Docker volume. Custom IVR audio is written to `asterisk/sounds/` and call recordings to `asterisk/sounds/recordings/` at runtime. The directory is kept in Git with a placeholder file; personal recordings are intentionally excluded.

A fresh deployment starts with an empty database. Existing deployments keep their current data in their Docker volume unless that volume is deliberately removed (`docker compose down -v` or `RESET=1`).

## Security notes

- Use this version only inside a trusted office network behind a firewall; do not expose the web interface, SIP, IAX2, RTP, AMI, or PostgreSQL to the Internet.
- The web interface is protected by the administrator password, but it is served over plain HTTP: restrict access to port `8000` with a firewall, or put it behind a reverse proxy with HTTPS.
- Backups contain SIP and trunk passwords; call recordings contain private conversations. Store both securely.
- The installer container needs access to the Docker socket (`/var/run/docker.sock`), which is equivalent to root access on the host. Run it only from the official image, or build it from this repository yourself.
- Never commit `.env`, private keys, recordings, database dumps, or backups.
- Installer-generated secrets are random; if you edit `.env` manually, use strong unique values.
- Restrict AMI to the backend's trusted network and use a dedicated account.
- Use strong, unique SIP extension passwords.

## Roadmap

- A separate edition for cloud deployment and use on the open Internet.
- Automatic cleanup of old call recordings.
- HTTPS for the web interface.

## License

Copyright (C) 2026 Fedor Afrin

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**; see the [LICENSE](LICENSE) file.

In short: you may use, study, modify, and share this software, including commercially. If you distribute a modified version, or let other people use it over a network (for example as a hosted service), you must make the complete source code of your version available under the same license and keep the copyright notices.

Releases made before this change were published under the Apache License 2.0 and remain available under those terms.
