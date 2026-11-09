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
