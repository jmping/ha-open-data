"""Provider-independent field role classification for Home Assistant entities."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping


FIELD_ROLE_LOCATION = "location"
FIELD_ROLE_TIME = "time"
FIELD_ROLE_DATA = "data"
FIELD_ROLE_MEASUREMENT_NAME = "measurement_name"
FIELD_ROLE_DESCRIPTIVE = "descriptive"
FIELD_ROLE_IRRELEVANT = "irrelevant"
FIELD_ROLE_UNASSIGNED = "unassigned"
FIELD_ROLES = (
    FIELD_ROLE_LOCATION,
    FIELD_ROLE_TIME,
    FIELD_ROLE_DATA,
    FIELD_ROLE_MEASUREMENT_NAME,
    FIELD_ROLE_DESCRIPTIVE,
    FIELD_ROLE_IRRELEVANT,
    FIELD_ROLE_UNASSIGNED,
)
ASSIGNABLE_FIELD_ROLES = tuple(
    role for role in FIELD_ROLES if role != FIELD_ROLE_UNASSIGNED
)


_TIME_COMPONENTS = {
    "year", "month", "day", "hour", "minute", "second", "quarter", "week",
    "weekday", "date", "time", "timestamp", "datetime", "observed_at",
    "observation_time", "sample_date", "sample_time", "created_at", "updated_at",
    "created_date", "closed_date", "due_date", "resolution_action_updated_date",
    "date_collected", "collection_date", "received_date", "recorded_at",
    "measurement_time", "measurement_date", "start_date", "end_date",
    "inspection_date", "issue_date", "expiration_date", "event_date",
}
_CONTEXT_TERMS = (
    "agency", "vendor", "owner", "program", "project", "source", "status",
    "station", "site", "location", "beach", "waterbody", "water_body", "river",
    "lake", "county", "city", "municipality", "township", "state", "region",
    "watershed", "basin", "district", "precinct", "ward", "borough", "boro",
    "community_board", "community_district", "council_district", "address", "street",
    "cross_street", "intersection", "zip", "zipcode", "latitude", "longitude",
    "lat", "lon", "lng", "x_coordinate", "y_coordinate", "geometry", "geom",
    "shape", "the_geom", "sample_no", "sample_number", "sample_id", "kit_id",
    "unique_key", "permit", "facility", "descriptor", "complaint_type", "resolution",
    "category", "type", "code", "segment", "link", "roadway", "direction",
    "counter", "sensor", "bridge", "tunnel", "school", "building", "bin", "bbl",
    "block", "lot", "nta", "tree_id", "spc_common", "spc_latin", "health",
    "steward", "curb_loc", "incident", "case_number", "jurisdiction", "offense",
    "premise", "victim", "name", "label", "id",
)
_MEASUREMENT_TERMS = (
    "temperature", "humidity", "pressure", "concentration", "level", "height",
    "depth", "flow", "speed", "velocity", "rain", "precip", "wind", "battery",
    "voltage", "current", "power", "energy", "count", "total", "sum", "average",
    "mean", "median", "rate", "index", "score", "reading", "measurement", "value",
    "lead", "copper", "turbidity", "conductivity", "oxygen", "ph", "tonnage",
    "tons", "weight", "volume", "distance", "duration", "occupancy", "capacity",
    "travel_time", "data_value", "measure", "vehicles", "pedestrians", "bicycles",
    "dbh", "diameter", "pfas", "pfoa", "pfos", "pfna", "pfba", "pfhpa",
    "pfhxa", "pfhxs", "pfpea", "pfteda", "6_2_fts", "wave",
)
_NON_MEASUREMENT_VALUES = {
    "not detected", "not measured", "unknown", "n/a", "na", "none", "null", "",
    "below detection limit", "<lod", "<loq",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str) or value.strip().casefold() in _NON_MEASUREMENT_VALUES:
        return False
    candidate = value.strip().replace(",", "")
    if candidate.startswith("<"):
        candidate = candidate[1:].strip()
    try:
        float(candidate)
        return True
    except ValueError:
        return False


@dataclass(slots=True, frozen=True)
class FieldRoles:
    """Fields split into entity-producing metrics and descriptive context."""

    metric_fields: tuple[str, ...]
    context_fields: tuple[str, ...]
    time_fields: tuple[str, ...]
    location_fields: tuple[str, ...] = ()
    measurement_name_fields: tuple[str, ...] = ()
    irrelevant_fields: tuple[str, ...] = ()
    unassigned_fields: tuple[str, ...] = ()

    def as_assignments(self) -> dict[str, str]:
        """Return the mutually exclusive role assigned to every classified field."""
        return {
            **dict.fromkeys(self.location_fields, FIELD_ROLE_LOCATION),
            **dict.fromkeys(self.time_fields, FIELD_ROLE_TIME),
            **dict.fromkeys(self.metric_fields, FIELD_ROLE_DATA),
            **dict.fromkeys(
                self.measurement_name_fields, FIELD_ROLE_MEASUREMENT_NAME
            ),
            **dict.fromkeys(self.context_fields, FIELD_ROLE_DESCRIPTIVE),
            **dict.fromkeys(self.irrelevant_fields, FIELD_ROLE_IRRELEVANT),
            **dict.fromkeys(self.unassigned_fields, FIELD_ROLE_UNASSIGNED),
        }


def assignments_from_categories(
    field_names: Iterable[str],
    fields_by_role: Mapping[str, Iterable[str]],
) -> dict[str, str]:
    """Build roles from optional category selections.

    Fields omitted from every category are deliberately inactive. This lets a
    user classify only the variables that matter without reviewing every
    column in a wide dataset.

    A field selected in more than one category is reassigned to the last
    submitted category. Home Assistant renders the categories in deterministic
    order, so selecting a field in a new category no longer requires manually
    clearing its previous checkbox before saving.
    """
    fields = tuple(dict.fromkeys(field_names))
    known_fields = set(fields)
    assignments = dict.fromkeys(fields, FIELD_ROLE_UNASSIGNED)

    invalid_roles = set(fields_by_role) - set(ASSIGNABLE_FIELD_ROLES)
    if invalid_roles:
        raise ValueError(f"Invalid field-role categories: {sorted(invalid_roles)!r}")

    for role, selected_fields in fields_by_role.items():
        for field in selected_fields:
            if field not in known_fields:
                raise ValueError(f"Unknown field in role assignment: {field!r}")
            assignments[field] = role

    return assignments


def classify_field_roles(
    field_names: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
    *,
    configured_metrics: Iterable[str] = (),
    structural_fields: Iterable[str] = (),
    timestamp_fields: Iterable[str] = (),
    ignored_fields: Iterable[str] = (),
    explicit_roles: Mapping[str, str] | None = None,
) -> FieldRoles:
    """Classify fields conservatively and leave uncertain fields unassigned.

    Explicit ontology/configuration metrics win. Otherwise numeric values and
    measurement vocabulary are used together. Time components and structural
    identifiers never become sensors merely because they contain numbers.
    Fields without strong evidence remain inactive until the user assigns them.
    """
    fields = tuple(dict.fromkeys(field_names))
    ignored = set(ignored_fields)
    structural = set(structural_fields)
    configured = set(configured_metrics) - ignored
    explicit_time = set(timestamp_fields)
    explicit = dict(explicit_roles or {})
    invalid_roles = set(explicit.values()) - set(FIELD_ROLES)
    if invalid_roles:
        raise ValueError(f"Invalid field roles: {sorted(invalid_roles)!r}")
    row_list = list(rows)

    time_fields: list[str] = []
    metrics: list[str] = []
    context: list[str] = []
    locations: list[str] = []
    measurement_names: list[str] = []
    irrelevant: list[str] = []
    unassigned: list[str] = []

    for field in fields:
        role = explicit.get(field)
        if role == FIELD_ROLE_LOCATION:
            locations.append(field)
            continue
        if role == FIELD_ROLE_TIME:
            time_fields.append(field)
            continue
        if role == FIELD_ROLE_DATA:
            metrics.append(field)
            continue
        if role == FIELD_ROLE_MEASUREMENT_NAME:
            measurement_names.append(field)
            continue
        if role == FIELD_ROLE_DESCRIPTIVE:
            context.append(field)
            continue
        if role == FIELD_ROLE_IRRELEVANT or (role is None and field in ignored):
            irrelevant.append(field)
            continue
        if role == FIELD_ROLE_UNASSIGNED:
            unassigned.append(field)
            continue
        norm = _norm(field)
        is_time = field in explicit_time or norm in _TIME_COMPONENTS
        if is_time:
            time_fields.append(field)
            continue
        if field in configured:
            metrics.append(field)
            continue
        if field in structural:
            locations.append(field)
            continue

        values = [row.get(field) for row in row_list if row.get(field) not in (None, "")]
        numeric_ratio = (
            sum(_is_number(value) for value in values) / len(values) if values else 0.0
        )
        measurement_name = any(term in norm for term in _MEASUREMENT_TERMS)
        context_name = any(term in norm for term in _CONTEXT_TERMS)

        if measurement_name and numeric_ratio >= 0.2 and not context_name:
            metrics.append(field)
        elif numeric_ratio >= 0.8 and not context_name:
            metrics.append(field)
        else:
            unassigned.append(field)

    return FieldRoles(
        tuple(metrics),
        tuple(context),
        tuple(time_fields),
        tuple(locations),
        tuple(measurement_names),
        tuple(irrelevant),
        tuple(unassigned),
    )


def context_attributes(
    values: Mapping[str, Any], context_fields: Iterable[str], *, limit: int = 30
) -> dict[str, Any]:
    """Return bounded, Home Assistant-safe descriptive attributes."""
    attributes: dict[str, Any] = {}
    for field in context_fields:
        value = values.get(field)
        if value in (None, ""):
            continue
        if isinstance(value, (str, int, float, bool)):
            attributes[field] = value
        else:
            attributes[field] = str(value)[:255]
        if len(attributes) >= limit:
            break
    return attributes
