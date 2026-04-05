"""Route registration module."""


def register_routes(app) -> None:
    """Register all blueprints on the Flask app."""
    from app.routes.health import health_bp
    from app.routes.entities import entities_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(entities_bp)
