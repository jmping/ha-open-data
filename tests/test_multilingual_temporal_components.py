"""Regression coverage for localized split calendar fields."""

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.open_data.temporal import TemporalContext, infer_temporal_plan, parse_row_timestamp


def _context(zone: str = "Europe/Madrid") -> TemporalContext:
    return TemporalContext(datetime(2026, 9, 4, 12, tzinfo=ZoneInfo(zone)), zone)


def test_catalan_calendar_components_build_timestamp() -> None:
    rows = [
        {"ANY": 2026, "MES": 9, "DIA": 4, "HORA": 10, "valor": 17.2},
        {"ANY": 2026, "MES": 9, "DIA": 4, "HORA": 11, "valor": 17.8},
    ]
    plan = infer_temporal_plan(tuple(rows[0]), rows, _context())
    assert plan is not None
    assert plan.strategy == "calendar_components"
    parsed = parse_row_timestamp(rows[-1], plan, _context())
    assert parsed is not None
    assert parsed.isoformat() == "2026-09-04T11:00:00+02:00"


def test_spanish_accented_year_component_is_normalized() -> None:
    rows = [
        {"AÑO": 2026, "MES": 9, "DÍA": 4, "HORA": 10},
        {"AÑO": 2026, "MES": 9, "DÍA": 4, "HORA": 11},
    ]
    plan = infer_temporal_plan(tuple(rows[0]), rows, _context())
    assert plan is not None
    assert dict(plan.fields)["year"] == "AÑO"
    assert dict(plan.fields)["day"] == "DÍA"


def test_french_calendar_components_build_timestamp() -> None:
    rows = [
        {"ANNÉE": 2026, "MOIS": 9, "JOUR": 4, "HEURE": 10},
        {"ANNÉE": 2026, "MOIS": 9, "JOUR": 4, "HEURE": 11},
    ]
    context = _context("Europe/Paris")
    plan = infer_temporal_plan(tuple(rows[0]), rows, context)
    assert plan is not None
    assert plan.strategy == "calendar_components"
    assert parse_row_timestamp(rows[-1], plan, context).hour == 11
