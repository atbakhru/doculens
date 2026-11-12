from contextlib import asynccontextmanager
from functools import lru_cache
import hashlib
import json
import os
import secrets
import time
from typing import Annotated
import numpy as np
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session as DBSession
from services.api.config import API_TOKEN, DEMO_MODE, MAX_BYTES, MAX_CLUSTER_PAGES, MODEL_VERSION, STORAGE
from services.api.db import Batch, Document, Page, ClusterRun, session, init_db, uid
from services.api.storage import store, valid_signature
from ml.feature_pipeline.vision import hamming, normalize, verify_pair, cluster


@asynccontextmanager
async def lifespan(_):
    init_db()
    yield


app = FastAPI(
    title="DocuLens",
    version="1.0.0",
    lifespan=lifespan,
    description="Visual document organization. Layout similarity is not semantic classification.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)


def tenant(authorization: str | None = Header(default=None)):
    if DEMO_MODE and not API_TOKEN:
        return "demo"
    token = (authorization or "").removeprefix("Bearer ")
    tokens = json.loads(os.getenv("API_TOKENS", "{}"))
    if API_TOKEN:
        tokens[API_TOKEN] = "workspace"
    for key, org in tokens.items():
        if secrets.compare_digest(token, key):
            return org
    raise HTTPException(401, "Enter a valid workspace access token")


DB = Annotated[DBSession, Depends(session)]
Org = Annotated[str, Depends(tenant)]


def get_batch(db, batch_id, org):
    batch = db.scalar(select(Batch).where(Batch.id == batch_id, Batch.tenant == org))
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


def get_doc(db, doc_id, org):
    doc = db.scalar(select(Document).join(Batch).where(Document.id == doc_id, Batch.tenant == org))
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


def get_page(db, page_id, org):
    page = db.scalar(select(Page).join(Document).join(Batch).where(Page.id == page_id, Batch.tenant == org))
    if not page:
        raise HTTPException(404, "Page not found")
    return page


def page_json(page, doc):
    return dict(
        id=page.id,
        document_id=doc.id,
        batch_id=doc.batch_id,
        filename=doc.filename,
        page_no=page.page_no,
        width=page.width,
        height=page.height,
        sha256=page.sha256,
        phash=page.phash,
        thumbnail_url=store.image_url(page.thumbnail_key),
        image_url=store.image_url(page.image_key),
        model_version=page.model_version,
        duration_ms=round(page.duration_ms, 1),
    )


def doc_json(doc):
    return {
        k: getattr(doc, k)
        for k in (
            "id",
            "batch_id",
            "filename",
            "mime",
            "size",
            "status",
            "attempts",
            "error",
            "page_count",
            "processed_pages",
            "created_at",
        )
    }


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get("/readyz")
def ready(db: DB):
    db.execute(select(1))
    return {"status": "ready"}


@app.get("/v1/config")
def config():
    return dict(
        demo=DEMO_MODE,
        auth_required=bool(API_TOKEN) or not DEMO_MODE,
        max_bytes=MAX_BYTES,
        max_pages=30,
        max_cluster_pages=MAX_CLUSTER_PAGES,
        model=MODEL_VERSION,
        storage=STORAGE,
    )


class BatchInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)


@app.post("/v1/batches", status_code=201)
def create_batch(body: BatchInput, db: DB, org: Org):
    b = Batch(name=body.name, tenant=org)
    db.add(b)
    db.commit()
    return dict(id=b.id, name=b.name)


@app.get("/v1/batches")
def batches(db: DB, org: Org, offset: int = 0):
    rows = db.scalars(
        select(Batch)
        .where(Batch.tenant == org)
        .order_by(Batch.created_at.desc())
        .offset(max(0, offset))
        .limit(100)
    ).all()
    return [dict(id=b.id, name=b.name, created_at=b.created_at) for b in rows]


