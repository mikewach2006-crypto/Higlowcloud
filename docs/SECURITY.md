# Security status

This is an early MVP, not a production hosting platform.

Before public workloads are accepted, implement authentication, organization membership and tenant-scoped queries; encrypted secrets; signed and replay-protected worker jobs; isolated builds and runtimes; non-root containers; CPU, memory and disk quotas; network egress controls; archive expansion limits; log redaction; audit trails; backups; abuse response and security testing.

Do not run customer code in the API service and do not mount the Docker socket into it.
