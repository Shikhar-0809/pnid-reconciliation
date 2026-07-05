"""SQLite persistence for extraction runs and conflict reports."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from pnid_recon.config import settings
from pnid_recon.schemas.conflicts import Conflict, ConflictReport
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult

_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_image TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_CREATE_INSTRUMENTS = """
CREATE TABLE IF NOT EXISTS instruments (
    run_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
"""

_CREATE_CONFLICTS = """
CREATE TABLE IF NOT EXISTS conflicts (
    run_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
"""


class StoredRun(BaseModel):
    """A persisted pipeline run with extraction output and conflict report."""

    id: int
    source_image: str
    model_name: str
    created_at: str
    extraction: ExtractionResult
    report: ConflictReport


def init_db(db_path: Path | None = None) -> None:
    """Create SQLite tables when missing."""
    path = db_path or settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript(
            _CREATE_RUNS + _CREATE_INSTRUMENTS + _CREATE_CONFLICTS,
        )
        connection.execute("PRAGMA journal_mode=WAL;")


def save_run(
    extraction: ExtractionResult,
    report: ConflictReport,
    *,
    db_path: Path | None = None,
) -> int:
    """Persist an extraction result and conflict report; return the run id."""
    path = db_path or settings.database_path
    init_db(path)
    created_at = datetime.now(tz=UTC).isoformat()

    with _connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO runs (source_image, model_name, created_at)
            VALUES (?, ?, ?)
            """,
            (extraction.source_image, extraction.model_name, created_at),
        )
        run_id_raw = cursor.lastrowid
        if run_id_raw is None:
            msg = "Failed to create run record"
            raise RuntimeError(msg)
        run_id = int(run_id_raw)

        for instrument in extraction.instruments:
            connection.execute(
                """
                INSERT INTO instruments (run_id, tag, json)
                VALUES (?, ?, ?)
                """,
                (
                    run_id,
                    instrument.tag,
                    instrument.model_dump_json(),
                ),
            )

        for conflict in report.conflicts:
            connection.execute(
                """
                INSERT INTO conflicts (run_id, tag, type, severity, json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    conflict.tag,
                    conflict.conflict_type.value,
                    conflict.severity.value,
                    conflict.model_dump_json(),
                ),
            )

        connection.commit()
        return run_id


def get_run(run_id: int, *, db_path: Path | None = None) -> StoredRun:
    """Load a stored run with its instruments and conflicts."""
    path = db_path or settings.database_path
    init_db(path)

    with _connect(path) as connection:
        row = connection.execute(
            "SELECT id, source_image, model_name, created_at FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            msg = f"Run {run_id} not found"
            raise LookupError(msg)

        instruments = [
            ExtractedInstrument.model_validate_json(instrument_row[0])
            for instrument_row in connection.execute(
                "SELECT json FROM instruments WHERE run_id = ? ORDER BY tag",
                (run_id,),
            ).fetchall()
        ]

        conflicts = [
            Conflict.model_validate_json(conflict_row[0])
            for conflict_row in connection.execute(
                "SELECT json FROM conflicts WHERE run_id = ? ORDER BY tag",
                (run_id,),
            ).fetchall()
        ]

    extraction = ExtractionResult(
        source_image=row[1],
        model_name=row[2],
        instruments=instruments,
    )
    report = ConflictReport(
        conflicts=conflicts,
        summary=_summary_from_conflicts(conflicts),
        generated_at=row[3],
    )
    return StoredRun(
        id=row[0],
        source_image=row[1],
        model_name=row[2],
        created_at=row[3],
        extraction=extraction,
        report=report,
    )


def _summary_from_conflicts(conflicts: list[Conflict]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for conflict in conflicts:
        type_key = conflict.conflict_type.value
        summary[type_key] = summary.get(type_key, 0) + 1
        severity_key = f"severity:{conflict.severity.value}"
        summary[severity_key] = summary.get(severity_key, 0) + 1
    return summary


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection
