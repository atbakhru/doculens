# Implementation scope

The source design guide distinguishes the required local MVP from stretch infrastructure. This implementation follows that split.

| Capability | State |
|---|---|
| Upload → durable worker → thumbnails → visual search | Implemented |
| PNG/JPEG/PDF limits, signed objects, tenant checks | Implemented and covered by backend tests |
| Exact/near duplicate evidence and side-by-side review | Implemented; near matches are candidates, not guaranteed identity |
| Frozen SIFT vocabulary, spatial features, DBSCAN, noise, run history | Implemented |
| PostgreSQL + MinIO Compose stack | Implemented; Compose CI exercises real signed PUT and worker persistence |
| React responsive library, inspector, clusters, jobs, report export | Implemented; browser flows in CI |
| Small labeled evaluation and baseline comparisons | Measured in `benchmark.json`; synthetic/development-set limitations apply |
| C++ SIFT CLI | Separate parity experiment with Docker/CI harness; not the default processor |
| Kubernetes deployments, probes, resources, PDB, HPA 3–20 | Configuration provided; no observed scale-out claim |
| Public live cloud endpoint | Not provisioned; local demo is the supported presentation path |
| SQS/KEDA, Terraform EKS/RDS, pgvector/HNSW, OCR | Future work; not required for the local MVP |

CI is the authoritative record of remote container/native checks. A manifest, Dockerfile, or CI definition alone is not a passing test result. See the actual run before making a deployment or native-parity claim.
