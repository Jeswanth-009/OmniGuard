"""Peewee database wiring with DatabaseProxy for app factory usage."""

import os

from peewee import DatabaseProxy, Model, PostgresqlDatabase

# Database proxy lets models import BaseModel before DB is initialized.
db = DatabaseProxy()


class BaseModel(Model):
    """Base model bound to the shared database proxy."""

    class Meta:
        database = db


def _build_database() -> PostgresqlDatabase:
    """Create PostgreSQL database instance from environment variables."""
    return PostgresqlDatabase(
        os.getenv("DATABASE_NAME", "hackathon_db"),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
    )


def init_db(app) -> None:
    """Initialize database proxy and app config defaults."""
    app.config.setdefault("DATABASE_NAME", os.getenv("DATABASE_NAME", "hackathon_db"))
    app.config.setdefault("DATABASE_USER", os.getenv("DATABASE_USER", "postgres"))
    app.config.setdefault("DATABASE_PASSWORD", os.getenv("DATABASE_PASSWORD", "postgres"))
    app.config.setdefault("DATABASE_HOST", os.getenv("DATABASE_HOST", "localhost"))
    app.config.setdefault("DATABASE_PORT", int(os.getenv("DATABASE_PORT", "5432")))

    db.initialize(_build_database())


def connect_db() -> None:
    """Open connection if closed."""
    if db.obj is not None and db.is_closed():
        db.connect(reuse_if_open=True)


def close_db() -> None:
    """Close connection at request teardown."""
    if db.obj is not None and not db.is_closed():
        db.close()
