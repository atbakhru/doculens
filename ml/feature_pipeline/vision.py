"""Versioned SIFT visual words + spatial ink layout, never semantic classification."""

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import hashlib
import warnings
import cv2
import numpy as np
from PIL import Image, ImageOps
from sklearn.cluster import MiniBatchKMeans, DBSCAN
from services.api.config import MAX_PIXELS, MODEL_VERSION

cv2.setNumThreads(1)
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)


def normalize(data: bytes):
    with Image.open(BytesIO(data)) as image:
        if image.format not in ("PNG", "JPEG"):
            raise ValueError("Only actual PNG and JPEG images are supported")
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Image exceeds 24 megapixels")
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, "white")
            image = Image.alpha_composite(bg, rgba)
        image = image.convert("L")
        image.thumbnail((1200, 1200))
        return np.array(image)


def encode(gray, thumbnail=False):
    im = Image.fromarray(gray)
    if thumbnail:
        im.thumbnail((300, 400))
    out = BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def phash(gray):
    resized = cv2.resize(gray, (32, 32)).astype(np.float32)
    low = cv2.dct(resized)[:8, :8].flatten()
    bits = low > np.median(low[1:])
    bits[0] = False
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def hamming(a, b):
    return (int(a, 16) ^ int(b, 16)).bit_count()


def sift(gray):
    return cv2.SIFT_create(nfeatures=600).detectAndCompute(gray, None)


@lru_cache(maxsize=1)
def vocabulary():
    artifact = Path(__file__).with_name("codebook.npz")
    if artifact.exists():
        with np.load(artifact, allow_pickle=False) as saved:
            centers = saved["centers"].astype(np.float32)
        if centers.shape != (128, 128) or not np.isfinite(centers).all():
            raise ValueError("Invalid visual vocabulary artifact")
        digest = hashlib.sha256(centers.tobytes()).hexdigest()[:12]
        return centers, f"{MODEL_VERSION}-{digest}"
    return train_vocabulary()


def train_vocabulary():
    # Train only on a separate synthetic split; evaluation uses seed=42.
    from scripts.fixtures import document, png

    desc = []
    for layout in range(3):
        for variant in range(4):
            _, des = sift(normalize(png(document(layout, variant, seed=713))))
            if des is not None:
                desc.append(des)
    model = MiniBatchKMeans(n_clusters=128, random_state=17, n_init=3, batch_size=512)
    model.fit(np.vstack(desc))
    centers = model.cluster_centers_.astype(np.float32)
    digest = hashlib.sha256(centers.tobytes()).hexdigest()[:12]
    return centers, f"{MODEL_VERSION}-{digest}"


def embed(gray):
    centers, version = vocabulary()
    _, descriptors = sift(gray)
    hist = np.zeros(128, dtype=np.float32)
    if descriptors is not None:
        matches = cv2.BFMatcher(cv2.NORM_L2).match(descriptors, centers)
        hist = np.bincount([m.trainIdx for m in matches], minlength=128).astype(np.float32)
        hist = np.sqrt(hist / max(hist.sum(), 1))
    # A 8x16 spatial ink map retains layout information discarded by a bag of words.
    layout = cv2.resize(1 - gray.astype(np.float32) / 255, (8, 16), interpolation=cv2.INTER_AREA).ravel()
    layout /= max(float(np.linalg.norm(layout)), 1e-8)
    vector = np.concatenate([hist * 0.35, layout * 0.9367497])
    vector /= max(float(np.linalg.norm(vector)), 1e-8)
    return vector, version


def verify_pair(a, b):
    ka, da = sift(a)
    kb, db = sift(b)
    if da is None or db is None or min(len(da), len(db)) < 4:
        return dict(verified=False, matches=0, inliers=0, inlier_ratio=0.0)
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.7 * pair[1].distance]
    if len(good) < 8:
        return dict(verified=False, matches=len(good), inliers=0, inlier_ratio=0.0)
    src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    cv2.setRNGSeed(17)
    homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    inliers = int(mask.sum()) if mask is not None else 0
    ratio = inliers / len(good)
    ink_error = 1.0
    if homography is not None and inliers >= 12:
        # Refine subpixel alignment before checking content; RANSAC keypoints alone
        # can leave a one-pixel drift that looks like changed text.
        try:
            _, inverse = cv2.findTransformECC(
                b.astype(np.float32) / 255,
                a.astype(np.float32) / 255,
                np.linalg.inv(homography).astype(np.float32),
                cv2.MOTION_HOMOGRAPHY,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 1e-5),
                None,
                5,
            )
            homography = np.linalg.inv(inverse)
        except (cv2.error, np.linalg.LinAlgError):
            pass
        warped = cv2.warpPerspective(a, homography, (b.shape[1], b.shape[0]), borderValue=255)
        valid = (
            cv2.warpPerspective(np.full(a.shape, 255, np.uint8), homography, (b.shape[1], b.shape[0])) > 250
        )
        ink_a, ink_b = (warped < 160) & valid, (b < 160) & valid
        kernel = np.ones((3, 3), np.uint8)
        near_a = cv2.dilate(ink_a.astype(np.uint8), kernel) > 0
        near_b = cv2.dilate(ink_b.astype(np.uint8), kernel) > 0
        mismatch = np.count_nonzero(ink_a & ~near_b) + np.count_nonzero(ink_b & ~near_a)
        ink_error = mismatch / max(1, np.count_nonzero(ink_a) + np.count_nonzero(ink_b))
    # Alignment-aware ink consistency rejects some shared-template false positives.
    return dict(
        verified=homography is not None and inliers >= 12 and ratio >= 0.65 and ink_error < 0.0018,
        matches=len(good),
        inliers=inliers,
        inlier_ratio=round(ratio, 4),
        ink_error=round(ink_error, 5),
    )


def cluster(vectors, eps=0.11, min_samples=2):
    if not len(vectors):
        return []
    return DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit_predict(np.asarray(vectors)).tolist()
