# Peach — Project Structure

This document defines the repository structure, technology stack, contracts between components, and local service dependencies.

## 2. Stack

**Backend**

- Python 3.14, dependencies managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`)
- FastAPI + Uvicorn
- SQLAlchemy 2.x (async, `asyncpg` driver)
- Alembic for migrations
- Pydantic v2 / pydantic-settings for config
- pytest + pytest-asyncio + httpx for tests
- ruff for lint and format

**Frontend**

- Node 22 (in Docker), pnpm 10
- Next.js 16 (App Router, TypeScript, `src/` disabled — app at the `frontend/` root)
- Tailwind CSS v4
- shadcn/ui (`radix-nova` preset, Lucide icons, CSS variables enabled)
- TanStack Query for server state, `zod` for response validation
- react-hook-form + `@hookform/resolvers` for forms
- vitest + Testing Library

**Infrastructure**

- Docker + Docker Compose v2
- PostgreSQL 17 (`postgres:17-alpine`)

---

## 3. Repository layout

```
Peach/
├── README.md
├── .env.example                  # every variable Compose reads; committed
├── .gitignore
├── docker-compose.yml            # base: db, backend, frontend
├── docker-compose.override.yml   # dev: bind mounts + hot reload (auto-loaded)
├── Makefile                      # thin wrappers over the compose and deploy commands
│
├── .github/workflows/
│   ├── lint.yml                  # ruff + eslint on every push
│   └── deploy-backend.yml        # ships when a commit message says "deploy"
│
├── infra/
│   ├── backend.yaml              # CloudFormation: Lambda + function URL + Aurora Serverless v2
│   ├── frontend.yaml             # CloudFormation: S3 + CloudFront (+ optional custom domain)
│   └── github-oidc.yaml          # CloudFormation: the role Actions assumes
│
├── scripts/
│   ├── deploy-backend.sh         # build -> ECR -> CloudFormation -> migrate -> BACKEND_URL in .env
│   ├── destroy-backend.sh        # delete the stack, database included
│   ├── deploy-frontend.sh        # static export (against BACKEND_URL) -> S3 -> CloudFront
│   ├── domain-frontend.sh        # us-east-1 ACM certificate + DNS for the frontend's domain
│   ├── destroy-frontend.sh       # delete the bucket and distribution
│   └── github-role.sh            # the OIDC role CI assumes to deploy
│
├── backend/
│   ├── Dockerfile                # builder / dev / runtime stages, plus lambda
│   ├── .dockerignore
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app factory, router + middleware wiring
│   │   ├── config.py             # Settings (pydantic-settings), cached accessor
│   │   ├── db.py                 # async engine, session factory, get_session dependency
│   │   ├── lambda_handler.py     # Lambda entry: function URL -> Mangum, {"action":"migrate"} -> alembic
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── item.py           # placeholder ORM model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── item.py           # ItemCreate / ItemUpdate / ItemRead
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py         # aggregates v1 routers under /api/v1
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       └── items.py      # dummy CRUD
│   │   └── services/
│   │       └── items.py          # business logic, kept out of route handlers
│   ├── migrations/               # alembic env.py, script.py.mako, versions/
│   ├── scripts/
│   │   └── entrypoint.sh         # wait for db → alembic upgrade head → uvicorn
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       └── test_items.py
│
└── frontend/
    ├── Dockerfile                # base / deps / dev / builder / runtime stages
    ├── .dockerignore
    ├── package.json
    ├── pnpm-lock.yaml
    ├── next.config.ts            # output: "standalone"
    ├── tsconfig.json
    ├── vitest.config.mts
    ├── components.json           # shadcn CLI config
    ├── app/
    │   ├── layout.tsx
    │   ├── globals.css
    │   ├── page.tsx              # dashboard: health badge + item list
    │   └── items/page.tsx        # dummy CRUD screen
    ├── components/
    │   ├── ui/                   # shadcn-generated; do not hand-edit
    │   ├── providers.tsx         # QueryClientProvider
    │   ├── site-header.tsx
    │   ├── health-badge.tsx
    │   ├── item-summary.tsx
    │   ├── item-table.tsx
    │   └── item-form-dialog.tsx
    ├── lib/
    │   ├── api.ts                # typed fetch wrapper around NEXT_PUBLIC_API_URL
    │   └── utils.ts              # cn(), added by shadcn init
    └── tests/                    # setup.ts, utils.tsx, *.test.tsx
