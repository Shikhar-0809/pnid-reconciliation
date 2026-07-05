"""Unit tests for declarative reconciliation rules."""

from __future__ import annotations

from pnid_recon.reconciliation.rules import RULES
from pnid_recon.schemas.conflicts import ConflictType


def test_rules_registry_covers_value_and_type_checks() -> None:
    rule_ids = {rule["id"] for rule in RULES}
    assert {"missing_datasheet", "pressure_mismatch", "type_mismatch"}.issubset(
        rule_ids
    )


def test_rules_use_declarative_conflict_types() -> None:
    conflict_types = {rule["conflict_type"] for rule in RULES}
    assert ConflictType.MISSING_DATASHEET in conflict_types
    assert ConflictType.VALUE_MISMATCH in conflict_types
    assert ConflictType.TYPE_MISMATCH in conflict_types