@app.get("/v1/batches/{batch_id}")
def batch_details(batch_id: str, db: DB, org: Org):
    b = get_batch(db, batch_id, org)
    docs = db.scalars(select(Document).where(Document.batch_id == b.id).order_by(Document.created_at)).all()
    return dict(id=b.id, name=b.name, documents=[doc_json(d) for d in docs])


class UploadInput(BaseModel):
    batch_id: str
    filename: str = Field(min_length=1, max_length=200)
    mime: str
    size: int = Field(gt=0, le=MAX_BYTES)


@app.post("/v1/uploads/presign", status_code=201)
def presign(body: UploadInput, db: DB, org: Org):
    get_batch(db, body.batch_id, org)
    if body.mime not in ("image/png", "image/jpeg", "application/pdf"):
        raise HTTPException(415, "Use PNG, JPEG, or PDF")
    if any(c in body.filename for c in ("/", "\\", "\x00")):
        raise HTTPException(422, "Filename must not contain a path")
    count = db.scalar(select(func.count()).select_from(Document).where(Document.batch_id == body.batch_id))
    if count >= 100:
        raise HTTPException(409, "A batch supports at most 100 files")
    doc_id = uid()
    doc = Document(id=doc_id, **body.model_dump(), object_key=f"originals/{org}/{doc_id}")
    db.add(doc)
    db.commit()
    return dict(id=doc.id, upload_url=store.upload_url(doc.object_key, doc.mime), expires_in=300)


@app.put("/v1/objects/{key:path}")
async def put_object(key: str, request: Request, expires: int, token: str, db: DB):
    if STORAGE != "local" or not valid_signature(key, expires, "put", token):
        raise HTTPException(403, "Upload link expired or invalid")
    # Lock prevents a concurrent complete request from racing this write on Postgres.
    doc = db.scalar(select(Document).where(Document.object_key == key).with_for_update())
    if not doc or doc.status != "PENDING_UPLOAD":
        raise HTTPException(409, "Upload has already been finalized")
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > min(MAX_BYTES, doc.size):
            raise HTTPException(413, "Upload exceeds reserved size")
    if len(chunks) != doc.size:
        raise HTTPException(422, "Uploaded size does not match reservation")
    store.put(key, bytes(chunks), doc.mime)
    db.commit()
    return {"stored": True}


@app.get("/v1/objects/{key:path}")
def read_object(key: str, expires: int, token: str):
    if STORAGE != "local" or not valid_signature(key, expires, "get", token):
        raise HTTPException(403, "Preview link expired or invalid")
    try:
        return Response(
            store.get(key),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"},
        )
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Preview not found")


@app.post("/v1/uploads/{doc_id}/complete")
def complete(doc_id: str, db: DB, org: Org):
    doc = get_doc(db, doc_id, org)
    if doc.status != "PENDING_UPLOAD":
        return doc_json(doc)
    try:
        data = store.get(doc.object_key)
    except Exception:
        raise HTTPException(422, "Upload missing or too large; upload the file again")
    if len(data) != doc.size:
        raise HTTPException(422, "Object size does not match reservation")
    # Snapshot upload into a private immutable processing key. A reusable S3 PUT URL
    # can no longer change the bytes workers process after completion.
    digest = hashlib.sha256(data).hexdigest()
    key = f"sealed/{org}/{doc.id}/{digest}"
    store.put(key, data, doc.mime)
    db.execute(
        update(Document)
        .where(Document.id == doc_id, Document.status == "PENDING_UPLOAD")
        .values(object_key=key, sha256=digest, status="QUEUED", updated_at=time.time())
    )
    db.commit()
    db.refresh(doc)
    return doc_json(doc)


@app.get("/v1/uploads/{doc_id}")
def upload_status(doc_id: str, db: DB, org: Org):
    return doc_json(get_doc(db, doc_id, org))


@app.post("/v1/uploads/{doc_id}/retry")
def retry(doc_id: str, db: DB, org: Org):
    doc = get_doc(db, doc_id, org)
    if doc.status != "FAILED":
        raise HTTPException(409, "Only failed jobs can be retried")
    doc.status, doc.error, doc.attempts, doc.available_at = "QUEUED", None, 0, 0
    db.commit()
    return doc_json(doc)


