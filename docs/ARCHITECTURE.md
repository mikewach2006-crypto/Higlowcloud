# HiglowCloud architecture

HiglowCloud separates three planes:

- Control plane: React dashboard, FastAPI API and PostgreSQL metadata hosted on Render.
- Build plane: isolated workers on separately provisioned VPS infrastructure.
- Runtime plane: customer application workloads on VPS nodes behind an edge proxy with managed TLS.

The API manages identities, workspaces, projects, deployment requests, environment variables, domain claims, database requests, usage records and audit events. It does not execute customer code or expose the Docker socket.

The current deployment lifecycle stops at a durable deployment request in the metadata database. A separate worker fleet, artifact storage, runtime orchestration and edge routing must be connected before deployments become live.

Legacy project/deployment tables from the first unauthenticated MVP are upgraded in place on API startup. Existing unassigned project records are adopted into the first registered workspace so the initial data is not silently discarded.
