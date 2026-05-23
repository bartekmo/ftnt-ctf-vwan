# Fortinet EMEA Xperts26 — CTF Platform

CTF platform for the FortiGate in Azure vWAN workshop at **Xperts26, Madrid, 6-11 July 2026**.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Attendees / Trainer                  │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────┐
│              React SPA  (Nginx, Docker)                  │
│              Cloud Run / Azure Container Apps            │
└─────────────────────────┬───────────────────────────────┘
                          │ REST + WebSocket
┌─────────────────────────▼───────────────────────────────┐
│              FastAPI  (Python 3.12, Docker)               │
│              Cloud Run / Azure Container Apps            │
└──────────┬──────────────────────────────┬───────────────┘
           │ SQLAlchemy                   │ (future)
┌──────────▼──────────┐      ┌────────────▼───────────────┐
│  PostgreSQL 16       │      │  Challenge Probers         │
│  Cloud SQL / Azure  │      │  (Azure-only, privileged)  │
│  Database for PG    │      │  Implemented separately    │
└─────────────────────┘      └────────────────────────────┘
```

## Components

| Path | Description |
|------|-------------|
| `backend/` | FastAPI REST API + WebSocket server |
| `frontend/` | React SPA with attendee & trainer UIs |
| `probers/` | Challenge probers (Azure, implemented later) |
| `infra/` | Docker Compose for local dev, deployment scripts |

## Quick Start (local)

```bash
cp backend/.env.example backend/.env
docker compose -f infra/docker/docker-compose.yml up --build
```

Frontend: http://localhost:3000  
API docs: http://localhost:8000/docs  
API redoc: http://localhost:8000/redoc

## Personas

- **Attendee** — register, join/create team, read challenges, use hints (costs points), view scoreboard
- **Trainer** — all attendee views + manage challenges, teams, attendees, start/stop/reset CTF, view hint usage per team

## Scoring

- Base points per challenge set by trainer
- Deduction for hints (configured per hint)
- Time bonus: earlier solves score higher (probers will record solve time)
- First-blood bonus: first team to solve a challenge gets extra points (configurable)

## Event

**Fortinet EMEA Xperts26 | Madrid | 6-11 July 2026**