@app.get("/v1/pages")
def pages(db: DB, org: Org, batch_id: str | None = None, offset: int = 0, limit: int = 60, q: str = ""):
    query = select(Page, Document).join(Document).join(Batch).where(Batch.tenant == org)
    if batch_id:
        get_batch(db, batch_id, org)
        query = query.where(Batch.id == batch_id)
    if q:
        query = query.where(Document.filename.ilike(f"%{q[:100]}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Document.created_at, Page.page_no)
        .offset(max(0, offset))
        .limit(min(max(limit, 1), 100))
    ).all()
    return dict(total=total, pages=[page_json(p, d) for p, d in rows])


@app.get("/v1/pages/{page_id}")
def page_details(page_id: str, db: DB, org: Org):
    p = get_page(db, page_id, org)
    return page_json(p, db.get(Document, p.document_id))


@app.get("/v1/pages/{page_id}/similar")
def similar(page_id: str, db: DB, org: Org):
    p = get_page(db, page_id, org)
    query = (
        select(Page, Document)
        .join(Document)
        .join(Batch)
        .where(Batch.tenant == org, Page.id != page_id, Page.model_version == p.model_version)
    )
    # Deliberate exact-search cap; pgvector is a future scaling path.
    if db.scalar(select(func.count()).select_from(query.subquery())) > 5000:
        raise HTTPException(409, "Exact search is limited to 5,000 pages per workspace")
    ranked = []
    a = np.asarray(p.embedding)
    for candidate, doc in db.execute(query):
        score = float(np.clip(np.dot(a, candidate.embedding), 0, 1))
        ranked.append(dict(**page_json(candidate, doc), similarity=round(score, 4)))
    return sorted(ranked, key=lambda item: item["similarity"], reverse=True)[:12]


@lru_cache(maxsize=1024)
def geometry(key_a, key_b):
    return verify_pair(normalize(store.get(key_a)), normalize(store.get(key_b)))


@app.get("/v1/duplicates")
def duplicates(batch_id: str, db: DB, org: Org):
    get_batch(db, batch_id, org)
    rows = db.execute(
        select(Page, Document)
        .join(Document)
        .where(Document.batch_id == batch_id)
        .order_by(Page.id)
        .limit(MAX_CLUSTER_PAGES + 1)
    ).all()
    if len(rows) > MAX_CLUSTER_PAGES:
        raise HTTPException(409, "Duplicate review is capped at 500 pages per batch")
    results = []
    candidates = 0
    for i, (a, da) in enumerate(rows):
        for b, dbb in rows[i + 1 :]:
            exact = a.sha256 == b.sha256
            distance = hamming(a.phash, b.phash)
            layout_similarity = (
                float(np.dot(a.embedding, b.embedding)) if a.model_version == b.model_version else 0
            )
            if not exact and distance > 14 and layout_similarity < 0.94:
                continue
            candidates += 1
            if candidates > 1000:
                raise HTTPException(409, "Too many candidate pairs; split this batch into smaller batches")
            evidence = (
                dict(verified=True, inlier_ratio=1.0, matches=0, inliers=0)
                if exact
                else geometry(a.image_key, b.image_key)
            )
            if exact or evidence["verified"]:
                results.append(
                    dict(
                        id=f"{a.id}:{b.id}",
                        kind="exact" if exact else "near",
                        left=page_json(a, da),
                        right=page_json(b, dbb),
                        hash_distance=distance,
                        **evidence,
                    )
                )
    return dict(pairs=results, screened_pairs=len(rows) * (len(rows) - 1) // 2, candidate_pairs=candidates)


class ClusterInput(BaseModel):
    batch_id: str
    eps: float = Field(default=0.11, gt=0, le=1)
    min_samples: int = Field(default=2, ge=2, le=20)


@app.post("/v1/cluster-runs", status_code=201)
def cluster_run(body: ClusterInput, db: DB, org: Org):
    get_batch(db, body.batch_id, org)
    pending = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.batch_id == body.batch_id, Document.status.not_in(["COMPLETE", "FAILED"]))
    )
    if pending:
        raise HTTPException(409, "Wait for this batch to finish processing")
    rows = db.scalars(
        select(Page)
        .join(Document)
        .where(Document.batch_id == body.batch_id)
        .order_by(Page.id)
        .limit(MAX_CLUSTER_PAGES + 1)
    ).all()
    if not rows or len(rows) > MAX_CLUSTER_PAGES:
        raise HTTPException(409, "Clustering requires 1-500 processed pages")
    versions = {p.model_version for p in rows}
    if len(versions) != 1:
        raise HTTPException(409, "Reprocess pages with one shared feature model version")
    labels = cluster([p.embedding for p in rows], body.eps, body.min_samples)
    run = ClusterRun(
        **body.model_dump(),
        model_version=versions.pop(),
        members={p.id: label for p, label in zip(rows, labels)},
    )
    db.add(run)
    db.commit()
    return run_json(run)


