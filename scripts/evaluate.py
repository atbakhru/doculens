"""Small held-out synthetic evaluation; no production accuracy/throughput claims."""

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
import cv2
import numpy as np
from sklearn.metrics import homogeneity_score, adjusted_rand_score
from scripts.fixtures import corpus
from ml.feature_pipeline.vision import normalize, embed, vocabulary, phash, hamming, verify_pair, cluster


def evaluate():
    samples = corpus(seed=42)
    vocabulary()  # training warmup excluded and disclosed
    start = time.perf_counter()
    gray = [normalize(data) for _, data, _, _ in samples]
    vectors = [embed(im)[0] for im in gray]
    elapsed = time.perf_counter() - start
    hashes = [phash(im) for im in gray]
    digests = [hashlib.sha256(s[1]).hexdigest() for s in samples]
    counts = {
        method: dict(tp=0, fp=0, fn=0, tn=0)
        for method in ["sha256", "phash", "full_candidate_geometry_ink_pipeline"]
    }
    false_positives = []
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            truth = samples[i][3] == samples[j][3]
            exact = digests[i] == digests[j]
            candidate = hamming(hashes[i], hashes[j]) <= 14
            recall_gate = candidate or float(np.dot(vectors[i], vectors[j])) >= 0.94
            verified = exact or (recall_gate and verify_pair(gray[i], gray[j])["verified"])
            for method, predicted in zip(counts, [exact, candidate, verified]):
                counts[method][
                    "tp" if truth and predicted else "fp" if predicted else "fn" if truth else "tn"
                ] += 1
            if verified and not truth:
                false_positives.append([samples[i][0], samples[j][0]])
    for count in counts.values():
        count["precision"] = count["tp"] / max(1, count["tp"] + count["fp"])
        count["recall"] = count["tp"] / max(1, count["tp"] + count["fn"])
    labels = cluster(vectors)
    return dict(
        corpus="synthetic-v1-eval-seed42",
        training="synthetic-v1-seed713 (separate split)",
        pages=len(samples),
        resolution="720x960",
        model=vocabulary()[1],
        vector_dimension=256,
        duplicate_detection=counts,
        false_positive_examples=false_positives[:10],
        clustering=dict(
            eps=0.11,
            min_samples=2,
            clusters=len(set(labels) - {-1}),
            noise=labels.count(-1),
            homogeneity=homogeneity_score([s[2] for s in samples], labels),
            adjusted_rand=adjusted_rand_score([s[2] for s in samples], labels),
            labels=labels,
        ),
        feature_benchmark=dict(
            seconds=elapsed,
            pages_per_second=len(samples) / elapsed,
            workers=1,
            warmup_excluded=True,
            includes="decode, normalize, SIFT, BoVW, layout embedding",
            excludes="training, PDF rendering, upload, persistence, duplicate verification",
        ),
        environment=dict(
            python=platform.python_version(),
            platform=platform.platform(),
            processor=platform.processor(),
            opencv=cv2.__version__,
            numpy=np.__version__,
        ),
        limitations=[
            "Tiny synthetic corpus; not representative of real-world scans.",
            "Shared templates produce near-duplicate false positives; human review required.",
            "No observed Kubernetes scaling or end-to-end throughput claim.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/benchmark.json")
    args = parser.parse_args()
    result = evaluate()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
