# 🎙️ AI Debate Coach

> Real-Time AI Debate Coach with Predictive Turn-Taking

A full-stack web application that listens to a user debating in real time, transcribes their speech, predicts natural turn boundaries, and responds with AI-generated coaching feedback — all over a single WebSocket connection.

Built as a final-year project exploring low-latency human–AI spoken interaction.

---

## Features

| Feature | Detail |
|---|---|
| **Streaming STT** | Deepgram Nova-3 via WebSocket — real-time interim + final transcripts |
| **Predictive turn-taking** | Hybrid VAD (RMS energy + optional Silero) with adaptive silence thresholds |
| **LLM coaching** | Groq-hosted models respond to user arguments with debate feedback |
| **TTS playback** | AI responses synthesised to audio and streamed back to the browser |
| **Google OAuth** | One-tap sign-in, JWT session tokens |
| **Session history** | Past debates stored in PostgreSQL, browseable from the dashboard |
| **Latency metrics** | End-to-end pipeline timing (STT → LLM → TTS) tracked per session |
| **Single-container prod** | Multi-stage Docker build bundles the Vite SPA into the FastAPI server |

---

## Tech Stack

### Backend
- **Python 3.12** / **FastAPI** / **Uvicorn**
- **WebSockets** — persistent bidirectional audio + control channel
- **Deepgram SDK** — streaming speech-to-text (Nova-3)
- **OpenAI Python SDK → Groq** — LLM inference
- **SQLAlchemy 2 + asyncpg** — async PostgreSQL ORM
- **Alembic** — database migrations
- **PyJWT + bcrypt** — authentication

### Frontend
- **React 18** / **TypeScript** / **Vite**
- **Zustand** — state management
- **React Router 7** — client-side routing
- **Web Audio API** — microphone capture, 48 kHz → 16 kHz resampling, PCM16 encoding
- **Google OAuth** (`@react-oauth/google`)

### Infrastructure
- **Docker Compose** — dev (3 containers) and prod (2 containers) configurations
- **PostgreSQL 16** (Alpine)
- **GitHub Actions** — CI/CD with test gate → SSH deploy
- **Azure VM** — production host

---

## Project Structure

