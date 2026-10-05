Markdown# 📞 Asterisk Web PBX

> A modern, fully containerized VoIP platform built around **Asterisk**, **FastAPI**, **PostgreSQL**, and **CoTURN**.

A complete Docker-based solution for deploying and managing an **Asterisk PBX** with a web-oriented backend API, persistent PostgreSQL storage, and integrated STUN/TURN support for reliable communication across NAT.

---

## 🚀 Fast Deployment (Production Server)

The easiest and fastest way to deploy the PBX on a fresh production server. The automated installer container will set up the directory structure, fetch configuration files, and prepare the environment automatically.

### 1. Run the Auto-Installer
Copy and paste this command into your server terminal:
```bash
sudo docker run --rm -v "$HOME/asterisk-veb:/app" ghcr.io/fedor-afrin/asterisk-veb-installer:latest
2. Start the StackNavigate to the newly created directory and start the services:Bashcd ~/asterisk-veb
Bashdocker compose up -d
That's it! The system is now up and running.✨ Features🟢 Asterisk PBXStandard SIP over UDP & Secure SIP over TLSRTP / SRTP media handling⚡ FastAPI BackendHigh-performance asynchronous API for PBX management🐘 PostgreSQLPersistent application data (endpoints, dialplans, settings)🌐 CoTURNSTUN/TURN server for NAT traversal🐳 Fully DockerizedReproducible deployments & isolated services🏗️ ArchitecturePlaintext                         ┌─────────────────────┐
                         │      SIP Client     │
                         │  Softphone / Phone  │
                         └──────────┬──────────┘
                                    │
                           SIP / SIP-TLS
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │       Asterisk PBX        │
                    │                           │
                    │  SIP │ TLS │ RTP / SRTP  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐
          │   FastAPI API   │         │     CoTURN      │
          │                 │         │   STUN / TURN   │
          └────────┬────────┘         └─────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │   PostgreSQL    │
          │    Database     │
          └─────────────────┘
🌐 Services & PortsServiceProtocolPortDescriptionFastAPIHTTP8000Backend APIPostgreSQLTCP5432DatabaseAsterisk SIPUDP5060Standard SIPAsterisk SIP-TLSTCP5061Secure SIPAsterisk RTP/SRTPUDP10000-10099Media streamsCoTURNUDP/TCP3478STUN/TURNCoTURN TLSTCP5349STUN/TURN over TLS🔒 Production ConsiderationsBefore exposing the PBX to the Internet, make sure to:Use strong SIP credentials and secure PostgreSQL passwords.Enable SIP-TLS where appropriate and configure TLS certificates.Restrict exposed ports with a firewall (e.g., ufw or iptables).Implement intrusion prevention (e.g., fail2ban).⚠️ Never expose an Asterisk installation to the public Internet without appropriate security controls.📄 LicenseThis project is licensed under the Apache License 2.0.