# Asterisk Web PBX

A Docker-based VoIP platform built with **Asterisk**, **FastAPI**, **PostgreSQL**, and **CoTURN**. It provides a web interface and API for managing SIP extensions, call groups, trunks, IVR menus, and call records.

## Features

- Asterisk PBX with SIP over UDP and SIP over TLS
- FastAPI backend for PBX configuration and status
- PostgreSQL persistence for extensions, groups, trunks, IVR menus, and call records
- CoTURN for STUN/TURN NAT traversal
- Docker Compose deployment
- Web administration interface

## Architecture

```text
SIP Phones / Softphones
          |
       SIP / RTP
          |
      Asterisk PBX
          |
   FastAPI Backend ---- PostgreSQL
          |
      Web Interface

      CoTURN (STUN/TURN)
```

## Repository layout

- `backend/` — FastAPI application and database models
- `frontend/` — browser-based administration interface
- `asterisk/config/` — Asterisk configuration templates
- `asterisk/coturn/` — Coturn configuration template
- `asterisk/sounds/` — runtime location for custom IVR recordings
- `installer/` — optional installation helper
- `docker-compose.yml` — local/source deployment
- `docker-compose.prod.yml` — container-image deployment

## Quick start

### 1. Prepare configuration

Clone the repository and create your local environment file:

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
- Adjust the `permit` network to match the Docker bridge network used by your host.
- Keep AMI access restricted to trusted networks.

### 3. Configure TLS

The repository intentionally does not include certificates or private keys. Install your own certificate and private key as:

- `asterisk/config/certs/fullchain.pem`
- `asterisk/config/certs/privkey.pem`

Do not commit these files. The TLS transport will not be usable until valid certificate files are installed.

### 4. Configure CoTURN (if required)

Edit `asterisk/coturn/turnserver.conf` and configure your own DNS realm, public IP/NAT settings, and authentication secret. Keep real deployment values out of Git.

### 5. Start the services

```bash
docker compose up -d --build
```

Check service status and logs:

```bash
docker compose ps
docker compose logs -f backend asterisk coturn db
```

The web administration interface and API are served by the backend on port `8000`. Restrict access to this port with a firewall or place it behind an authenticated reverse proxy before exposing it beyond a trusted network.

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

The `.env.example` file contains placeholders only. Replace them locally before deployment.

## Main ports

| Component | Protocol | Port |
|---|---|---:|
| Web UI / FastAPI | TCP | 8000 |
| SIP | UDP | 5060 |
| SIP-TLS | TCP | 5061 |
| Asterisk AMI | TCP | 5038 |
| RTP media | UDP | 10000-10099 |
| CoTURN | UDP/TCP | 3478 |
| CoTURN TLS (if configured) | TCP | 5349 |
| PostgreSQL | TCP | 5432 (internal) |

Actual Asterisk RTP range and network requirements depend on your local configuration.

## Runtime data

Database contents and user-created PBX objects are stored in the PostgreSQL Docker volume. Custom IVR audio is written to `asterisk/sounds/` at runtime. The directory is kept in Git with a placeholder file; personal recordings are intentionally excluded.

A fresh deployment starts with an empty database. Existing deployments keep their current data in their Docker volume unless that volume is deliberately removed.

## Security notes

- Never commit `.env`, private keys, certificates, recordings, database dumps, or backups.
- Replace all example credentials before starting the stack.
- Restrict AMI to the backend's trusted network and use a dedicated account.
- Do not expose AMI or PostgreSQL directly to the public Internet.
- Configure firewall rules for SIP, RTP, and TURN according to your deployment.
- Use valid TLS certificates and strong, unique SIP credentials.
- Rotate any credentials or private keys that may have been exposed previously.

## License

This project is licensed under the Apache License 2.0.
