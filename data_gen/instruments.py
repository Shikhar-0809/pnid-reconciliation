"""Deterministic ISA 5.1 instrument sampling for synthetic scenarios."""

import random
from dataclasses import dataclass

from data_gen.models import TruthInstrument


@dataclass(frozen=True)
class InstrumentTemplate:
    """Catalog entry with valid ISA 5.1 tag and engineering attributes."""

    tag: str
    instrument_type: str
    service: str
    manufacturer: str
    model: str
    design_pressure: str
    range: str
    show_pressure_on_drawing: bool = False


# Fixed catalog — valid ISA 5.1 tags per DOMAIN_GLOSSARY.
CATALOG: tuple[InstrumentTemplate, ...] = (
    InstrumentTemplate(
        tag="PT-101",
        instrument_type="Pressure Transmitter",
        service="Reactor pressure",
        manufacturer="Rosemount",
        model="3051CD",
        design_pressure="50 bar",
        range="0-100 bar",
        show_pressure_on_drawing=True,
    ),
    InstrumentTemplate(
        tag="TT-102",
        instrument_type="Temperature Transmitter",
        service="Reactor temperature",
        manufacturer="Yokogawa",
        model="YTA110",
        design_pressure="10 bar",
        range="0-200 C",
    ),
    InstrumentTemplate(
        tag="FT-103",
        instrument_type="Flow Transmitter",
        service="Feed flow",
        manufacturer="Endress+Hauser",
        model="Promag 50",
        design_pressure="16 bar",
        range="0-50 m3/h",
    ),
    InstrumentTemplate(
        tag="LT-104",
        instrument_type="Level Transmitter",
        service="Reactor level",
        manufacturer="Vega",
        model="VEGAPULS 64",
        design_pressure="50 bar",
        range="0-3000 mm",
    ),
    InstrumentTemplate(
        tag="FIC-105",
        instrument_type="Flow Indicating Controller",
        service="Product flow control",
        manufacturer="Honeywell",
        model="UDC2500",
        design_pressure="25 bar",
        range="0-80 m3/h",
    ),
    InstrumentTemplate(
        tag="LCV-106",
        instrument_type="Level Control Valve",
        service="Bottom outlet level control",
        manufacturer="Fisher",
        model="EZ",
        design_pressure="50 bar",
        range="0-100 pct",
    ),
    InstrumentTemplate(
        tag="TT-107",
        instrument_type="Temperature Transmitter",
        service="Outlet temperature",
        manufacturer="Yokogawa",
        model="YTA110",
        design_pressure="10 bar",
        range="0-150 C",
    ),
    InstrumentTemplate(
        tag="PT-108",
        instrument_type="Pressure Transmitter",
        service="Column overhead pressure",
        manufacturer="Rosemount",
        model="3051CD",
        design_pressure="16 bar",
        range="0-25 bar",
    ),
    InstrumentTemplate(
        tag="FT-109",
        instrument_type="Flow Transmitter",
        service="Recycle flow",
        manufacturer="Endress+Hauser",
        model="Promag 50",
        design_pressure="25 bar",
        range="0-120 m3/h",
    ),
    InstrumentTemplate(
        tag="LT-110",
        instrument_type="Level Transmitter",
        service="Separator level",
        manufacturer="Vega",
        model="VEGAPULS 64",
        design_pressure="16 bar",
        range="0-2000 mm",
    ),
    InstrumentTemplate(
        tag="TIC-111",
        instrument_type="Temperature Indicating Controller",
        service="Reactor temperature control",
        manufacturer="Honeywell",
        model="UDC2500",
        design_pressure="10 bar",
        range="0-200 C",
    ),
    InstrumentTemplate(
        tag="FCV-112",
        instrument_type="Flow Control Valve",
        service="Product flow control",
        manufacturer="Fisher",
        model="657",
        design_pressure="25 bar",
        range="0-100 pct",
    ),
    InstrumentTemplate(
        tag="PIC-113",
        instrument_type="Pressure Indicating Controller",
        service="Column pressure control",
        manufacturer="Honeywell",
        model="UDC2500",
        design_pressure="16 bar",
        range="0-25 bar",
        show_pressure_on_drawing=True,
    ),
    InstrumentTemplate(
        tag="AT-114",
        instrument_type="Analyzer Transmitter",
        service="Product composition",
        manufacturer="ABB",
        model="AO2000",
        design_pressure="6 bar",
        range="0-100 pct",
    ),
)

PHANTOM_TAG = "FT-999"
PHANTOM_INSTRUMENT_TYPE = "Flow Transmitter"
PHANTOM_SERVICE = "Cooling water return"


def sample_instruments(rng: random.Random, tier: str) -> list[TruthInstrument]:
    """Sample a deterministic instrument set for the requested tier."""
    if tier == "T0":
        count = 3 + rng.randint(0, 2)
    elif tier == "T1":
        count = 8 + rng.randint(0, 4)
    else:
        msg = f"Unsupported tier {tier!r}; supported tiers: T0, T1"
        raise ValueError(msg)

    if count > len(CATALOG):
        msg = f"Catalog has {len(CATALOG)} instruments; tier {tier} requested {count}"
        raise ValueError(msg)

    indices = rng.sample(range(len(CATALOG)), count)
    return [_template_to_truth(CATALOG[i]) for i in sorted(indices)]


def _template_to_truth(template: InstrumentTemplate) -> TruthInstrument:
    return TruthInstrument(
        tag=template.tag,
        instrument_type=template.instrument_type,
        service=template.service,
        manufacturer=template.manufacturer,
        model=template.model,
        design_pressure=template.design_pressure,
        range=template.range,
        show_pressure_on_drawing=template.show_pressure_on_drawing,
    )
