"""Application factory for Flask + Peewee template layout."""

import logging

from flask import Flask

from app.database import close_db, connect_db, init_db
from app.routes import register_routes

__version__ = "1.0.0"
__author__ = "OmniGuard Team"

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev",
    )

    init_db(app)
    register_routes(app)

    @app.before_request
    def _connect() -> None:
        try:
            connect_db()
        except Exception as exc:  # pragma: no cover - safety guard
            logger.warning("Database connect skipped for request: %s", exc)

    @app.teardown_appcontext
    def _close(_exc: object) -> None:
        try:
            close_db()
        except Exception:
            pass

    return app
