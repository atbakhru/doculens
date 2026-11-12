from io import BytesIO
import time
import numpy as np
from PIL import Image
from sqlalchemy import select
from services.api.db import Session, Document, Page
from services.api.main import app, tenant
from services.api.storage import signature
from workers.processor.main import process_one, claim
from ml.feature_pipeline.vision import normalize, embed, phash, hamming, cluster, verify_pair
from tests.conftest import upload


def test_upload_process_search_cluster_idempotence(client, sample):
    doc, batch = upload(client, sample)
    assert client.post(f"/v1/uploads/{doc}/complete").json()["status"] == "QUEUED"
    assert process_one()
    assert not process_one()
    assert client.get(f"/v1/uploads/{doc}").json()["status"] == "COMPLETE"
    doc2, _ = upload(client, sample, "copy.png", batch=batch)
    assert process_one()
    assert client.post(f"/v1/uploads/{doc2}/complete").json()["status"] == "COMPLETE"
    pages = client.get(f"/v1/pages?batch_id={batch}").json()
    assert pages["total"] == 2
    first = pages["pages"][0]
    assert client.get(first["thumbnail_url"]).status_code == 200
    ranked = client.get(f"/v1/pages/{first['id']}/similar").json()
    assert ranked[0]["similarity"] > 0.999
    pairs = client.get(f"/v1/duplicates?batch_id={batch}").json()["pairs"]
    assert pairs[0]["kind"] == "exact"
    run = client.post("/v1/cluster-runs", json={"batch_id": batch}).json()
    assert run["cluster_count"] == 1
    assert run["noise_count"] == 0
    assert (
        client.patch(f"/v1/clusters/{run['id']}/0", json={"name": "Reviewed invoices"}).json()["names"]["0"]
        == "Reviewed invoices"
    )
    assert client.post(f"/v1/uploads/{doc}/retry").status_code == 409


def test_invalid_uploads_and_missing_objects(client, sample):
    batch = client.post("/v1/batches", json={"name": "Validation"}).json()["id"]
    body = dict(batch_id=batch, filename="x.png", mime="image/png", size=100)
    for change, expected in [
        ({"filename": "../x.png"}, 422),
        ({"mime": "text/html"}, 415),
        ({"size": 21 * 1024 * 1024}, 422),
        ({"size": 0}, 422),
    ]:
        assert client.post("/v1/uploads/presign", json={**body, **change}).status_code == expected
    ticket = client.post("/v1/uploads/presign", json=body).json()
    assert client.post(f"/v1/uploads/{ticket['id']}/complete").status_code == 422
    assert client.put(ticket["upload_url"], content=b"a" * 101).status_code == 413
    assert client.put(ticket["upload_url"], content=b"a").status_code == 422
    doc, _ = upload(client, b"not an image", batch=batch)
    process_one()
    assert client.get(f"/v1/uploads/{doc}").json()["status"] == "FAILED"
    assert client.post(f"/v1/uploads/{doc}/retry").json()["status"] == "QUEUED"


def test_pdf_success_malformed_and_page_cap(client):
    out = BytesIO()
    im = Image.new("RGB", (240, 320), "white")
    im.save(out, "PDF", save_all=True, append_images=[im])
    doc, _ = upload(client, out.getvalue(), "sample.pdf", "application/pdf")
    process_one()
    assert client.get(f"/v1/uploads/{doc}").json()["page_count"] == 2
    bad, _ = upload(client, b"%PDF-malformed", "bad.pdf", "application/pdf")
    process_one()
    assert client.get(f"/v1/uploads/{bad}").json()["status"] == "FAILED"
    out = BytesIO()
    im.save(out, "PDF", save_all=True, append_images=[im] * 30)
    too_many, _ = upload(client, out.getvalue(), "large.pdf", "application/pdf")
    process_one()
    assert client.get(f"/v1/uploads/{too_many}").json()["status"] == "FAILED"


