from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def create_http_client(base_url: str | None = None, verify: bool | str = True) -> httpx.Client:
    """
    Shared HTTP client with sane defaults.
    Add retry/backoff middleware per broker requirements as implementation evolves.
    """
    return httpx.Client(
        base_url=base_url or "",
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=verify,
    )
