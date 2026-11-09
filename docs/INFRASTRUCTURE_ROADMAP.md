# Infrastructure activation and security runbook

## Plane separation
1. Control plane: dashboard, FastAPI API and metadata PostgreSQL on Render.
2. Build plane: separate isolated build workers on VPS nodes.
3. Runtime plane: separate customer application workloads on VPS nodes behind an edge proxy.

Never execute customer source inside the public API service. Never expose the Docker socket to the public API.

## Build and runtime prerequisites
- Provision VPS nodes and register them with authenticated, short-lived node credentials.
- Add a signed job queue and worker heartbeat/claim/report endpoints.
- Use isolated builder VMs or rootless BuildKit.
- Run untrusted customer workloads in per-tenant sandboxes; prefer gVisor/Kata or microVM isolation over a shared privileged Docker daemon.
- Enforce CPU, RAM, process, disk, execution-time and concurrent-build quotas.
- Drop Linux capabilities, use non-root identities, read-only root filesystems, seccomp and AppArmor.
- Deny cloud metadata endpoints and private control-plane networks; define explicit outbound network policy.
- Store source archives and build artifacts in private object storage with expiring access URLs.
- Redact environment values from logs; use short-lived build secrets and encrypt secrets at rest.
- Add health checks, deploy promotion, rollback, log streaming, cleanup and resource metering.

## Edge, domains and certificates
- Point wildcard DNS for the HiglowCloud app domain at the edge proxy.
- Verify custom-domain ownership before enabling routing.
- Connect an edge proxy such as Traefik or Caddy and automate TLS issuance/renewal.
- Never route a hostname to a deployment until its domain claim is verified.

## Managed databases
A dedicated provisioner must create per-customer PostgreSQL/Redis instances, generate credentials, store them encrypted, apply network isolation, meter resources and run tested backups/restores. The current API records database requests only.

## Before public launch
- Implement password reset, email verification and MFA.
- Add membership invitations and role-based access controls.
- Add worker authentication, signed jobs, node lifecycle and server-side authorization.
- Add object storage, persistent upload handling and retention policies.
- Add billing, plan enforcement, abuse reporting, support and incident response.
- Add automated security tests, dependency scanning, backup restore drills and load tests.
- Complete a threat model and independent security review.

## Current truth
The control plane stores account/project metadata and queues deployment requests. Build execution, live runtime hosting, TLS routing, managed database provisioning, usage-based billing and worker fleet orchestration remain inactive until their infrastructure components are deployed and verified.
