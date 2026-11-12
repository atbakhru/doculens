import hashlib
import logging
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from sqlalchemy import select, update, delete, or_, and_
from services.api.db import Session, Document, Page, init_db, uid
from services.api.storage import store
from services.api.config import MAX_BYTES
from ml.feature_pipeline.vision import normalize, encode, phash, embed, vocabulary

logger = logging.getLogger("doculens.worker")
STOP = False
LEASE_SECONDS = 300


def claim():
    now = time.time()
    with Session.begin() as db:
        eligible = or_(
            and_(Document.status.in_(["QUEUED", "RETRY_WAIT"]), Document.available_at <= now),
            and_(Document.status == "PROCESSING", Document.updated_at < now - LEASE_SECONDS),
        )
        doc = db.scalar(
            select(Document).where(eligible, Document.attempts < 3).order_by(Document.created_at).limit(1)
        )
        if not doc:
            # Final-attempt workers killed mid-job must eventually reach a terminal state.
            db.execute(
                update(Document)
                .where(eligible, Document.attempts >= 3)
                .values(status="FAILED", error="Worker lease expired after 3 attempts")
            )
            return None
        token = uid()
        result = db.execute(
            update(Document)
            .where(Document.id == doc.id, eligible, Document.attempts == doc.attempts)
            .values(
                status="PROCESSING",
                attempts=Document.attempts + 1,
                updated_at=now,
                lease_token=token,
                error=None,
            )
        )
        return (doc.id, token) if result.rowcount == 1 else None


def images(data, mime):
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds 20 MB")
    if mime == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("File is not a valid PDF")
        with tempfile.TemporaryDirectory(prefix="doculens-") as tmp:
            src = Path(tmp) / "source.pdf"
            src.write_bytes(data)
            try:
                subprocess.run(
                    [sys.executable, "-m", "ml.feature_pipeline.render", str(src), tmp],
                    check=True,
                    capture_output=True,
                    timeout=90,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError(
                    "PDF cannot be rendered: malformed, encrypted, over 30 pages, or time limit exceeded"
                ) from exc
            for path in sorted(Path(tmp).glob("*.png")):
                page = path.read_bytes()
                yield normalize(page), hashlib.sha256(page).hexdigest()
    else:
        if mime == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("File content does not match PNG")
        if mime == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("File content does not match JPEG")
        yield normalize(data), hashlib.sha256(data).hexdigest()


def process_one():
    job = claim()
    if not job:
        return False
    doc_id, token = job
    try:
        with Session() as db:
            doc = db.get(Document, doc_id)
            data = store.get(doc.object_key)
            mime = doc.mime
        pages = []
        started = time.perf_counter()
        for number, (gray, sha) in enumerate(images(data, mime), 1):
            vector, version = embed(gray)
            # Attempt-specific keys keep stale workers from overwriting current output.
            prefix = f"pages/{doc_id}/{token}/{number}"
            store.put(prefix + ".png", encode(gray), "image/png")
            store.put(prefix + "-thumb.png", encode(gray, True), "image/png")
            pages.append(
                Page(
                    document_id=doc_id,
                    page_no=number,
                    width=gray.shape[1],
                    height=gray.shape[0],
                    image_key=prefix + ".png",
                    thumbnail_key=prefix + "-thumb.png",
                    sha256=sha,
                    phash=phash(gray),
                    model_version=version,
                    embedding=vector.tolist(),
                    duration_ms=(time.perf_counter() - started) * 1000 / number,
                )
            )
            with Session.begin() as db:
                result = db.execute(
                    update(Document)
                    .where(Document.id == doc_id, Document.lease_token == token)
                    .values(updated_at=time.time(), processed_pages=number)
                )
                if result.rowcount != 1:
                    return True
        with Session.begin() as db:
            result = db.execute(
                update(Document)
                .where(Document.id == doc_id, Document.lease_token == token)
                .values(
                    status="COMPLETE",
                    page_count=len(pages),
                    processed_pages=len(pages),
                    updated_at=time.time(),
                    error=None,
                )
            )
            if result.rowcount == 1:
                db.execute(delete(Page).where(Page.document_id == doc_id))
                db.add_all(pages)
        logger.info(
            "document_complete id=%s pages=%s elapsed_seconds=%.3f",
            doc_id,
            len(pages),
            time.perf_counter() - started,
        )
    except Exception as exc:
        logger.exception("document_failed id=%s", doc_id)
        with Session.begin() as db:
            doc = db.get(Document, doc_id)
            if doc and doc.lease_token == token:
                permanent = isinstance(exc, (ValueError, OSError)) and not isinstance(exc, ConnectionError)
                doc.status = "FAILED" if permanent or doc.attempts >= 3 else "RETRY_WAIT"
                doc.error = (
                    str(exc)[:250]
                    if isinstance(exc, ValueError)
                    else "Processing failed; inspect worker logs or retry"
                )
                doc.available_at = time.time() + 2**doc.attempts
                doc.updated_at = time.time()
    return True


def stop(*_):
    global STOP
    STOP = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    vocabulary()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not STOP:
        Path(".data").mkdir(exist_ok=True)
        Path(".data/worker-heartbeat").touch()
        if not process_one():
            time.sleep(0.75)
