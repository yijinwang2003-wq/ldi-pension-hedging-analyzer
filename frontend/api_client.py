"""Shared frontend helpers for calling the FastAPI backend."""

from __future__ import annotations

import requests


REQUEST_TIMEOUT_SECONDS = 60


def backend_health_url(api_base_url: str) -> str:
    """Return the backend root health-check URL for an API base URL."""
    normalized_url = api_base_url.rstrip("/")
    if normalized_url.endswith("/api"):
        return normalized_url[: -len("/api")]
    return normalized_url


def warm_up_backend(api_base_url: str) -> None:
    """Call the backend health endpoint before a calculation request."""
    response = requests.get(
        backend_health_url(api_base_url),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def post_api_json(
    api_base_url: str,
    path: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """POST JSON to a backend API path and return JSON data."""
    response = requests.post(
        f"{api_base_url.rstrip('/')}/{path.lstrip('/')}",
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def render_backend_error(action: str, exc: requests.RequestException) -> str:
    """Return a user-facing backend error message for Streamlit pages."""
    return (
        f"Unable to {action}. The Render backend may be waking up, which can "
        "take up to a minute after a period of inactivity. Please retry in "
        f"30-60 seconds if the first request fails. Details: {exc}"
    )
