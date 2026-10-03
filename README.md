Markdown
# Asterisk Web PBX

A modern, fully containerized solution for deploying and managing an Asterisk PBX system with a FastAPI backend and PostgreSQL database.

## 🚀 Features
- **Asterisk PBX**: Pre-configured for standard SIP (UDP) and secure SIP over TLS.
- **FastAPI Backend**: High-performance asynchronous API for PBX management.
- **PostgreSQL**: Reliable data storage for endpoints, dialplans, and system settings.
- **CoTURN**: Integrated STUN/TURN server for NAT traversal (ensuring reliable SIP signaling and RTP/SRTP media stream delivery).
- **Dockerized**: Ready for both local development and production deployment out of the box.
- **CI/CD**: Automated builds and image publishing to GitHub Container Registry (GHCR).

## 🛠 Prerequisites
Make sure you have the following installed on your machine:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## 📦 Quick Start (Production)
To run the pre-built images directly from the GitHub Container Registry (GHCR) without building them locally, follow these steps:

1. Clone the repository:
   ```bash
   git clone [https://github.com/Fedor-Afrin/asterisk-veb.git](https://github.com/Fedor-Afrin/asterisk-veb.git)
   cd asterisk-veb
Start the production stack:

Bash
docker compose -f docker-compose.prod.yml up -d
💻 Local Development
If you want to modify the code, develop new features, and build the images locally:

Start the development stack (this will build the containers from source):

Bash
docker compose up -d --build
To stop and remove the development containers:

Bash
docker compose down
🌐 Services & Ports
Once the containers are up and running, the following services will be available:

Backend API: http://localhost:8000

PostgreSQL Database: localhost:5432 (internal: db)

Asterisk SIP (UDP): udp/5060

Asterisk SIP (TLS): tcp/5061

Asterisk Media (RTP/SRTP): udp/10000-10099