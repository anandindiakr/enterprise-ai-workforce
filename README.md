# AI Workforce Platform

A production-grade, enterprise-scale **Multi-Agent AI Workforce Platform** built on the
[Swarms](https://github.com/kyegomez/swarms) orchestration framework with first-class
**chat** *and* **real-time voice** interaction.

The platform behaves like a scalable digital enterprise where humans (and other agents)
can chat or speak with specialised departmental agents — Reception, Customer Care,
Sales, HR, Finance, Technology, and Marketing — supervised by a Director / CEO agent
that plans, routes, and escalates work across departments.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            Client (Web / Phone)                          │
│   Next.js dashboard · Browser WebRTC · Twilio SIP · LiveKit rooms        │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │ REST / WebSocket / Media Streams
┌──────────────────────────▼───────────────────────────────────────────────┐
│                       FastAPI API Gateway                                │
│  Auth (JWT/RBAC) · Rate limit · CORS · OpenTelemetry · Structured logs   │
└──────────┬───────────────────────────────────────────────┬──────────────┘
           │                                               │
   ┌───────▼────────┐                              ┌───────▼────────┐
   │  Chat Service  │                              │ Voice Gateway  │
   │  WS / streaming│                              │ STT/TTS/Realtime│
   └───────┬────────┘                              └───────┬────────┘
           │                  Workforce Router (SwarmRouter)│
           └─────────────────────┬─────────────────────────┘
                                 │
                ┌────────────────▼─────────────────┐
                │      HierarchicalSwarm            │
                │  Director ── Department Agents    │
                │  (Reception, Sales, HR, Finance,  │
                │   Tech, Marketing, Customer Care) │
                └────┬───────────┬──────────────────┘
                     │           │
        ┌────────────▼┐         ┌▼──────────────┐
        │ MCP Registry │         │   Memory      │
        │  CRM HRIS    │         │ Redis (short) │
        │  ERP Tickets │         │ Chroma (long) │
        │  Calendar …  │         └───────────────┘
        └──────────────┘
```

---

## Highlights

- **Swarms-idiomatic** — agents, `SwarmRouter`, and `HierarchicalSwarm` follow the
  upstream `CLAUDE.md` spec; only top-level imports are used.
- **`max_loops="auto"`** for reasoning, support, voice, and diagnostic agents.
- **Hierarchical orchestration** — Director plans → managers supervise → workers execute.
- **Pluggable Voice stack** — OpenAI Realtime, Deepgram, ElevenLabs, Twilio Voice,
  LiveKit, Azure, and Google providers behind a single `VoiceGateway` abstraction.
- **MCP everywhere** — modular connectors for CRM, HRIS, ERP, accounting, ticketing,
  knowledge bases, calendar, email, and analytics, with secure permission isolation
  and audit logging.
- **Memory** — Redis short-term + ChromaDB vector long-term + RAG-style retrieval.
- **Cloud-native** — Dockerfile, `docker-compose.yml`, and Kubernetes manifests with
  HPA + ingress, ready for AWS / Azure / GCP.
- **Observability** — Loguru structured JSON logs + OpenTelemetry traces + Prometheus.
- **Security** — JWT auth, RBAC, rate limiting, encrypted secrets, tenant isolation,
  audit trails.
- **Frontend** — Next.js 14 dashboard with Chat console + Voice console (WebRTC).

---

## Project Layout

```
.
├── app/
│   ├── agents/         # AgentProfile, prompts, factory, Director, departments
│   ├── api/            # FastAPI routes + WebSocket endpoints
│   ├── core/           # config, logging, exceptions
│   ├── mcp/            # MCP base + 8 connector implementations + registry
│   ├── memory/         # Redis short-term + Chroma long-term
│   ├── models/         # Pydantic schemas (chat, voice, platform)
│   ├── security/       # JWT, RBAC, password hashing
│   ├── services/       # ChatService and orchestration glue
│   ├── swarms/         # WorkforceRouter (SwarmRouter wrapper) + HierarchicalSwarm setup
│   ├── telemetry/      # OpenTelemetry tracing init
│   ├── voice/          # Gateway + providers + session manager
│   └── main.py         # FastAPI factory + lifespan
├── frontend/           # Next.js 14 dashboard (chat + voice consoles)
├── deploy/
│   ├── k8s/            # Namespace, ConfigMap, Secrets, Deployment, HPA, Ingress
│   └── prometheus.yml
├── scripts/run.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Backend — local dev with `uv`

```bash
uv venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env                  # fill in API keys
python -m scripts.run
```

API at `http://localhost:8000`, OpenAPI docs at `/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at `http://localhost:3000`.

### 3. Full stack with Docker Compose

```bash
docker compose up -d --build
```

Brings up API, worker, Redis, ChromaDB, Postgres, Prometheus, and the Next.js
frontend.

### 4. Kubernetes

```bash
kubectl apply -f deploy/k8s/
```

---

## Sample Voice Flow

1. User opens `/voice` in the dashboard and clicks **Start Call**.
2. Frontend `POST /api/v1/voice/sessions` returns `session_id`.
3. Browser opens `WS /api/v1/ws/voice/{session_id}` and streams PCM audio.
4. `VoiceGateway.stt()` (Deepgram by default) emits live partial + final transcripts.
5. Final transcripts go to `VoiceSessionManager.handle_user_utterance()` →
   `WorkforceRouter` → Director → routed department agent.
6. The agent's text response is synthesised by `VoiceGateway.tts()` (ElevenLabs by
   default) and streamed back as binary audio frames.
7. Control tokens like `{"transfer": "sales"}` or `{"escalate": "human"}` embedded by
   the agent trigger live conversation transfers / supervisor handoffs.
8. The full session summary is persisted in long-term memory for cross-agent recall.

---

## Sample Chat Flow

```bash
curl -X POST http://localhost:8000/api/v1/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
        "session_id": "demo",
        "user_id": "u-1",
        "message": "I need help reconciling last month'\''s invoices."
      }'
```

The Director auto-routes to the Finance agent, which may invoke the Accounting MCP
connector, return a structured response, and persist a conversation summary in Redis +
Chroma.

---

## Security & Multi-Tenancy

- All requests require a JWT (issued via `/api/v1/auth/token`); RBAC is enforced
  through scopes (`agent.invoke`, `voice.stream`, `admin.platform`, …).
- Tenant ID flows through every layer (chat, voice, MCP, memory) and is used for
  Chroma collection partitioning and Redis key namespacing.
- MCP calls go through the `MCPRegistry` permission gate and are audit-logged with
  request hashes.

---

## Observability

- Structured JSON logs via Loguru, ready for shipping to ELK / Loki.
- OpenTelemetry tracing across FastAPI + Swarms + MCP boundaries.
- Prometheus scrape config in `deploy/prometheus.yml`.

---

## Extending

Add a new department:

1. Append a `DepartmentKey` value in `app/agents/profiles.py`.
2. Add an `AgentProfile` and a system prompt in `app/agents/prompts.py`.
3. Register a manager in `WorkforceRouter._build_swarm()` and the Director routing
   logic.
4. (Optional) Wire a new MCP connector under `app/mcp/`.

Add a new voice provider:

1. Subclass `STTProvider` / `TTSProvider` in `app/voice/providers/`.
2. Register the import in `VoiceGateway._resolve()`.
3. Set `VOICE_PROVIDER_*` in `.env` to the new provider name.

---

## License

Proprietary — internal enterprise use.
