# Security status

## Implemented control-plane protections
- Email/password authentication with salted scrypt password derivation.
- Signed, expiring bearer tokens.
- Organization-scoped project, deployment, environment, domain, database, usage and audit queries.
- Environment values encrypted at rest with Fernet using a key derived from SECRET_KEY.
- Secret environment values are not returned by list endpoints.
- ZIP size, entry-count, path-traversal and expanded-size checks.
- Platform administrator endpoints protected by the platform-admin flag.
- In-place schema upgrade for the original MVP tables; no table drop or destructive reset.

## Required before public production workloads
- Email verification, password reset, MFA, session revocation and login rate limiting.
- Membership invitations and role-based permissions beyond the initial owner role.
- Signed, replay-protected worker jobs and node identity/rotation.
- Isolated builders and runtime sandboxes; prefer gVisor/Kata or microVMs for untrusted code.
- CPU, memory, process, disk, time and concurrency quotas.
- Network egress restrictions and cloud metadata blocking.
- Persistent private object storage and short-lived source/artifact URLs.
- Log redaction, TLS edge routing, backups, restore drills, abuse response and independent security review.

Do not execute customer code inside the public API service. Do not mount the Docker socket into the API. The current deployment queue is not a live hosting runtime.
