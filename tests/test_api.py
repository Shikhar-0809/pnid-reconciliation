"""API integration tests for the full pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pnid_recon.api.app import app
from pnid_recon.config import settings
from pnid_recon.schemas.conflicts import ConflictType
from pnid_recon.storage.db import init_db
from tests.fixtures.reconciliation_fixtures import build_full_conflict_fixture

SCENARIO_DIR = settings.scenarios_dir / "scenario_001"


def _scenario_paths() -> dict[str, str]:
    return {
        "image_path": str(SCENARIO_DIR / "pid.png"),
        "index_path": str(SCENARIO_DIR / "instrument_index.csv"),
        "datasheets_dir": str(SCENARIO_DIR / "datasheets"),
    }


@pytest.fixture
def api_client(tmp_path: Path) -> Iterator[TestClient]:
    db_path = tmp_path / "test.db"
    with patch.object(settings, "database_path", db_path):
        init_db(db_path)
        yield TestClient(app)


def test_process_t0_scenario_returns_full_report(api_client: TestClient) -> None:
    if not SCENARIO_DIR.exists():
        pytest.skip("T0 scenario not generated")

    extraction, _, _, expected_types = build_full_conflict_fixture()

    with (
        patch("pnid_recon.api.app.extract_pid", return_value=extraction),
        patch("pnid_recon.api.app.text_complete", return_value="[]"),
    ):
        response = api_client.post("/process", json=_scenario_paths())

    assert response.status_code == 200
    payload = response.json()
    assert "run_id" in payload
    assert payload["report"]["conflicts"]
    assert payload["report_json"]
    assert payload["report_markdown"]

    found_types = {
        conflict["conflict_type"] for conflict in payload["report"]["conflicts"]
    }
    assert expected_types.issubset(found_types)


def test_get_run_returns_stored_report(api_client: TestClient) -> None:
    if not SCENARIO_DIR.exists():
        pytest.skip("T0 scenario not generated")

    extraction, _, _, _ = build_full_conflict_fixture()

    with (
        patch("pnid_recon.api.app.extract_pid", return_value=extraction),
        patch("pnid_recon.api.app.text_complete", return_value="[]"),
    ):
        process_response = api_client.post("/process", json=_scenario_paths())
        run_id = process_response.json()["run_id"]
        run_response = api_client.get(f"/runs/{run_id}")

    assert run_response.status_code == 200
    stored = run_response.json()
    assert stored["id"] == run_id
    assert stored["extraction"]["instruments"]
    assert stored["report"]["conflicts"]


def test_reconcile_endpoint_returns_conflicts(api_client: TestClient) -> None:
    if not SCENARIO_DIR.exists():
        pytest.skip("T0 scenario not generated")

    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    paths = _scenario_paths()

    with (
        patch("pnid_recon.api.app.load_index_csv", return_value=index_rows),
        patch("pnid_recon.api.app.load_datasheets", return_value=datasheets),
        patch("pnid_recon.api.app.text_complete", return_value="[]"),
    ):
        response = api_client.post(
            "/reconcile",
            json={
                "extraction": extraction.model_dump(mode="json"),
                "index_path": paths["index_path"],
                "datasheets_dir": paths["datasheets_dir"],
            },
        )

    assert response.status_code == 200
    found_types = {
        conflict["conflict_type"] for conflict in response.json()["conflicts"]
    }
    assert ConflictType.VALUE_MISMATCH.value in found_types