def run_json(run):
    labels = list(run.members.values())
    return dict(
        id=run.id,
        batch_id=run.batch_id,
        status=run.status,
        eps=run.eps,
        min_samples=run.min_samples,
        model_version=run.model_version,
        members=run.members,
        names=run.names,
        created_at=run.created_at,
        cluster_count=len(set(labels) - {-1}),
        noise_count=labels.count(-1),
    )


@app.get("/v1/cluster-runs")
def runs(batch_id: str, db: DB, org: Org):
    get_batch(db, batch_id, org)
    return [
        run_json(r)
        for r in db.scalars(
            select(ClusterRun)
            .where(ClusterRun.batch_id == batch_id)
            .order_by(ClusterRun.created_at.desc())
            .limit(30)
        )
    ]


@app.get("/v1/cluster-runs/{run_id}")
def run_details(run_id: str, db: DB, org: Org):
    run = db.get(ClusterRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    get_batch(db, run.batch_id, org)
    return run_json(run)


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.patch("/v1/clusters/{run_id}/{label}")
def rename(run_id: str, label: int, body: Rename, db: DB, org: Org):
    run_details(run_id, db, org)
    run = db.get(ClusterRun, run_id)
    if label not in run.members.values():
        raise HTTPException(404, "Cluster not found")
    run.names = {**run.names, str(label): body.name}
    db.commit()
    return run_json(run)


@app.post("/v1/demo", status_code=201)
def demo(db: DB, org: Org):
    if not DEMO_MODE:
        raise HTTPException(403, "Demo seeding is disabled")
    from scripts.fixtures import corpus

    existing = db.scalar(select(Batch).where(Batch.tenant == org, Batch.name == "The sample collection"))
    if existing:
        return {"id": existing.id}
    batch = Batch(name="The sample collection", tenant=org)
    db.add(batch)
    db.flush()
    for name, data, _, _ in corpus():
        doc_id = uid()
        key = f"sealed/{org}/{doc_id}"
        store.put(key, data, "image/png")
        db.add(
            Document(
                id=doc_id,
                batch_id=batch.id,
                filename=name,
                mime="image/png",
                size=len(data),
                object_key=key,
                sha256=hashlib.sha256(data).hexdigest(),
                status="QUEUED",
            )
        )
    db.commit()
    return {"id": batch.id}


@app.get("/v1/metrics")
def metrics(db: DB, org: Org):
    docs = db.scalars(select(Document).join(Batch).where(Batch.tenant == org)).all()
    pages_count = db.scalar(
        select(func.count()).select_from(Page).join(Document).join(Batch).where(Batch.tenant == org)
    )
    return dict(
        documents=len(docs),
        pages=pages_count,
        complete=sum(d.status == "COMPLETE" for d in docs),
        failed=sum(d.status == "FAILED" for d in docs),
        queued=sum(d.status in ("QUEUED", "RETRY_WAIT", "PROCESSING") for d in docs),
        model=MODEL_VERSION,
        queue="Database leases",
        storage=STORAGE,
    )
