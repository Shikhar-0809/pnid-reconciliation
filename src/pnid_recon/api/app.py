"""FastAPI routes — delegate to modules, no business logic here."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pnid_recon.extraction.extract import extract_pid
from pnid_recon.ingest.documents import load_datasheets, load_index_csv
from pnid_recon.ingest.images import resolve_image_path
from pnid_recon.reconciliation.engine import reconcile
from pnid_recon.reporting.report import report_to_json, report_to_markdown
from pnid_recon.schemas.conflicts import ConflictReport
from pnid_recon.schemas.extraction import ExtractionResult
from pnid_recon.storage.db import StoredRun, get_run, init_db, save_run

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="pnid-recon", version="0.1.0", lifespan=lifespan)


class ExtractRequest(BaseModel):
    """Path to a P&ID image for extraction."""

    image_path: str


class ReconcileRequest(BaseModel):
    """Extraction output plus paths to source documents."""

    extraction: ExtractionResult
    index_path: str
    datasheets_dir: str


class ProcessRequest(BaseModel):
    """Paths for the full extraction + reconciliation pipeline."""

    image_path: str
    index_path: str
    datasheets_dir: str


class ProcessResponse(BaseModel):
    """Full pipeline output including persisted run id and rendered report."""

    run_id: int
    report: ConflictReport
    report_json: str
    report_markdown: str


@app.post("/extract", response_model=ExtractionResult)
def extract_endpoint(body: ExtractRequest) -> ExtractionResult:
    """Extract instruments from a P&ID image."""
    try:
        image_path = resolve_image_path(body.image_path)
        return extract_pid(image_path)
    except Exception:
        logger.exception("Extract failed for image_path=%s", body.image_path)
        raise


@app.post("/reconcile", response_model=ConflictReport)
def reconcile_endpoint(body: ReconcileRequest) -> ConflictReport:
    """Reconcile an extraction result against index and datasheets."""
    index_rows = load_index_csv(body.index_path)
    datasheets = load_datasheets(body.datasheets_dir)
    return reconcile(body.extraction, index_rows, datasheets)


@app.post("/process", response_model=ProcessResponse)
def process_endpoint(body: ProcessRequest) -> ProcessResponse:
    """Run extraction and reconciliation, persist the run, return the report."""
    image_path = resolve_image_path(body.image_path)
    index_rows = load_index_csv(body.index_path)
    datasheets = load_datasheets(body.datasheets_dir)

    extraction = extract_pid(image_path)
    report = reconcile(extraction, index_rows, datasheets)
    run_id = save_run(extraction, report)

    return ProcessResponse(
        run_id=run_id,
        report=report,
        report_json=report_to_json(report),
        report_markdown=report_to_markdown(report),
    )


@app.get("/runs/{run_id}", response_model=StoredRun)
def get_run_endpoint(run_id: int) -> StoredRun:
    """Fetch a stored run with its extraction and conflict report."""
    try:
        return get_run(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