```
finalyear/
├── backend/
│   ├── Dockerfile              # Multi-stage: Node build → Python runtime
│   ├── requirements.txt
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, SPA static mount
│   │   ├── config.py           # Pydantic settings (env vars)
│   │   ├── db/                 # SQLAlchemy models, session, init
│   │   ├── routers/
│   │   │   ├── api.py          # REST endpoints (sessions, health)
│   │   │   ├── auth.py         # Google OAuth + JWT auth routes
│   │   │   └── ws_handler.py   # WebSocket: audio → STT → turn-taking → LLM → TTS
│   │   ├── schemas/            # Pydantic message schemas
│   │   └── services/
│   │       ├── stt_service.py          # Deepgram / Groq / local STT
│   │       ├── llm_service.py          # LLM coaching responses
│   │       ├── tts_service.py          # Text-to-speech synthesis
│   │       ├── turn_taking_service.py  # Hybrid VAD + silence detection
│   │       ├── session_service.py      # DB session CRUD
│   │       ├── auth_service.py         # JWT + Google token verification
│   │       ├── metrics_service.py      # Pipeline latency tracking
│   │       └── latency_tracker.py      # Per-stage timing
│   └── tests/                  # Unit + integration tests (pytest)
├── web/
│   ├── src/
│   │   ├── components/         # Layout, Transcript, TurnIndicator, etc.
│   │   ├── hooks/              # useAudioCapture, useWebSocket
│   │   ├── pages/              # Auth, Debate, Dashboard, History, etc.
│   │   └── stores/             # Zustand stores (auth, app, debate)
│   └── public/
├── shared/types/               # TypeScript message type definitions
├── docker-compose.yml          # Development stack
├── docker-compose.prod.yml     # Production stack
├── Makefile                    # Convenience commands
└── .github/workflows/
    └── deploy-azure.yml        # CI/CD: test → deploy over SSH
```

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** v2+
- A [Deepgram](https://console.deepgram.com) API key (free $200 credit)
- A [Groq](https://console.groq.com) API key (free tier)
- A Google OAuth Client ID (from [Google Cloud Console](https://console.cloud.google.com/apis/credentials))

### 1. Clone the repo

```bash
git clone https://github.com/nekumartins/finalyear.git
cd finalyear
```

### 2. Create your `.env` file

```bash
cp .env.example .env   # or create manually
```

Required variables:

```env
# API Keys
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key

# Auth
SECRET_KEY=some-random-secret-string
VITE_GOOGLE_CLIENT_ID=your_google_oauth_client_id.apps.googleusercontent.com

# STT provider: deepgram (default), groq, or faster-whisper
STT_PROVIDER=deepgram

# CORS (production domain, or * for dev)
ALLOWED_ORIGINS=*
```

### 3. Run the dev stack

```bash
make dev
# or: docker compose up --build
```

This starts:
| Service | URL |
|---|---|
| Frontend (Vite HMR) | http://localhost:3000 |
| Backend (FastAPI) | http://localhost:8000 |
| PostgreSQL | localhost:5432 |

### 4. Run the production stack

```bash
make prod
# or: docker compose -f docker-compose.prod.yml up --build -d
```

In production, the Vite SPA is compiled into the backend container and served from FastAPI at **http://localhost:8000**.

---

## Makefile Commands

| Command | Description |
|---|---|
| `make dev` | Start dev stack (hot-reload, foreground) |
| `make dev-d` | Start dev stack (detached) |
| `make prod` | Build + start production stack |
| `make down` | Stop dev stack |
| `make prod-down` | Stop production stack |
| `make logs` | Tail all logs (`make logs s=backend` for one service) |
| `make ps` | Show running containers |
| `make shell` | Open bash in backend container |
| `make migrate` | Run Alembic migrations |

---

## Running Tests

```bash
# With conda/venv (from repo root):
pip install -r backend/requirements.txt
python -m pytest backend/tests/ -x --tb=short

# Inside the backend container:
make shell
pytest backend/tests/ -x --tb=short
```

---

## CI/CD

The GitHub Actions workflow ([.github/workflows/deploy-azure.yml](.github/workflows/deploy-azure.yml)) runs on every push to `master`:

1. **Test** — installs dependencies and runs `pytest` (unit tests, no integration/edge)
2. **Deploy** — SSHs into the production VM, pulls the latest code, rebuilds Docker containers

### Required GitHub Secrets

| Secret | Value |
|---|---|
| `AZURE_SSH_PRIVATE_KEY` | SSH private key for the production server |
| `AZURE_SSH_HOST` | Server hostname / IP |
| `AZURE_SSH_USER` | SSH username |

Optional: `AZURE_SSH_PORT` (default 22), `AZURE_SSH_KNOWN_HOSTS`, `AZURE_APP_DIR`.

---

## Architecture

```
Browser                          Server (Azure VM)
┌──────────┐    WebSocket       ┌────────────────────────────────┐
│  React   │◄──────────────────►│  FastAPI  ws_handler.py        │
│  App     │  audio_chunk (b64) │                                │
│          │  transcripts       │  ┌──────────┐  ┌───────────┐  │
│  Audio   │  ai_response       │  │ Deepgram │  │ Groq LLM  │  │
│  Capture │  tts_audio         │  │ STT (WS) │  │ (REST)    │  │
│  16kHz   │  state changes     │  └──────────┘  └───────────┘  │
└──────────┘                    │                                │
                                │  ┌──────────┐  ┌───────────┐  │
                                │  │ Turn-    │  │ TTS       │  │
                                │  │ Taking   │  │ Service   │  │
                                │  │ (VAD)    │  │           │  │
                                │  └──────────┘  └───────────┘  │
                                │                                │
                                │  ┌──────────────────────────┐  │
                                │  │ PostgreSQL (sessions,    │  │
                                │  │ users, metrics)          │  │
                                │  └──────────────────────────┘  │
                                └────────────────────────────────┘
```

**Audio pipeline**: Mic → ScriptProcessorNode (48 kHz) → resample to 16 kHz → PCM16 LE → base64 → WebSocket → Deepgram streaming → interim/final transcripts → hybrid turn-taking → Groq LLM → TTS → audio back to browser.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async Postgres connection string |
| `SECRET_KEY` | Random per-process | JWT signing key (set explicitly in prod) |
| `DEEPGRAM_API_KEY` | — | Deepgram API key for streaming STT |
| `GROQ_API_KEY` | — | Groq API key for LLM inference |
| `STT_PROVIDER` | `deepgram` | STT engine: `deepgram`, `groq`, or `faster-whisper` |
| `VITE_GOOGLE_CLIENT_ID` | — | Google OAuth client ID (build-time) |
| `ALLOWED_ORIGINS` | — | Comma-separated CORS origins, or `*` |
| `DEBUG` | `false` | Enable debug logging |
| `VAD_THRESHOLD` | `0.5` | Silero VAD confidence threshold |

---

## License

This project is part of a final-year academic submission. All rights reserved.
