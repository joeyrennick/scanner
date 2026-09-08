from fastapi.testclient import TestClient

from scanner.desktop.sidecar import create_desktop_app


TOKEN = "phase-zero-test-token-that-is-long-enough"


def test_desktop_health_requires_bearer_token():
    client = TestClient(create_desktop_app(TOKEN))

    response = client.get("/api/desktop/health")

    assert response.status_code == 401
    assert response.json() == {"detail": "Desktop authentication required"}


def test_desktop_health_reports_packaged_dependency_versions():
    client = TestClient(create_desktop_app(TOKEN))

    response = client.get(
        "/api/desktop/health",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "desktop-proof-of-concept"
    assert payload["architecture"]
    assert set(payload["dependencies"]) == {
        "certifi",
        "lxml",
        "matplotlib",
        "numpy",
        "pandas",
        "pillow",
        "uvicorn",
    }


def test_desktop_shutdown_runs_callback_after_authenticated_response():
    shutdown_requests = []
    client = TestClient(
        create_desktop_app(TOKEN, shutdown_callback=lambda: shutdown_requests.append(True))
    )

    response = client.post(
        "/api/desktop/shutdown",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 202
    assert response.json() == {"status": "shutting_down"}
    assert shutdown_requests == [True]
