"""Compare native/Python wrappers against the SAME system OpenCV in this container."""

import json
import subprocess
import tempfile
import time
from pathlib import Path
import cv2
import numpy as np

cv2.setNumThreads(1)
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    rng = np.random.default_rng(17)
    im = np.full((960, 720), 255, np.uint8)
    for i in range(40):
        x, y = rng.integers(20, 620), rng.integers(20, 880)
        cv2.putText(im, f"Sample {i}", (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
    src, dest = root / "page.png", root / "result.yml"
    cv2.imwrite(str(src), im)
    subprocess.run(["build/doculens-extract", str(src), str(dest)], check=True)
    fs = cv2.FileStorage(str(dest), cv2.FILE_STORAGE_READ)
    native = fs.getNode("descriptors").mat()
    native_ms = fs.getNode("duration_ms").real()
    version = fs.getNode("opencv_version").string()
    fs.release()
    start = time.perf_counter()
    _, python = cv2.SIFT_create(600).detectAndCompute(im, None)
    python_ms = (time.perf_counter() - start) * 1000
    assert version == cv2.__version__, (version, cv2.__version__)
    assert native.shape == python.shape
    np.testing.assert_allclose(native, python, atol=1e-5)
    print(
        json.dumps(
            dict(
                opencv=version,
                parity=True,
                native_ms=native_ms,
                python_ms=python_ms,
                note="Single warmup-sensitive sample. No speedup claim. Python OpenCV already runs native C++.",
            )
        )
    )
