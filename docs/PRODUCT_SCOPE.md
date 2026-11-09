# HiglowCloud MVP

## Implemented control-plane capabilities
- Email/password registration and sign-in. No Google or social OAuth.
- Automatic personal workspace creation and organization-scoped records.
- Project creation, framework selection, GitHub HTTPS repository reference and ZIP upload intake.
- Deployment queue, history, cancellation and redeploy requests.
- Encrypted environment-variable storage; secret values are not returned by list endpoints.
- Custom-domain claims with DNS verification tokens.
- PostgreSQL and Redis provisioning requests.
- Usage event ledger and workspace audit log.
- Platform admin overview, customer listing, deployment listing and account-disable action.
- Responsive dashboard for projects, deployments, domains, databases, environment, usage, audit and settings.

## Honest deployment status
A deployment request is queued; it is not a live deployment until an isolated build worker processes it and a runtime node starts the resulting workload. GitHub URLs are stored as source references; a GitHub App/private repository integration and actual source fetch/build pipeline are not connected yet. ZIP uploads are written to the configured upload directory, which is ephemeral on a standard Render free web service.

## Authentication
The platform uses email and password only. Passwords are salted and derived with scrypt. Set a unique high-entropy SECRET_KEY in production. Set ADMIN_EMAILS before registering the platform operator account. The current MVP does not include email verification, password reset, MFA, Google login or other OAuth providers; add these before a public launch.

## Required environment variables
- DATABASE_URL: PostgreSQL connection string.
- SECRET_KEY: random secret of at least 32 characters.
- ADMIN_EMAILS: comma-separated platform administrator email addresses.
- FRONTEND_ORIGIN: exact dashboard origin(s), comma-separated.
- APP_ENV: production on the deployed API.
- MAX_UPLOAD_MB: ZIP upload cap.
- UPLOAD_DIR: upload spool directory; use persistent storage or object storage before relying on uploaded source.