```

Rule: nothing outside `backend/` imports Python from it, and nothing outside `frontend/` imports
TypeScript from it. The only contract between the two is the HTTP API described in §5.

---

## 4. Configuration

All configuration comes from environment variables. `.env.example` is committed and lists every
variable with a working local default; `.env` is git-ignored and is what Compose actually reads.

```dotenv
# --- database ---
POSTGRES_USER=peach
POSTGRES_PASSWORD=peach
POSTGRES_DB=peach
POSTGRES_PORT=5432

# --- backend ---
DATABASE_URL=postgresql+asyncpg://peach:peach@db:5432/peach
BACKEND_PORT=8000
APP_ENV=development           # development | test | production
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000

# --- frontend ---
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000    # used by the browser
INTERNAL_API_URL=http://backend:8000         # used by Next.js server components
```

Two API URLs are required and are not interchangeable: browser code resolves `localhost`, server
components inside the Compose network resolve the `backend` service name.

`backend/app/config.py` defines a `Settings(BaseSettings)` class mirroring the backend variables,
exposed through a `@lru_cache`d `get_settings()`. No module reads `os.environ` directly.

---

## 5. API contract

Base path `/api/v1`. JSON only. Errors use FastAPI's default shape
(`{"detail": ...}`) with the appropriate status code.

### Authentication

Every route under `/api/v1` requires `Authorization: Bearer <Cognito ID token>`; only `/health`
(liveness) is public. The token's signature is checked against the user pool's public keys, then
its issuer, audience (the web app client), expiry and `token_use == "id"`. Missing or bad token →
`401` with `WWW-Authenticate: Bearer`; no pool configured → `503`, never an open door. The first
request from a person creates their `users` row (keyed by Cognito `sub`), and every item query is
scoped to that user — someone else's item answers `404`, exactly like a missing one.

`users` table: `id uuid pk`, `cognito_sub varchar(64) unique`, `email`, `name`, `created_at`,
`updated_at`. `items.owner_id uuid not null references users(id) on delete cascade`.

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/v1/me` | `{"id", "email", "name", "created_at"}` — the signed-in user |

### Health

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/health` | `{"status": "ok"}` — liveness, no dependencies touched |
| `GET` | `/api/v1/health/ready` | `{"status": "ok", "database": "ok"}` — runs `SELECT 1`; `503` if the DB is unreachable |

### Items (placeholder resource)

| Method | Path | Body | Success |
|--------|------|------|---------|
| `GET` | `/api/v1/items` | — | `200` `{"items": ItemRead[], "total": int}`, query params `limit` (1–100, default 20) and `offset` (default 0) |
| `POST` | `/api/v1/items` | `ItemCreate` | `201` `ItemRead` |
| `GET` | `/api/v1/items/{item_id}` | — | `200` `ItemRead`, `404` if missing |
| `PATCH` | `/api/v1/items/{item_id}` | `ItemUpdate` (all fields optional) | `200` `ItemRead`, `404` if missing |
| `DELETE` | `/api/v1/items/{item_id}` | — | `204`, `404` if missing |

```python
# ItemCreate
name: str                      # 1..120 chars
description: str | None = None # <= 2000 chars
status: "todo" | "in_progress" | "done" = "todo"

