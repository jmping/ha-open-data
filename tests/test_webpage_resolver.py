from custom_components.open_data.webpage_resolver import _candidate_urls


def test_embedded_google_charts_collapse_to_shared_workbook() -> None:
    page = "https://www.example.gov/opioid-data"
    body = """
    <iframe src="https://docs.google.com/spreadsheets/d/e/ABC123/pubchart?oid=1"></iframe>
    <iframe src="https://docs.google.com/spreadsheets/d/e/ABC123/pubchart?oid=2"></iframe>
    """
    candidates = _candidate_urls(page, body)
    canonical = [item for item in candidates if item.relationship == "shared_upstream_workbook"]
    assert len(canonical) == 1
    assert canonical[0].url == "https://docs.google.com/spreadsheets/d/ABC123"
    assert canonical[0].kind == "google_sheet"


def test_arcgis_and_direct_data_links_are_generic_candidates() -> None:
    page = "https://example.gov/dashboard"
    body = """
    <a href="/exports/current.csv">CSV</a>
    <script>window.service = "https://gis.example.gov/arcgis/rest/services/Flood/FeatureServer/0";</script>
    """
    candidates = _candidate_urls(page, body)
    kinds = {item.kind for item in candidates}
    assert "csv" in kinds
    assert "arcgis_service" in kinds


def test_documentation_assets_and_image_apis_are_not_data_candidates() -> None:
    page = "https://api.weather.gov"
    body = """
    <a href="/openapi.json">API specification</a>
    <script src="/build/app.48df84fd.js"></script>
    <link href="/build/app.addd834c.css">
    <img src="/build/images/logo-noaa.svg">
    <img src="https://content.civicplus.com/api/assets/example?height=150">
    """

    assert _candidate_urls(page, body) == []
