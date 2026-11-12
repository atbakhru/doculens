"""Real HTTP smoke test: presign -> object PUT -> finalize -> worker -> search -> cluster."""

import base64
import time
import httpx

# Tiny valid PNG, suitable for storage/worker plumbing (not clustering quality).
png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jT1kAAAAASUVORK5CYII="
)
with httpx.Client(base_url="http://localhost:8000", timeout=120) as client:
    batch = client.post("/v1/batches", json={"name": "CI smoke"})
    batch.raise_for_status()
    batch = batch.json()["id"]
    for name in ["smoke.png", "copy.png"]:
        ticket = client.post(
            "/v1/uploads/presign", json=dict(batch_id=batch, filename=name, mime="image/png", size=len(png))
        )
        ticket.raise_for_status()
        ticket = ticket.json()
        response = client.put(ticket["upload_url"], content=png, headers={"Content-Type": "image/png"})
        response.raise_for_status()
        client.post(f"/v1/uploads/{ticket['id']}/complete").raise_for_status()
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        docs = client.get(f"/v1/batches/{batch}").json()["documents"]
        if any(d["status"] == "FAILED" for d in docs):
            raise RuntimeError(docs)
        if all(d["status"] == "COMPLETE" for d in docs):
            break
        time.sleep(1)
    else:
        raise TimeoutError("Worker did not finish in 180s")
    pages = client.get(f"/v1/pages?batch_id={batch}").json()["pages"]
    assert len(pages) == 2
    client.get(pages[0]["thumbnail_url"]).raise_for_status()
    client.get(f"/v1/pages/{pages[0]['id']}/similar").raise_for_status()
    response = client.post("/v1/cluster-runs", json={"batch_id": batch})
    response.raise_for_status()
    assert client.get(f"/v1/duplicates?batch_id={batch}").json()["pairs"][0]["kind"] == "exact"
    print("PASS: signed upload, object storage, worker, thumbnail, similarity, clustering, exact duplicate")
