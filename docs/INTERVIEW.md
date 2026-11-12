# A five-minute DocuLens walkthrough

## Before the call

Start `python scripts/dev.py`, open the local UI, and load **The sample collection**. Wait for all 16 documents to complete, then run layout clustering. Keep this warmed workspace open. Open the repository's README, architecture, and benchmark JSON in other tabs. The sample data is generated, and fonts/codebook are bundled, so the demo does not need a cloud service after installation.

## 0:00 — The problem

“Teams collect repeated scans and forms with similar structure. I built a visual organizer that preserves originals and helps a reviewer see likely duplicates and shared layouts. It doesn't pretend layout similarity is semantic document understanding.”

Show the library. Open a page and point out its source page, model version, hash, and visually similar results.

## 1:00 — Follow real data

Upload two copies of a generated fixture from `.data/fixtures` (create fixtures with `python -m scripts.fixtures`). Show Pipeline and its progression to COMPLETE. Explain that the browser receives a signed URL, storage receives bytes, completion seals an immutable snapshot, and a separate worker claims a durable job. Refresh the browser to demonstrate persistence.

## 2:00 — Explain the interesting computer vision

Open Duplicates. Compare an exact copy with a near-match candidate. Explain the cost cascade: SHA-256 → pHash/layout screening → SIFT ratio test → RANSAC → alignment/content check. Point out that geometric agreement is evidence, not a probability. Show a false positive if the evaluation reports one; preserving human judgment is an intentional product decision.

## 3:00 — Unsupervised organization

Choose the sample batch, open Layout clusters, and create a run. The corpus contains three template families. Explain why SIFT needs aggregation: a variable number of local descriptors becomes 128 visual-word bins; 128 spatial features preserve layout. Rename a group. Reduce eps to show how cluster density and noise can change. Every run is preserved with parameters and a codebook digest.

## 4:00 — Reliability and tradeoffs

Show tests and `docs/benchmark.json`. The suite covers invalid files, tenant boundaries, expired links, duplicate completion, worker lease recovery, and transient retries. To demonstrate a failure, upload a text file renamed to `.png`: the server rejects the actual bytes and the Pipeline explains the failure. Retry cannot make malformed bytes valid; upload a corrected file instead.

Explain that database leases give a cheap reproducible MVP; SQS/outbox, pgvector, and queue-aware scaling are extensions. Show the HPA YAML as configuration, not an observed scaling result.

## Questions worth preparing for

| Interviewer asks | Answer to understand |
|---|---|
| Why not OCR or a large model? | The problem is visual organization; layout is useful without semantic extraction. OCR would be a separately evaluated pipeline. |
| Why not use raw SIFT as an embedding? | Every image has a different number of descriptors. Quantization and aggregation produce a fixed representation. |
| Why can duplicate detection be wrong? | A shared template yields many matching features even when critical fields differ. Alignment and ink checks help; review remains necessary. |
| What happens if a worker dies? | The lease expires, another worker claims it, and a new token fences the old worker. Final page writes and state commit atomically. |
| What if a signed upload URL is reused? | Completion copies the accepted bytes to an immutable private processing key; reusing the original PUT cannot change queued input. |
| What is the first scaling bottleneck? | Measure it. Candidate-pair verification is expensive, clustering can use quadratic memory, exact search scans vectors, and pollers contend on the database. |
| Did C++ make it faster? | No speedup is claimed. Python OpenCV already uses native C++; the separate CLI is an explicit parity experiment. |
| Is three clusters proof of accuracy? | No. It is a small, known synthetic corpus; templates and thresholds are not independent of development. More varied labeled scans are the next evaluation step. |

## Resume wording you can defend

“Built a document organization application with React, FastAPI, and OpenCV, combining signed uploads, recoverable worker jobs, visual duplicate review, and versioned DBSCAN layout clustering; added automated tests and a reproducible synthetic evaluation.”

Mention PostgreSQL/MinIO after running the container smoke test. Mention native parity after the native CI job passes. Do not add a throughput figure without naming the benchmark and exclusions. Do not say “scaled to 20 replicas” unless you actually run and record that experiment.
