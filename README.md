# Asterisk Web PBX

A Docker-based office VoIP platform built with **Asterisk**, **FastAPI**, and **PostgreSQL**. It provides a web interface and API for managing SIP extensions, call groups, trunks, IVR menus, and call records.

This initial public deployment is designed for an office LAN and uses **SIP over UDP**. SIP-TLS, certificates, STUN, and TURN are not part of this version.

## Features

- Asterisk PBX with SIP over UDP
- RTP audio for internal calls
- FastAPI backend for PBX configuration and status
- PostgreSQL persistence for extensions, groups, trunks, IVR menus, and call records
- Docker Compose deployment
- Web administration interface

## Architecture

```text
SIP Phones / Softphones
          |
       SIP / UDP
       RTP / UDP
          |
      Asterisk PBX
          |
   FastAPI Backend ---- PostgreSQL
          |
      Web Interface
```

## Repository layout

- `backend/` — FastAPI application and database models
- `frontend/` — browser-based administration interface
- `asterisk/config/` — Asterisk configuration templates
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

### 3. Start the services

For a source deployment:

```bash
docker compose up -d --build
```

For a deployment using the published images:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Check service status and logs:

```bash
docker compose ps
docker compose logs -f backend asterisk db
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

## Network ports

| Component | Protocol | Port |
|---|---|---:|
| Web UI / FastAPI | TCP | 8000 |
| SIP signaling | UDP | 5060 |
| Asterisk AMI | TCP | 5038 (internal/trusted network only) |
| RTP audio | UDP | 10000-20000 |
| PostgreSQL | TCP | 5432 (internal Docker network) |

The Asterisk container uses host networking. Configure the host firewall to allow SIP and RTP only from the office network and any explicitly trusted SIP provider addresses. Do not expose the PBX indiscriminately to the public Internet.

This version does not include SIP-TLS, certificate management, STUN, or TURN. A SIP provider trunk may still be configured separately; connectivity to the provider depends on the provider's transport and the network/firewall configuration.

## Runtime data

Database contents and user-created PBX objects are stored in the PostgreSQL Docker volume. Custom IVR audio is written to `asterisk/sounds/` at runtime. The directory is kept in Git with a placeholder file; personal recordings are intentionally excluded.

A fresh deployment starts with an empty database. Existing deployments keep their current data in their Docker volume unless that volume is deliberately removed.

## Security notes

- This version is intended for a trusted office LAN, not direct exposure of SIP/RTP to the public Internet.
- Never commit `.env`, private keys, recordings, database dumps, or backups.
- Replace all example credentials before starting the stack.
- Restrict AMI to the backend's trusted network and use a dedicated account.
- Do not expose AMI or PostgreSQL directly to the public Internet.
- Configure firewall rules to limit SIP and RTP traffic to trusted devices and provider addresses.
- Use strong, unique SIP extension passwords.

## License

This project is licensed under the Apache License 2.0.