def test_cross_tenant_and_expired_preview(client, sample):
    doc, batch = upload(client, sample)
    process_one()
    page = client.get(f"/v1/pages?batch_id={batch}").json()["pages"][0]
    run = client.post("/v1/cluster-runs", json={"batch_id": batch}).json()
    app.dependency_overrides[tenant] = lambda: "someone-else"
    for path in [
        f"/v1/uploads/{doc}",
        f"/v1/batches/{batch}",
        f"/v1/pages/{page['id']}",
        f"/v1/pages/{page['id']}/similar",
        f"/v1/duplicates?batch_id={batch}",
        f"/v1/cluster-runs/{run['id']}",
    ]:
        assert client.get(path).status_code == 404
    assert client.get("/v1/pages").json()["total"] == 0
    assert client.post(f"/v1/uploads/{doc}/retry").status_code == 404
    assert (
        client.post(
            "/v1/uploads/presign", json=dict(batch_id=batch, filename="x.png", mime="image/png", size=10)
        ).status_code
        == 404
    )
    key = "pages/test.png"
    expiry = int(time.time()) - 1
    assert (
        client.get(f"/v1/objects/{key}?expires={expiry}&token={signature(key, expiry, 'get')}").status_code
        == 403
    )
    assert client.get(page["thumbnail_url"].replace("token=", "token=bad")).status_code == 403


def test_worker_lease_reclaim_and_fencing(client, sample):
    doc, _ = upload(client, sample)
    first = claim()
    assert first and not claim()
    with Session.begin() as db:
        row = db.get(Document, doc)
        row.updated_at = time.time() - 400
    assert process_one()
    with Session() as db:
        row = db.get(Document, doc)
        assert row.status == "COMPLETE" and row.attempts == 2
        assert row.lease_token != first[1]
        assert len(db.scalars(select(Page).where(Page.document_id == doc)).all()) == 1


def test_final_attempt_crash_fails(client, sample):
    doc, _ = upload(client, sample)
    with Session.begin() as db:
        row = db.get(Document, doc)
        row.status, row.attempts, row.updated_at = "PROCESSING", 3, time.time() - 400
    assert not claim()
    assert client.get(f"/v1/uploads/{doc}").json()["status"] == "FAILED"


def test_embedding_and_geometric_evidence(sample):
    gray = normalize(sample)
    a, version = embed(gray)
    b, version2 = embed(gray)
    assert a.shape == (256,) and np.isfinite(a).all()
    assert np.isclose(np.linalg.norm(a), 1)
    assert np.array_equal(a, b) and version == version2
    assert hamming(phash(gray), phash(gray)) == 0
    rotated = np.array(Image.fromarray(gray).rotate(1.4, fillcolor=255))
    assert verify_pair(gray, rotated)["verified"]
    assert not verify_pair(np.full((100, 100), 255, np.uint8), gray)["verified"]
    assert cluster([a], min_samples=2) == [-1]


def test_demo_is_idempotent_and_cluster_waits(client):
    a = client.post("/v1/demo").json()["id"]
    b = client.post("/v1/demo").json()["id"]
    assert a == b
    assert len(client.get(f"/v1/batches/{a}").json()["documents"]) == 16
    assert client.post("/v1/cluster-runs", json={"batch_id": a}).status_code == 409


def test_transient_failure_retries(client, sample, monkeypatch):
    from workers.processor import main

    doc, _ = upload(client, sample)
    original = main.store.get
    monkeypatch.setattr(main.store, "get", lambda _: (_ for _ in ()).throw(RuntimeError("temporary")))
    process_one()
    assert client.get(f"/v1/uploads/{doc}").json()["status"] == "RETRY_WAIT"
    with Session.begin() as db:
        db.get(Document, doc).available_at = 0
    monkeypatch.setattr(main.store, "get", original)
    process_one()
    assert client.get(f"/v1/uploads/{doc}").json()["status"] == "COMPLETE"
