"""Runtime orchestration for bounded dataset re-analysis."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .adaptive_sampling import infer_dataset_ordering
from .const import CONF_FIELD_ROLES
from .field_roles import (
    FIELD_ROLE_DATA,
    FIELD_ROLE_MEASUREMENT_NAME,
    classify_field_roles,
)
from .observation_sampling import stratify_observation_rows
from .reanalysis import (
    AnalysisFingerprint,
    ReanalysisState,
    build_analysis_fingerprint,
    decide_reanalysis,
    record_reanalysis_result,
)

CONF_REANALYSIS_STATE = "reanalysis_state"
DATA_REANALYSIS_CONTROLLERS = "reanalysis_controllers"
DATA_SUPPRESS_RELOAD = "suppress_reanalysis_reload"
MAX_REANALYSIS_SAMPLE_ROWS = 200
MAX_REANALYSIS_CANDIDATE_ROWS = 800


def _fingerprint_from_dict(value: Mapping[str, Any] | None) -> AnalysisFingerprint | None:
    if not value:
        return None
    try:
        return AnalysisFingerprint(
            schema=tuple(tuple(item) for item in value.get("schema", ())),
            field_roles=tuple(tuple(item) for item in value.get("field_roles", ())),
            metrics=tuple(value.get("metrics", ())),
            dimensions=tuple(
                (item[0], tuple(item[1])) for item in value.get("dimensions", ())
            ),
            coordinate_mode=str(value.get("coordinate_mode", "none")),
            ordering=str(value.get("ordering", "unknown")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_reanalysis_state(value: Mapping[str, Any] | None) -> ReanalysisState:
    """Load persisted state conservatively."""
    value = value or {}
    return ReanalysisState(
        fingerprint=_fingerprint_from_dict(value.get("fingerprint")),
        last_attempt_at=value.get("last_attempt_at"),
        last_success_at=value.get("last_success_at"),
        reason=value.get("reason"),
        result=str(value.get("result", "never_run")),
        review_recommended=bool(value.get("review_recommended", False)),
        consecutive_failures=int(value.get("consecutive_failures", 0)),
    )


def dump_reanalysis_state(state: ReanalysisState) -> dict[str, Any]:
    """Serialize persisted state."""
    return {
        "fingerprint": state.fingerprint.as_dict() if state.fingerprint else None,
        "last_attempt_at": state.last_attempt_at,
        "last_success_at": state.last_success_at,
        "reason": state.reason,
        "result": state.result,
        "review_recommended": state.review_recommended,
        "consecutive_failures": state.consecutive_failures,
    }


def _coordinate_mode(field_names: set[str]) -> str:
    lowered = {name.casefold() for name in field_names}
    latitude = {"latitude", "lat", "y_wgs84"}
    longitude = {"longitude", "lon", "lng", "x_wgs84"}
    if lowered & latitude and lowered & longitude:
        return "wgs84_fields"
    if lowered & {"geometry", "geom", "geolocation", "location"}:
        return "geometry"
    return "none"


def reviewed_roles_for_current_schema(
    *,
    field_names: tuple[str, ...],
    rows: list[Mapping[str, Any]],
    reviewed_roles: Mapping[str, str],
) -> dict[str, str]:
    """Keep reviewed assignments and infer only newly appearing fields."""
    current = set(field_names)
    retained = {
        field: role for field, role in reviewed_roles.items() if field in current
    }
    return classify_field_roles(
        field_names,
        rows,
        explicit_roles=retained,
    ).as_assignments()


@dataclass(slots=True)
class ReanalysisController:
    """Serialize automatic and manual bounded analysis for one config entry."""

    hass: Any
    entry: Any
    coordinator: Any
    _lock: asyncio.Lock | None = None
    _sampling_evidence: dict[str, Any] | None = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _async_candidate_rows(self, dataset: Any) -> list[dict[str, Any]]:
        """Prefer an ordered history window when the provider supports it."""
        provider = self.coordinator.provider
        capabilities = getattr(provider, "capabilities", None)
        if (
            self.coordinator.timestamp_field is not None
            and capabilities is not None
            and capabilities.supports_timeseries
        ):
            return await provider.async_observation_rows(
                dataset.dataset_id,
                dataset.resource_id,
                self.coordinator.timestamp_field,
                limit=MAX_REANALYSIS_CANDIDATE_ROWS,
            )
        return await provider.async_sample_rows(
            dataset.dataset_id,
            dataset.resource_id,
            limit=MAX_REANALYSIS_CANDIDATE_ROWS,
        )

    async def async_build_fingerprint(self) -> AnalysisFingerprint:
        """Collect a capped stratified provider sample and build current evidence."""
        dataset = self.coordinator.dataset
        if dataset is None:
            dataset = await self.coordinator.provider.async_get_dataset(
                self.coordinator.dataset_id, self.coordinator.resource_id
            )
        candidate_rows = await self._async_candidate_rows(dataset)
        identity_fields = (
            (self.coordinator.identity_field,)
            if self.coordinator.identity_field is not None
            else ()
        )
        sample = stratify_observation_rows(
            candidate_rows,
            timestamp_field=self.coordinator.timestamp_field,
            identity_fields=identity_fields,
            limit=MAX_REANALYSIS_SAMPLE_ROWS,
        )
        rows = list(sample.rows)
        self._sampling_evidence = sample.evidence.as_dict()
        reviewed = self.entry.options.get(
            CONF_FIELD_ROLES,
            self.entry.data.get(CONF_FIELD_ROLES, self.coordinator.field_roles),
        )
        roles = reviewed_roles_for_current_schema(
            field_names=tuple(field.name for field in dataset.fields),
            rows=rows,
            reviewed_roles=reviewed or {},
        )
        metric_fields = tuple(
            field for field, role in roles.items() if role == FIELD_ROLE_DATA
        )
        dimension_fields = tuple(
            field for field, role in roles.items() if role == FIELD_ROLE_MEASUREMENT_NAME
        )
        ordering = infer_dataset_ordering(
            rows,
            self.coordinator.identity_field,
            self.coordinator.timestamp_field,
        )
        names = {field.name for field in dataset.fields}
        return build_analysis_fingerprint(
            fields=((field.name, field.data_type) for field in dataset.fields),
            field_roles=roles,
            rows=rows,
            metric_fields=metric_fields,
            dimension_fields=dimension_fields,
            coordinate_mode=_coordinate_mode(names),
            ordering=str(ordering),
        )

    async def async_run(self, *, manual: bool = False) -> dict[str, Any]:
        """Run one serialized check; failures preserve the last working state."""
        async with self.lock:
            previous = load_reanalysis_state(
                self.entry.data.get(CONF_REANALYSIS_STATE)
            )
            now = datetime.now(timezone.utc)
            try:
                fingerprint = await self.async_build_fingerprint()
                decision = decide_reanalysis(previous, fingerprint, now=now, manual=manual)
                if not decision.should_run:
                    return {
                        "ran": False,
                        "reason": decision.reason,
                        "next_allowed_at": decision.next_allowed_at,
                        "sampling_evidence": self._sampling_evidence,
                        "state": dump_reanalysis_state(previous),
                    }
                review = decision.reason not in {"initial_analysis", "manual_request"}
                current = record_reanalysis_result(
                    previous,
                    attempted_at=now,
                    reason=decision.reason,
                    fingerprint=fingerprint,
                    success=True,
                    review_recommended=review,
                )
            except Exception:
                current = record_reanalysis_result(
                    previous,
                    attempted_at=now,
                    reason="manual_request" if manual else "automatic_check",
                    fingerprint=None,
                    success=False,
                )
                await self._async_persist(current)
                raise
            await self._async_persist(current)
            return {
                "ran": True,
                "reason": current.reason,
                "review_recommended": current.review_recommended,
                "sampling_evidence": self._sampling_evidence,
                "state": dump_reanalysis_state(current),
            }

    async def _async_persist(self, state: ReanalysisState) -> None:
        value = dump_reanalysis_state(state)
        if self.entry.data.get(CONF_REANALYSIS_STATE) == value:
            return
        domain_data = self.hass.data.setdefault("open_data", {})
        domain_data.setdefault(DATA_SUPPRESS_RELOAD, set()).add(self.entry.entry_id)
        data = dict(self.entry.data)
        data[CONF_REANALYSIS_STATE] = value
        self.hass.config_entries.async_update_entry(self.entry, data=data)
