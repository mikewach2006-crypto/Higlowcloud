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



## Android build workspace (Codemagic)

Requires an authenticated HiglowCloud session:
- GET `/android-builds/status` — Codemagic connection and fixed workflow configuration status.
- GET `/android-builds` — workspace build history and refreshed Codemagic statuses.
- POST `/android-builds` — queue both signed Android APKs using the existing Codemagic workflow.
- GET `/android-builds/{build_id}/download/call` — authenticated standalone Nenva Call APK download.
- GET `/android-builds/{build_id}/download/unified` — authenticated unified Nenva APK download.
- POST `/android-builds/{build_id}/cancel` — cancel an active Codemagic build.

The API requires `CODEMAGIC_API_TOKEN` in the server-side Render environment. The Codemagic app ID and workflow key are fixed to the existing HiglowBiz project and `nenva-android` workflow. The Codemagic API token is never sent to the browser.
