# HiglowCloud deployment worker protocol

## Current state

The API now exposes a private, token-authenticated worker control plane. It can register worker heartbeats, lease queued deployments, deliver project configuration and environment values to an authenticated worker, provide uploaded ZIP sources, accept redacted build logs, and record successful or failed deployments.

**No worker is currently running.** A deployment remains queued until a separately hosted worker is provisioned and connected. The API service must never execute customer build commands itself.

## Render API environment

Configure these only on the HiglowCloud API service:

- `DEPLOY_WORKER_TOKEN`: a randomly generated secret of at least 32 characters. Set the same value on the worker host. Never put it in Vite/frontend variables, GitHub source code, or customer environment variables.
- `DEPLOYMENT_LEASE_SECONDS`: optional lease duration; defaults to 600 seconds and is clamped to 60–3600 seconds.
- `DEPLOYMENT_BASE_DOMAIN`: set to `higlowbiz.co.ke` only after the wildcard DNS, deployment host, reverse proxy, and HTTPS routing have been configured. The API will reject a worker's `live` result until this is set.

The API's existing `SECRET_KEY` must remain unchanged because it protects stored environment variables.

## Worker identity and authentication

Every request must use HTTPS and include:

- `X-HiglowCloud-Worker-Token: <DEPLOY_WORKER_TOKEN>`

The worker must use a stable identifier (3–120 characters, letters, numbers, dot, underscore or hyphen). For ZIP source retrieval, also send:

- `X-HiglowCloud-Worker-Id: <same worker identifier>`

## API sequence

1. Send `POST /internal/worker/heartbeat` with JSON `{"worker_id":"worker-01","version":"0.1.0"}` periodically.
2. Poll `POST /internal/worker/claim` with JSON `{"worker_id":"worker-01"}`. An empty queue returns `{"job":null}`. A claimed job changes to `building` and is leased to that worker.
3. The claim response contains the source type, repository URL/branch or ZIP download path, service/build configuration, and decrypted project environment values. A GitHub installation access token may be included for private repository access.
4. For ZIP jobs, download the supplied `source_download_path` using both worker headers. The source endpoint only serves the ZIP belonging to the active lease.
5. Send build output to `POST /internal/worker/deployments/{uid}/logs` with JSON `{"worker_id":"worker-01","message":"..." }`. Send regular log/lease updates while a build is running; the log endpoint renews the lease.
6. Finish with `POST /internal/worker/deployments/{uid}/complete` and JSON status `live` or `failed`. A `live` result must include a verified HTTPS URL under `DEPLOYMENT_BASE_DOMAIN`. Failed jobs must not include a public URL.

All job mutation endpoints verify that the deployment is still leased to the calling worker. Expired leases are returned to the queue and jobs are failed after three attempts.

## Security requirements for the actual runner

- Run customer builds in isolated containers or stronger sandboxes, never inside the FastAPI process.
- Do not mount the Docker socket into customer containers. Use a dedicated builder/daemon boundary.
- Apply CPU, memory, disk, process-count and execution-time limits.
- Run as an unprivileged identity; use read-only base filesystems where possible.
- Restrict container network access and prevent access to cloud metadata, host services, private networks and the control-plane token.
- Pass environment values only to the job that owns them. Never print them, persist them in build artifacts, or include GitHub installation tokens in logs.
- Treat repository files, Dockerfiles, build scripts and ZIP archives as untrusted input.
- Keep worker tokens out of customer containers and rotate them if exposed.
- Do not report a deployment as live until the reverse proxy routes to the running application and HTTPS has been verified.

## Current limitations

- The worker control plane is implemented, but no worker process, container runtime, reverse proxy, wildcard DNS record or deployment TLS endpoint is provisioned yet.
- Render's current upload directory is ephemeral. ZIP uploads can be lost when the API instance restarts; durable object storage should replace local upload storage before relying on ZIP deployments in production.
- Metrics, persistent runtime management, private service networking, cron execution and database provisioning remain separate infrastructure tasks.
