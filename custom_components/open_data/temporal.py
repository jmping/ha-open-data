"""Explainable timestamp planning and parsing for heterogeneous open-data rows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import math
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

_COMPONENT_ALIASES = {
    "year": {"year", "yr", "yyyy"},
    "month": {"month", "mon", "mm"},
    "day": {"day", "day_of_month", "dom", "dd"},
    "hour": {"hour", "hr", "hh"},
    "minute": {"minute", "min", "mi"},
    "second": {"second", "sec", "ss"},
    "date": {"date", "sample_date", "measurement_date", "observation_date", "observed_date", "collection_date"},
    "time": {"time", "sample_time", "measurement_time", "observation_time", "observed_time", "collection_time"},
    "timestamp": {"timestamp", "datetime", "date_time", "observed_at", "measured_at", "sampled_at", "collected_at", "observation_time"},
}
_ADMIN_TIME_TERMS = {"updated_at", "modified", "last_modified", "created_at", "dataset_updated", "resource_updated"}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


@dataclass(frozen=True, slots=True)
class TemporalContext:
    """External facts used to resolve incomplete local timestamps."""

    now: datetime
    timezone_name: str = "UTC"
    source_updated_at: datetime | None = None

    @classmethod
    def current(cls, timezone_name: str = "UTC") -> "TemporalContext":
        zone = ZoneInfo(timezone_name)
        return cls(datetime.now(zone), timezone_name)


@dataclass(frozen=True, slots=True)
class TemporalPlan:
    """Persistable strategy for constructing one observation timestamp."""

    strategy: str
    fields: tuple[tuple[str, str], ...]
    timezone_name: str
    confidence: float
    parse_success_rate: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["fields"] = dict(self.fields)
        return result

    @property
    def field_map(self) -> dict[str, str]:
        return dict(self.fields)


@dataclass(frozen=True, slots=True)
class TemporalCandidate:
    plan: TemporalPlan
    parsed: tuple[datetime | None, ...]


def _int_value(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _parse_clock(value: Any) -> time | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%H%M", "%H%M%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _parse_date(value: Any, context: TemporalContext) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y",
        "%d %b %Y", "%Y%m%d", "%m-%d-%Y", "%m-%d-%y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    partial = re.fullmatch(r"\s*(\d{1,2})[/-](\d{1,2})\s*", text)
    if partial:
        return _nearest_partial_date(int(partial.group(1)), int(partial.group(2)), context)
    return None


def _nearest_partial_date(month: int, day: int, context: TemporalContext) -> date | None:
    candidates: list[date] = []
    for year in (context.now.year - 1, context.now.year, context.now.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            pass
    if not candidates:
        return None
    today = context.now.date()
    plausible = [item for item in candidates if item <= today + timedelta(days=2)]
    return min(plausible or candidates, key=lambda item: abs((item - today).days))


def _attach_zone(value: datetime, context: TemporalContext) -> datetime:
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=ZoneInfo(context.timezone_name))


def parse_flexible_timestamp(value: Any, context: TemporalContext) -> datetime | None:
    """Parse complete timestamps, epochs, and common municipal date/time formats."""
    if isinstance(value, datetime):
        return _attach_zone(value, context)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if math.isfinite(number):
            if abs(number) >= 1e12:
                number /= 1000.0
            if 0 < number < 4_102_444_800:
                return datetime.fromtimestamp(number, timezone.utc)
        return None
    if value in (None, ""):
        return None
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return parse_flexible_timestamp(float(text), context)
    iso = text.replace("Z", "+00:00")
    try:
        return _attach_zone(datetime.fromisoformat(iso), context)
    except ValueError:
        pass
    for fmt in (
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
        "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y%m%d%H%M%S",
    ):
        try:
            return _attach_zone(datetime.strptime(text, fmt), context)
        except ValueError:
            continue
    parsed_date = _parse_date(text, context)
    if parsed_date is not None:
        return datetime.combine(parsed_date, time.min, ZoneInfo(context.timezone_name))
    return None


def _field_candidates(fields: Sequence[str], role: str) -> tuple[str, ...]:
    aliases = _COMPONENT_ALIASES[role]
    normalized = {field: _norm(field) for field in fields}
    exact = [field for field, name in normalized.items() if name in aliases]
    fuzzy = [
        field for field, name in normalized.items()
        if field not in exact and any(name.endswith(f"_{alias}") or name.startswith(f"{alias}_") for alias in aliases)
    ]
    return tuple((*exact, *fuzzy))


def _candidate_score(plan: TemporalPlan, parsed: Sequence[datetime | None], context: TemporalContext) -> TemporalPlan:
    valid = [item for item in parsed if item is not None]
    success = len(valid) / max(len(parsed), 1)
    distinct = len({item.isoformat() for item in valid})
    future = sum(item > context.now + timedelta(days=2) for item in valid) / max(len(valid), 1)
    score = 0.45 * success + (0.15 if distinct > 1 else 0.0) + (0.15 if valid else 0.0)
    score -= 0.6 * future
    field_names = {_norm(name) for _, name in plan.fields}
    if field_names & _ADMIN_TIME_TERMS:
        score -= 0.18
    if plan.strategy in {"calendar_components", "date_and_time"}:
        score += 0.12
    reasons = list(plan.reasons)
    reasons.append(f"{success:.0%} of sampled rows parsed")
    if distinct > 1:
        reasons.append("timestamps vary across observations")
    if future:
        reasons.append(f"{future:.0%} implausibly future values")
    return TemporalPlan(plan.strategy, plan.fields, plan.timezone_name, round(max(0.0, min(1.0, score)), 3), round(success, 3), tuple(reasons))


def parse_row_timestamp(row: Mapping[str, Any], plan: TemporalPlan, context: TemporalContext) -> datetime | None:
    fields = plan.field_map
    if plan.strategy == "single_field":
        return parse_flexible_timestamp(row.get(fields["timestamp"]), context)
    if plan.strategy == "date_and_time":
        parsed_date = _parse_date(row.get(fields["date"]), context)
        parsed_time = _parse_clock(row.get(fields["time"]))
        if parsed_date is None or parsed_time is None:
            return None
        return datetime.combine(parsed_date, parsed_time, ZoneInfo(context.timezone_name))
    if plan.strategy == "calendar_components":
        year = _int_value(row.get(fields.get("year", ""))) if "year" in fields else None
        month = _int_value(row.get(fields.get("month", "")))
        day = _int_value(row.get(fields.get("day", "")))
        hour = _int_value(row.get(fields.get("hour", ""))) or 0
        minute = _int_value(row.get(fields.get("minute", ""))) or 0
        second = _int_value(row.get(fields.get("second", ""))) or 0
        if month is None or day is None:
            return None
        if year is None:
            inferred = _nearest_partial_date(month, day, context)
            year = inferred.year if inferred else None
        if year is None:
            return None
        try:
            return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(context.timezone_name))
        except ValueError:
            return None
    return None


def infer_temporal_plan(fields: Sequence[str], rows: Sequence[Mapping[str, Any]], context: TemporalContext) -> TemporalPlan | None:
    """Generate and score complete-field and component-based timestamp plans."""
    candidates: list[TemporalPlan] = []
    for field in _field_candidates(fields, "timestamp"):
        candidates.append(TemporalPlan("single_field", (("timestamp", field),), context.timezone_name, 0.0, 0.0, ("complete timestamp field",)))
    date_fields = _field_candidates(fields, "date")
    time_fields = _field_candidates(fields, "time")
    for date_field in date_fields[:3]:
        for time_field in time_fields[:3]:
            if date_field != time_field:
                candidates.append(TemporalPlan("date_and_time", (("date", date_field), ("time", time_field)), context.timezone_name, 0.0, 0.0, ("date and time fields combined",)))
    components = {role: _field_candidates(fields, role) for role in ("year", "month", "day", "hour", "minute", "second")}
    if components["month"] and components["day"]:
        mapping = [("month", components["month"][0]), ("day", components["day"][0])]
        for role in ("year", "hour", "minute", "second"):
            if components[role]:
                mapping.append((role, components[role][0]))
        candidates.append(TemporalPlan("calendar_components", tuple(mapping), context.timezone_name, 0.0, 0.0, ("calendar components synthesized", "missing year resolved near current date" if not components["year"] else "explicit year component",)))
    scored: list[TemporalPlan] = []
    for candidate in candidates:
        parsed = tuple(parse_row_timestamp(row, candidate, context) for row in rows)
        scored.append(_candidate_score(candidate, parsed, context))
    usable = [item for item in scored if item.parse_success_rate >= 0.5]
    return max(usable, key=lambda item: (item.confidence, item.parse_success_rate), default=None)


def normalize_row_timestamps(rows: Sequence[Mapping[str, Any]], *, timezone_name: str, now: datetime | None = None) -> tuple[list[dict[str, Any]], TemporalPlan | None, str | None]:
    """Copy rows and add one canonical timestamp field when a plan is usable."""
    zone = ZoneInfo(timezone_name)
    context = TemporalContext(now or datetime.now(zone), timezone_name)
    fields = tuple(dict.fromkeys(str(field) for row in rows for field in row))
    plan = infer_temporal_plan(fields, rows, context)
    if plan is None:
        return [dict(row) for row in rows], None, None
    canonical = "__open_data_timestamp"
    normalized: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        parsed = parse_row_timestamp(row, plan, context)
        if parsed is not None:
            copied[canonical] = parsed.isoformat()
        normalized.append(copied)
    return normalized, plan, canonical
