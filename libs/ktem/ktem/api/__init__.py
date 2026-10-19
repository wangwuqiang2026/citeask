"""API router registration.

``app.py`` owns the FastAPI host and calls :func:`install_routes` while building
it. The ``files`` router is optional at import time so the core API can be tested
before the file-management endpoints land.
"""

from __future__ import annotations

from fastapi import FastAPI


def install_routes(api: FastAPI) -> None:
    from . import (
        auth,
        chat,
        conversations,
        help,
        meta,
        resources,
        settings,
        users,
    )

    for module in (
        auth,
        meta,
        conversations,
        chat,
        settings,
        users,
        resources,
        help,
    ):
        api.include_router(module.router, prefix="/api/v1")

    try:
        from . import files

        api.include_router(files.router, prefix="/api/v1")
    except ImportError:
        # the file-management router is developed separately; the rest of the
        # API must stay importable without it (tests, partial deployments)
        pass


__all__ = ["install_routes"]
