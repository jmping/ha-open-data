"""Home Assistant test fixtures for the Open Data integration."""

pytest_plugins = "pytest_homeassistant_custom_component"


import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load the repository custom integration."""
    yield
