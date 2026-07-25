"""Regression guard for the single-entry portal preparation path."""

from pathlib import Path


def test_config_flow_logs_reference_kind_only_when_supported() -> None:
    """The flow and reference model must evolve together."""
    root = Path(__file__).parents[1]
    flow_source = (root / "custom_components/open_data/config_flow.py").read_text(
        encoding="utf-8"
    )
    reference_source = (root / "custom_components/open_data/reference.py").read_text(
        encoding="utf-8"
    )
    assert "reference.kind" in flow_source
    assert "def kind(self) -> str:" in reference_source
