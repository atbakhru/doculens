# Deployment and recovery

## Local options

The Python launcher uses SQLite + files in `.data/`. The Compose stack uses PostgreSQL + MinIO. Neither requires external accounts. The API and worker must use the same database URL, storage backend, codebook artifact, and software image. SQLite is a local-development option, not a shared Kubernetes volume design.

`python -m db.migrate` applies the idempotent initial schema. The initial tables are also created on local startup for convenience; subsequent incompatible schema changes should be explicit numbered migrations. Do not run destructive schema changes on live data.

## Private hosted demo

1. Build `infra/docker/Dockerfile` for both API and worker and tag it with the Git commit SHA. Use one small container host with a private PostgreSQL database and a private S3 bucket before considering Kubernetes.
2. Set `DEMO_MODE=false`, `DATABASE_URL`, `STORAGE_BACKEND=s3`, `S3_BUCKET`, `AWS_DEFAULT_REGION`, `CORS_ORIGINS`, `API_TOKEN` (at least 24 characters), and `SIGNING_KEY` (at least 32 characters) in a managed secret/config store. Never put tokens into `VITE_*` variables. Use workload identity or IAM roles for AWS access.
3. The API needs PutObject/GetObject on its originals/sealed/previews prefixes; the worker needs GetObject on sealed inputs and PutObject/GetObject on generated pages. Keep the bucket private with Block Public Access. Scope CORS to the actual frontend origin, PUT/GET, and Content-Type. Add lifecycle cleanup for abandoned originals and old attempt outputs.
4. Run the schema migration before rolling out services. The API exposes `/healthz` and database readiness `/readyz`. Termination grace should exceed the maximum render time. Worker logs include document ID, state, page count, and duration without raw document data.
5. Serve the API through HTTPS, a rate-limiting gateway, upload quotas, and a request timeout appropriate for bounded clustering/verification. Put PDF processing in a hardened container sandbox before accepting untrusted public traffic. Authentication currently uses workspace tokens; implement OIDC/roles/audit logging before multi-user production use.
6. Import the repository into Vercel with root `apps/web`, build command `npm run build`, output `dist`, Node 22. Set only public `VITE_API_BASE_URL=https://your-api-host` and rebuild. `vercel.json` provides the SPA fallback. The static site requires the separately hosted API/worker; frontend deployment alone does not run computer vision.
7. Enter the workspace access token in the UI. Upload synthetic PNG/JPEG/PDF files; verify completion, preview authorization, similarity, duplicate evidence, and an explicit cluster run. Also test a bad token, expired upload URL, malformed PDF, and forced worker restart.

No cloud resources are created by this repository or its CI. Set a budget and choose a host before provisioning anything that incurs charges.

## Kubernetes configuration

`infra/k8s/app.yaml` and `ingress.yaml` are parameterized manifests. Replace every `REPLACE_*` value, create `doculens-secrets` through your secret manager (DATABASE_URL, API_TOKEN, SIGNING_KEY), configure workload identity for the service account, and provide TLS/Ingress. Do not apply the placeholders unchanged. The AWS workload-identity setup depends on your cluster; the included service account does not assume a particular EKS role.

The worker HPA targets 70% CPU, min 3, max 20. Install Metrics Server and ensure node capacity/autoprovisioning first. Capture `kubectl get hpa`, pod counts, queue age, actual throughput, and node capacity during a named load test before claiming observed scaling. The included workers use the database queue, not SQS. A future SQS/KEDA deployment needs an outbox, DLQ, visibility extension, and scoped roles.

## Rollback and incident handling

- Roll back API, worker, and frontend to the same known-good commit/image. Preserve the matching codebook. Schema rollback must be checked separately; the initial migration is additive.
- Queue backlog: inspect worker health, DB reachability, leases, and error logs. More CPU replicas will not solve unavailable storage or exhausted DB connections.
- Failed document: inspect the safe user-facing failure reason and worker log by document ID. Retry transient failures from Pipeline. For corrupt/unsupported bytes, upload a corrected file.
- Model change: produce a new codebook artifact and version, reprocess a controlled dataset, compare evaluation, and then migrate existing pages. Mixed versions are rejected for clustering and skipped by similarity search.
- Back up PostgreSQL and object storage together. Restoring only metadata can leave dead object references. Test restore in a separate workspace.
- Local teardown: `docker compose -f infra/docker/compose.yml down` stops services and preserves data. Volume removal is a separate destructive choice. Keep screenshots and benchmark reports before cleaning up a demo.
