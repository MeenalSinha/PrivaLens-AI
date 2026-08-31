"""
Tests for two real gaps found during audit: there was no way to
actually download a dataset (rescued or otherwise) as a file, and no
endpoint that assembled a rescue job's state into an actual report
document.
"""
import asyncio

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import init_db, new_id, save_dataset_record
from app.rescue.job_store import init_rescue_db, create_job
from app.rescue.orchestrator import DataRescueAgent, approval_registry
from app.storage import save_dataframe


@pytest.fixture(autouse=True)
def _init_dbs(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    import app.models.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path / "generated")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "generated").mkdir()
    import app.storage as storage_module
    monkeypatch.setattr(storage_module, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(storage_module, "GENERATED_DIR", tmp_path / "generated")
    init_db()
    init_rescue_db()


def test_download_dataset_returns_valid_csv():
    client = TestClient(app)
    df = pd.DataFrame({"Age": [30, 40, 50], "Gender": ["Male", "Female", "Male"]})
    dataset_id = new_id()
    path = save_dataframe(df, dataset_id)
    save_dataset_record(dataset_id, "my_data.csv", path, len(df), df.shape[1])

    r = client.get(f"/api/datasets/{dataset_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "my_data.csv" in r.headers["content-disposition"]

    # the CSV content must actually round-trip to the original data
    import io
    roundtrip = pd.read_csv(io.StringIO(r.text))
    assert roundtrip["Age"].tolist() == [30, 40, 50]
    assert roundtrip["Gender"].tolist() == ["Male", "Female", "Male"]


def test_download_nonexistent_dataset_404s():
    client = TestClient(app)
    r = client.get("/api/datasets/doesnotexist/download")
    assert r.status_code == 404


def test_rescue_report_not_available_before_completion():
    client = TestClient(app)
    df = pd.DataFrame({"Age": [30, 40], "Gender": ["Male", "Female"]})
    dataset_id = new_id()
    path = save_dataframe(df, dataset_id)
    save_dataset_record(dataset_id, "d.csv", path, len(df), df.shape[1])
    job = create_job(dataset_id)  # status "queued", never run

    r = client.get(f"/api/rescue/{job['job_id']}/report")
    assert r.status_code == 400


def test_rescue_report_contains_real_before_after_and_can_download_final_dataset():
    async def scenario():
        rows = [
            {"PatientID": f"P{i:03d}", "Age": 20 + i, "Gender": "Male" if i % 2 == 0 else "Female",
             "Pincode": f"11000{i}", "Diagnosis": "Flu"}
            for i in range(30)
        ]
        df = pd.DataFrame(rows)
        df = pd.concat([df, df.iloc[:5]], ignore_index=True)  # inject duplicates
        dataset_id = new_id()
        path = save_dataframe(df, dataset_id)
        save_dataset_record(dataset_id, "hospital.csv", path, len(df), df.shape[1])

        job = create_job(dataset_id)
        agent = DataRescueAgent(job["job_id"], dataset_id)
        task = asyncio.create_task(agent.run())

        from app.rescue.job_store import get_job
        for _ in range(30):
            current = get_job(job["job_id"])
            if current["status"] == "completed":
                break
            if current["status"] == "awaiting_approval" and current["pending_action_id"]:
                approval_registry.decide(job["job_id"], current["pending_action_id"], "approved")
            await asyncio.sleep(0.02)
        await task
        return job["job_id"], get_job(job["job_id"])

    job_id, final_job = asyncio.run(scenario())
    assert final_job["status"] == "completed"

    client = TestClient(app)

    # report endpoint
    r = client.get(f"/api/rescue/{job_id}/report")
    assert r.status_code == 200
    report = r.json()
    assert report["executive_summary"]["data_health_before"] == final_job["before_metrics"]["data_health"]
    assert report["executive_summary"]["data_health_after"] == final_job["after_metrics"]["data_health"]
    assert report["executive_summary"]["rescue_score"] == final_job["rescue_score"]
    assert len(report["problems_discovered"]["quality_issues"]) == len(final_job["discovered_issues"])
    assert len(report["audit_trail"]) == len(final_job["audit_events"])
    assert report["final_dataset_id"] == final_job["final_dataset_id"]

    # markdown variant
    r_md = client.get(f"/api/rescue/{job_id}/report?format=markdown")
    assert r_md.status_code == 200
    assert r_md.headers["content-type"].startswith("text/markdown")
    assert "DataRescue Report" in r_md.text
    assert "Audit Trail" in r_md.text

    # the final rescued dataset must actually be downloadable, not just referenced
    r_dl = client.get(f"/api/datasets/{final_job['final_dataset_id']}/download")
    assert r_dl.status_code == 200
    assert r_dl.headers["content-type"].startswith("text/csv")
    import io
    rescued_df = pd.read_csv(io.StringIO(r_dl.text))
    assert len(rescued_df) > 0
