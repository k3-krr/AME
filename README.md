# Adaptive Memory Engine (AME) — Version 0.1 Foundation

Adaptive Memory Engine (AME) is an intelligent, long-term memory architecture designed to manage the full lifecycle of agent context injection: classification, prioritization, retrieval, update, consolidate, reflection, and decay/forgetting. 

Version 0.1 builds the baseline production-ready infrastructure: a clean Next.js client chat dashboard and a FastAPI ASGI service gateway layer. Code layers utilize **Next.js (App Router)** and **FastAPI (DDD-lite layered backend)**.

---

## Technical Stack
- **Client**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, Zustand, Framer Motion
- **Backend API**: Python 3.10+, FastAPI, SQLAlchemy 2.0 (Async), Alembic, Pydantic v2
- **Database**: PostgreSQL (pgvector compatible)
- **Containerization**: Docker, Docker Compose

---

## Project Structure (DDD-lite Baseline)
```text
ame-workspace/
├── backend/                  # Python FastAPI ASGI API service
│   ├── app/
│   │   ├── domain/           # Core Entities & interfaces
│   │   ├── application/      # Orchestrators & business UseCases
│   │   ├── infrastructure/   # DB engines, SQL Repositories, API Clients
│   │   ├── presentation/     # FastAPI routers, payload validations
│   │   └── config.py         # Dynamic Settings parser
│   ├── alembic/              # DB Schema version migrations
│   └── requirements.txt      # Backend Python dependencies
├── frontend/                 # Client User Interface (Next.js)
│   ├── src/
│   │   ├── app/              # Next.js page routes, layouts, templates
│   │   ├── components/       # Interface layout cards (ui, chat)
│   │   ├── hooks/            # Modular state triggers (useStream)
│   │   ├── store/            # Global Zustand stores
│   │   ├── lib/              # Client side utilities (Tailwind selectors merge)
│   │   └── types/            # TypeScript typing definitions
│   └── package.json
└── docker-compose.yml        # Multi-container local orchestration manifest
```

---

## Local Development Quickstart

### Prerequisites
- Node.js 18+ (npm)
- Python 3.10+
- PostgreSQL server active (with database named `ame`)

### 1. Backend API Bootstrap
1. Navigate to `./backend/`:
   ```bash
   cd backend
   ```
2. Initialize virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate virtual environment:
   - **Windows PowerShell**: `.\.venv\Scripts\Activate.ps1`
   - **Linux/macOS**: `source .venv/bin/activate`
4. Install packages:
   ```bash
   pip install -r requirements.txt
   ```
5. Copy environment variables template:
   ```bash
   cp .env.example .env
   ```
6. Spin up development server:
   ```bash
   uvicorn app.presentation.main:app --reload --host 127.0.0.1 --port 8000
   ```
7. Verify active health checks: opening [http://localhost:8000/health](http://localhost:8000/health) or API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend client Bootstrap
1. Navigate to `./frontend/`:
   ```bash
   cd ../frontend
   ```
2. Install client packages:
   ```bash
   npm install
   ```
3. Copy environment variables template:
   ```bash
   cp .env.local.example .env.local
   ```
4. Spin up Next.js client engine:
   ```bash
   npm run dev
   ```
5. Open [http://localhost:3000](http://localhost:3000) using a browser view.

---

## Milestone 10 — Multi-Agent Memory Platform

Milestone 10 introduces the core backend framework to handle agent-aware security boundaries, cryptographic credentials, memory access grants, and collaboration rules.

### 1. Architectural Design
The multi-agent platform implements a strict cleanly separated architecture:
* **Agent Principal Scope**: Every request is executed inside an `AccessContext` representing either a human `USER` or an `AGENT`.
* **Cryptographic Keys**: Agents authenticate using high-entropy API keys (`Authorization: Bearer ame_agent_<key>`), which are validated by comparing their SHA-256 hashes against stored credentials.
* **Controlled Access Control**: Automatic `MANAGE` access is given to the agent who created the memory. For all other agents, access level (`READ`, `WRITE`, `MANAGE`) is checked against unexpired, unrevoked `MemoryAccessGrant` database records.
* **Database Filtration**: Domain rules are compiled into optimal database-level EXISTS subqueries (`apply_memory_auth_filter`) to prevent memory discovery leakage during semantic retrieval, hybrid retrieval, and Knowledge Graph traversals.

### 2. Deployment Configurations
* **CORS Settings**: The `CORS_ALLOWED_ORIGINS` environment variable dynamically configures the allowed client origins for API routes.
* **Production Validation**: In production environments (`ENV=production` or `DEBUG=False`), the application enforces secure credential configurations by rejecting default insecure `JWT_SECRET_KEY` values and failing closed on startup.
