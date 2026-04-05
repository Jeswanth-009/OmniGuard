"""Entry point for Flask + Peewee template app."""

import os

from dotenv import load_dotenv

from app import create_app

load_dotenv()


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app.run(host=host, port=port, debug=debug)
