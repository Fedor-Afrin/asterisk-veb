# 📞 Asterisk Web PBX

> A modern, fully containerized VoIP platform built around **Asterisk**, **FastAPI**, **PostgreSQL**, and **CoTURN**.

A complete Docker-based solution for deploying and managing an **Asterisk PBX** with a web-oriented backend API, persistent PostgreSQL storage, and integrated STUN/TURN support for reliable communication across NAT.

---

## 🚀 Fast Deployment (Production Server)

The easiest and fastest way to deploy the PBX on a fresh production server. The automated installer container will set up the directory structure, fetch configuration files, and prepare the environment automatically.

### 1. Run the Auto-Installer

Copy and paste this command into your server terminal:

```bash
sudo docker run --rm -v "$HOME/asterisk-veb:/app" ghcr.io/fedor-afrin/asterisk-veb-installer:latest
```

### 2. Start the Stack

Navigate to the newly created directory and start the services:

```bash
cd ~/asterisk-veb
docker sudo compose up -d
```

That's it! The system is now up and running.

---

## ✨ Features

### 🟢 Asterisk PBX
- Standard SIP over UDP & Secure SIP over TLS
- RTP / SRTP media handling

### ⚡ FastAPI Backend
- High-performance asynchronous API for PBX management

### 🐘 PostgreSQL
- Persistent application data (endpoints, dialplans, settings)

### 🌐 CoTURN
- STUN/TURN server for NAT traversal

### 🐳 Fully Dockerized
- Reproducible deployments & isolated services

---

## 🏗️ Architecture

```plaintext
                         ┌─────────────────────┐
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
```

---

## 🌐 Services & Ports

| Service        | Protocol | Port        | Description        |
|----------------|----------|-------------|--------------------|
| FastAPI        | HTTP     | 8000        | Backend API        |
| PostgreSQL     | TCP      | 5432        | Database           |
| Asterisk SIP   | UDP      | 5060        | Standard SIP       |
| Asterisk SIP-TLS | TCP    | 5061        | Secure SIP         |
| Asterisk RTP/SRTP | UDP   | 10000-10099 | Media streams      |
| CoTURN         | UDP/TCP  | 3478        | STUN/TURN          |
| CoTURN TLS     | TCP      | 5349        | STUN/TURN over TLS |

---

## 🔒 Production Considerations

Before exposing the PBX to the Internet, make sure to:

- Use strong SIP credentials and secure PostgreSQL passwords.
- Enable SIP-TLS where appropriate and configure TLS certificates.
- Restrict exposed ports with a firewall (e.g., `ufw` or `iptables`).
- Implement intrusion prevention (e.g., `fail2ban`).

> ⚠️ **Never expose an Asterisk installation to the public Internet without appropriate security controls.**

---

## 📄 License

This project is licensed under the **Apache License 2.0**.