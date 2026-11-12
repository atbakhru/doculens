import os
import tempfile
from pathlib import Path
import pytest

_tmp = tempfile.TemporaryDirectory(prefix="doculens-tests-")
os.environ["DATA_DIR"] = _tmp.name
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "test.db")
os.environ["DEMO_MODE"] = "true"
os.environ["STORAGE_BACKEND"] = "local"
os.environ.pop("API_TOKEN", None)

from services.api.db import Base, engine, init_db  # noqa: E402
from services.api.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    init_db()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample():
    from scripts.fixtures import document, png

    return png(document(0, 0))


def upload(client, data, filename="invoice.png", mime="image/png", batch=None):
    batch = batch or client.post("/v1/batches", json={"name": "Test collection"}).json()["id"]
    ticket = client.post(
        "/v1/uploads/presign", json={"batch_id": batch, "filename": filename, "mime": mime, "size": len(data)}
    )
    assert ticket.status_code == 201, ticket.text
    ticket = ticket.json()
    response = client.put(ticket["upload_url"], content=data)
    assert response.status_code == 200, response.text
    response = client.post(f"/v1/uploads/{ticket['id']}/complete")
    assert response.status_code == 200, response.text
    return ticket["id"], batch
