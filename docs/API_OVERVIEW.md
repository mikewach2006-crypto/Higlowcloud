# API overview

Base path: /api/v1

## Authentication
- POST /auth/register — email/password registration and workspace creation.
- POST /auth/login — email/password sign-in.
- GET /auth/me — current account and workspace role.

Send the returned bearer token in the Authorization header.

## Projects and deployments
- GET /projects
- POST /projects
- DELETE /projects/{project_id}
- GET /projects/{project_id}/deployments
- POST /projects/{project_id}/deployments
- POST /projects/{project_id}/source/zip
- POST /deployments/{deployment_id}/cancel
- POST /deployments/{deployment_id}/redeploy
- GET /deployments/{deployment_id}/logs

## Configuration and resources
- GET/PUT /projects/{project_id}/env
- DELETE /projects/{project_id}/env/{key}
- GET/POST /projects/{project_id}/domains
- DELETE /domains/{domain_id}
- GET/POST /projects/{project_id}/databases
- GET /usage
- GET /audit

## Platform administration
Requires a platform-admin account provisioned through ADMIN_EMAILS:
- GET /admin/overview
- GET /admin/users
- GET /admin/deployments
- POST /admin/users/{user_id}/disable

## Health and status
- GET /health
- GET /status

The API currently queues deployments and resource requests. It does not yet provision application runtimes, edge routing or managed databases.


## Android build workspace

Requires an authenticated HiglowCloud account unless marked internal:
- GET `/android-builds/status` — build provider and setup status.
- GET `/android-builds` — current workspace build history and status refresh.
- POST `/android-builds` — queue a supported Android build from an installed GitHub repository.
- GET `/android-builds/{build_id}/download` — authenticated private artifact download.
- POST `/android-builds/internal/claim` — internal GitHub Actions runner claim; the API validates the workflow run and returns a short-lived, source-repository-only read token.
- POST `/android-builds/internal/complete` — internal runner completion callback; the API validates the workflow run and records the private artifact.

The GitHub App needs Contents: read and Actions: read/write permissions and must be installed on both HiglowCloud and the selected source repository. See `docs/ANDROID_BUILDS.md`.
