# HiglowCloud architecture

HiglowCloud separates three planes:

- **Control plane:** React dashboard, FastAPI API and PostgreSQL metadata hosted on Render.
- **Build plane:** isolated workers on separately provisioned VPS infrastructure. They fetch source, build images and report logs.
- **Runtime plane:** customer application containers on VPS nodes, routed through a proxy with managed TLS.

The public API must never execute customer code or expose the Docker socket. The current MVP accepts ZIP metadata and marks deployments as simulated. A production build agent, tenant isolation, authentication, resource quotas, network policy, secrets management, backups and abuse controls are still required.

Initial customer flow: create project → upload ZIP → validate archive → create deployment record → later dispatch a signed job to an isolated build worker.