# ItemRead = ItemCreate + 
id: uuid.UUID
created_at: datetime           # timezone-aware, UTC
updated_at: datetime
```

`items` table: `id uuid pk default gen_random_uuid()`, `name text not null`,
`description text`, `status varchar(20) not null default 'todo'` (checked to `todo`/`in_progress`/`done`),
`created_at timestamptz not null default now()`, `updated_at timestamptz not null default now()`.

Interactive docs at `/docs` (Swagger) and `/redoc`; the raw schema at `/openapi.json`.

---

## 6. Frontend behaviour

- `/` — log in (email + password, or Google once it is enabled); `/signup` — create an account,
  then enter the code Cognito emails; `/auth/callback` — where Google sign-in lands. Sign-in talks
  to Cognito straight from the browser (`lib/auth.ts`): the public `InitiateAuth` / `SignUp` API
  for passwords, the hosted domain with the OAuth code flow + PKCE for Google. Tokens live in
  `localStorage`; the ID token is renewed from the refresh token a minute before it expires.
- `/home` — progress dashboard: the share of tasks done (headline figure + meter), a stacked
  bar of tasks by status with legend and hover tooltips, a tile per status linking to the board,
  this week's added/completed counts, and short "In progress" / "Recently completed" lists.
- `/home` and `/items` sit behind `AuthGate`, which sends signed-out visitors to `/`. That is a
  convenience: the static export has no server to refuse a page, so the real boundary is the API,
  which answers nothing without a valid token. A `401` from it signs the browser out.
- `/items` — a Trello-style board in Notion styling: one column per status (To do, In progress,
  Done). Cards drag between columns (native HTML5 drag and drop, optimistic update rolled back on
  error); clicking a card opens a `Dialog` with a `react-hook-form` + `zod` form to edit title,
  status and description, or delete (confirmed via `AlertDialog`). Each column has its own "New"
  button, and `Sonner` toasts report outcomes.
- Loading states use `Skeleton`; empty state is a centered card with a call to action; a failed
  fetch renders an `Alert` with a retry button rather than a blank page.

Components to generate with the CLI (`pnpm dlx shadcn@latest add ...`):
`button card table dialog alert-dialog field input textarea checkbox badge skeleton sonner
dropdown-menu label alert`. (`form` is now an empty stub in the registry — `field` replaced it.)

All network access goes through `lib/api.ts`, which reads `NEXT_PUBLIC_API_URL` on the client and
`INTERNAL_API_URL` on the server, throws a typed `ApiError` on non-2xx, and parses responses with
the zod schemas that mirror §5.

---

## 7. Docker Compose

`docker-compose.yml` defines exactly three services on one user-defined network, with a named
volume `pgdata` for the database.

**`db`** — `postgres:17-alpine`, env from `POSTGRES_*`, volume `pgdata:/var/lib/postgresql/data`,
port `${POSTGRES_PORT}:5432` published for local inspection, healthcheck
`pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` (interval 5s, retries 10).

**`backend`** — built from `backend/Dockerfile`, `depends_on: db: {condition: service_healthy}`,
port `${BACKEND_PORT}:8000`, healthcheck on `GET /health`. Its entrypoint runs
`alembic upgrade head` before starting Uvicorn, so a fresh volume comes up migrated.

**`frontend`** — built from `frontend/Dockerfile`, `depends_on: backend: {condition: service_healthy}`,
port `${FRONTEND_PORT}:3000`. `NEXT_PUBLIC_API_URL` is a build arg *and* a runtime env var, since
Next.js inlines `NEXT_PUBLIC_*` at build time.

`docker-compose.override.yml` (loaded automatically, dev only) selects each image's `dev` stage,
bind-mounts `./backend` and `./frontend`, swaps the commands for `uvicorn --reload` and
`next dev`, and keeps `node_modules`, `.next` and `.venv` in named volumes so container
installs are not shadowed by the host mount. Run the production images with
`docker compose -f docker-compose.yml up --build`, which skips the override entirely.

**Dockerfiles** are multi-stage. Backend: `python:3.14-slim` base, `uv sync --frozen --no-dev` into
`/app/.venv`, non-root `app` user, `CMD ["./scripts/entrypoint.sh"]`; its `dev` stage adds the
dev dependency group so `pytest` and `ruff` are available in the container. Frontend:
`node:22-alpine` with pnpm via corepack, `pnpm install --frozen-lockfile` → `pnpm build` →
runtime stage copying `.next/standalone`, `.next/static`, and `public`, running as `node`.

---

