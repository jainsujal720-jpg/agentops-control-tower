# Stage 2 — Architecture decisions

## Purpose

Set up a small, runnable backend foundation for AgentOps Control Tower. This stage checks that the service can start and reach its database. It does not implement an AI agent or connect an external model API.

## Component choices

| Component | Stage 2 choice | Why it is here | What it does not do yet |
|---|---|---|---|
| Backend API | Python + FastAPI | Creates HTTP endpoints, validates typed request/response data as features are added, and publishes an OpenAPI page at `/docs` | No agent behavior or business workflow yet |
| Database | PostgreSQL 18 container | Gives us a persistent relational store for future runs, traces, evaluations, and reviewer decisions | No application tables or migrations yet |
| Local service runner | Docker Compose | Describes API and database together, waits for the database health check before starting the API, and keeps database data in a named volume | Not a production deployment design |
| Dashboard | Deferred | The API is the foundation the future dashboard will use | No UI in this stage |
| LLM provider | Deferred | Keeps setup independent from provider credentials while we build service structure | No model requests or model cost yet |
| Redis / background workers | Deferred | Adds components only when asynchronous ingestion or job processing is introduced | No queue or cache in this stage |

FastAPI’s official getting-started guide shows the app and path-operation pattern used here. Docker documents Compose as a way to configure and run an application’s services together. The PostgreSQL container uses the official image. [FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/) · [Docker Compose](https://docs.docker.com/compose/intro/) · [PostgreSQL image](https://hub.docker.com/_/postgres)

## Request and readiness behavior

| Request | Expected success response | Purpose |
|---|---|---|
| `GET /` | `200 {"service":"agentops-control-tower-api","stage":"2-foundation"}` | Gives a developer a simple service identity response |
| `GET /healthz` | `200 {"status":"ok"}` | Liveness: checks whether the API process can answer a request; it intentionally does not depend on PostgreSQL |
| `GET /readyz` | `200 {"status":"ready","database":"connected"}` | Readiness: checks whether the API can use PostgreSQL |
| `GET /readyz` when DB is down | `503 {"detail":"database is not ready"}` | Prevents a running API from being mistaken for a usable service |
| `GET /docs` | Interactive OpenAPI UI | Lets a developer inspect and manually try the HTTP endpoints |

The readiness handler makes a short `SELECT 1` query using the PostgreSQL driver. `DATABASE_URL` tells the API where the database is; inside Compose the hostname is `db`, which is the Compose service name. The example credential is for local development only.

## Local service flow

1. Compose creates or reuses a PostgreSQL container and a named volume.
2. PostgreSQL reports healthy after it accepts readiness checks.
3. Compose then starts the API container with `DATABASE_URL` configured.
4. The API answers liveness checks; readiness also tries a database connection.
5. The API is published only on `127.0.0.1` by default, so it is reachable from the local machine and not exposed to the local network by this Compose configuration.

## Stage 2 boundary

This is a development foundation, not a production-ready service. It has no authentication, schema migration system, database tables, rate limiting, audit records, or production secret management. We will add these when a later stage needs them and explain the reason at that point.
