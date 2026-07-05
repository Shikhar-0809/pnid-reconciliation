"""Deliberate conflict injection on perturbed index/datasheet copies."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from data_gen.instruments import PHANTOM_INSTRUMENT_TYPE, PHANTOM_SERVICE, PHANTOM_TAG
from data_gen.models import SeededConflict, TruthInstrument
from pnid_recon.schemas.conflicts import ConflictType, Severity
from pnid_recon.schemas.sources import Datasheet, IndexRow

InjectorFn = Callable[
    [random.Random, list[TruthInstrument], list[IndexRow], list[Datasheet]],
    tuple[list[IndexRow], list[Datasheet], SeededConflict | None],
]


@dataclass(frozen=True)
class InjectorSpec:
    """Declarative conflict injector metadata."""

    id: str
    apply: InjectorFn


T0_INJECTOR_ORDER: tuple[str, ...] = (
    "duplicate_tag",
    "missing_in_index",
    "missing_in_pid",
    "missing_datasheet",
    "value_mismatch",
    "type_mismatch",
)

T1_INJECTOR_ORDER = T0_INJECTOR_ORDER


def inject_conflicts(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
    *,
    tier: str,
) -> tuple[list[IndexRow], list[Datasheet], list[SeededConflict]]:
    """Perturb copies of index/datasheets and record every seeded conflict."""
    if tier == "T0":
        injector_order = T0_INJECTOR_ORDER
    elif tier == "T1":
        injector_order = T1_INJECTOR_ORDER
    else:
        msg = f"Unsupported tier {tier!r}; supported tiers: T0, T1"
        raise ValueError(msg)

    registry = {spec.id: spec for spec in _build_injectors()}
    working_index = [row.model_copy(deep=True) for row in index_rows]
    working_datasheets = [sheet.model_copy(deep=True) for sheet in datasheets]
    conflicts: list[SeededConflict] = []

    for injector_id in injector_order:
        spec = registry[injector_id]
        working_index, working_datasheets, conflict = spec.apply(
            rng,
            instruments,
            working_index,
            working_datasheets,
        )
        if conflict is not None:
            conflicts.append(conflict)

    return working_index, working_datasheets, conflicts


def _build_injectors() -> list[InjectorSpec]:
    return [
        InjectorSpec(id="duplicate_tag", apply=_inject_duplicate_tag),
        InjectorSpec(id="missing_in_index", apply=_inject_missing_in_index),
        InjectorSpec(id="missing_in_pid", apply=_inject_missing_in_pid),
        InjectorSpec(id="missing_datasheet", apply=_inject_missing_datasheet),
        InjectorSpec(id="value_mismatch", apply=_inject_value_mismatch),
        InjectorSpec(id="type_mismatch", apply=_inject_type_mismatch),
    ]


def _inject_duplicate_tag(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
) -> tuple[list[IndexRow], list[Datasheet], SeededConflict | None]:
    if not index_rows:
        return index_rows, datasheets, None

    source = index_rows[rng.randint(0, len(index_rows) - 1)]
    duplicate = source.model_copy(
        update={"service": f"{source.service} (duplicate row)"},
    )
    updated_index = [*index_rows, duplicate]
    return (
        updated_index,
        datasheets,
        SeededConflict(
            conflict_type=ConflictType.DUPLICATE_TAG,
            severity=Severity.LOW,
            tag=source.tag,
            sources=["index"],
            values={"index": source.tag},
            message=f"Tag {source.tag} appears more than once in the instrument index.",
            injector_id="duplicate_tag",
        ),
    )


def _inject_missing_in_index(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
) -> tuple[list[IndexRow], list[Datasheet], SeededConflict | None]:
    if not instruments:
        return index_rows, datasheets, None

    duplicate_tags = {
        tag
        for tag, count in _index_tag_counts(index_rows).items()
        if count > 1
    }
    candidates = [
        inst for inst in instruments if inst.tag not in duplicate_tags
    ]
    if not candidates:
        return index_rows, datasheets, None

    target = candidates[rng.randint(0, len(candidates) - 1)]
    updated_index = [row for row in index_rows if row.tag != target.tag]
    if len(updated_index) == len(index_rows):
        return index_rows, datasheets, None

    return (
        updated_index,
        datasheets,
        SeededConflict(
            conflict_type=ConflictType.MISSING_IN_INDEX,
            severity=Severity.MEDIUM,
            tag=target.tag,
            sources=["pid", "index"],
            values={"pid": target.tag},
            message=(
                f"Instrument {target.tag} is on the P&ID but missing from the index."
            ),
            injector_id="missing_in_index",
        ),
    )


def _inject_missing_in_pid(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
) -> tuple[list[IndexRow], list[Datasheet], SeededConflict | None]:
    del rng
    if any(row.tag == PHANTOM_TAG for row in index_rows):
        return index_rows, datasheets, None

    phantom = IndexRow(
        tag=PHANTOM_TAG,
        instrument_type=PHANTOM_INSTRUMENT_TYPE,
        service=PHANTOM_SERVICE,
        pid_ref="DWG-001",
        properties={"design_pressure": "6 bar"},
    )
    return (
        [*index_rows, phantom],
        datasheets,
        SeededConflict(
            conflict_type=ConflictType.MISSING_IN_PID,
            severity=Severity.MEDIUM,
            tag=PHANTOM_TAG,
            sources=["index", "pid"],
            values={"index": PHANTOM_TAG},
            message=f"Instrument {PHANTOM_TAG} is in the index but not on the P&ID.",
            injector_id="missing_in_pid",
        ),
    )


def _inject_missing_datasheet(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
) -> tuple[list[IndexRow], list[Datasheet], SeededConflict | None]:
    if not datasheets:
        return index_rows, datasheets, None

    value_mismatch_tags = {
        inst.tag for inst in instruments if inst.show_pressure_on_drawing
    }
    candidates = [sheet for sheet in datasheets if sheet.tag not in value_mismatch_tags]
    if not candidates:
        return index_rows, datasheets, None

    target = candidates[rng.randint(0, len(candidates) - 1)]
    updated = [sheet for sheet in datasheets if sheet.tag != target.tag]
    if len(updated) == len(datasheets):
        return index_rows, datasheets, None

    return (
        index_rows,
        updated,
        SeededConflict(
            conflict_type=ConflictType.MISSING_DATASHEET,
            severity=Severity.MEDIUM,
            tag=target.tag,
            sources=["index", "datasheet"],
            values={"index": target.tag},
            message=f"No datasheet found for instrument {target.tag}.",
            injector_id="missing_datasheet",
        ),
    )


def _inject_value_mismatch(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
) -> tuple[list[IndexRow], list[Datasheet], SeededConflict | None]:
    pressure_instruments = [
        inst
        for inst in instruments
        if inst.show_pressure_on_drawing and any(s.tag == inst.tag for s in datasheets)
    ]
    if not pressure_instruments:
        return index_rows, datasheets, None

    target = pressure_instruments[rng.randint(0, len(pressure_instruments) - 1)]
    perturbed_value = _perturbed_pressure(target.design_pressure)
    updated_sheets: list[Datasheet] = []
    changed = False
    for sheet in datasheets:
        if sheet.tag == target.tag:
            props = dict(sheet.properties)
            props["design_pressure"] = perturbed_value
            updated_sheets.append(sheet.model_copy(update={"properties": props}))
            changed = True
        else:
            updated_sheets.append(sheet)

    if not changed:
        return index_rows, datasheets, None

    return (
        index_rows,
        updated_sheets,
        SeededConflict(
            conflict_type=ConflictType.VALUE_MISMATCH,
            severity=Severity.HIGH,
            tag=target.tag,
            field="design_pressure",
            sources=["pid", "datasheet"],
            values={
                "pid": target.design_pressure,
                "datasheet": perturbed_value,
            },
            message=(
                f"Design pressure for {target.tag} differs between P&ID "
                f"({target.design_pressure}) and datasheet ({perturbed_value})."
            ),
            injector_id="value_mismatch",
        ),
    )


def _inject_type_mismatch(
    rng: random.Random,
    instruments: list[TruthInstrument],
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
) -> tuple[list[IndexRow], list[Datasheet], SeededConflict | None]:
    candidates = [
        inst
        for inst in instruments
        if any(row.tag == inst.tag for row in index_rows)
        and inst.instrument_type != "Temperature Indicator"
    ]
    if not candidates:
        return index_rows, datasheets, None

    target = candidates[rng.randint(0, len(candidates) - 1)]
    wrong_type = "Temperature Indicator"
    updated_index: list[IndexRow] = []
    changed = False
    for row in index_rows:
        if row.tag == target.tag:
            updated_index.append(row.model_copy(update={"instrument_type": wrong_type}))
            changed = True
        else:
            updated_index.append(row)

    if not changed:
        return index_rows, datasheets, None

    return (
        updated_index,
        datasheets,
        SeededConflict(
            conflict_type=ConflictType.TYPE_MISMATCH,
            severity=Severity.MEDIUM,
            tag=target.tag,
            field="instrument_type",
            sources=["pid", "index"],
            values={
                "pid": target.instrument_type,
                "index": wrong_type,
            },
            message=(
                f"Instrument type for {target.tag} differs between P&ID "
                f"({target.instrument_type}) and index ({wrong_type})."
            ),
            injector_id="type_mismatch",
        ),
    )


def _perturbed_pressure(correct: str) -> str:
    """Return a deterministic wrong pressure value for conflict seeding."""
    if correct == "50 bar":
        return "40 bar"
    if correct.endswith(" bar"):
        value = correct.removesuffix(" bar")
        try:
            numeric = float(value)
        except ValueError:
            return "40 bar"
        return f"{max(numeric - 10.0, 1.0):g} bar"
    return "40 bar"


def _index_tag_counts(index_rows: list[IndexRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in index_rows:
        counts[row.tag] = counts.get(row.tag, 0) + 1
    return counts
