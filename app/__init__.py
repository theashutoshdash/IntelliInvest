import os
from pathlib import Path
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from .extensions import csrf, db, login_manager, migrate, oauth


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if os.environ.get("VERCEL"):
        app.instance_path = "/tmp/instance"
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    configured_secret = os.getenv("SECRET_KEY", "")
    if app.config.get("ENV_NAME") == "production" and (
        len(configured_secret) < 32 or configured_secret.startswith("replace-with")
        or "development-only" in configured_secret
    ):
        raise RuntimeError("Set a strong SECRET_KEY before running in production.")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    from . import models  # noqa: F401 - registers models with SQLAlchemy
    from .auth import bp as auth_bp
    from .main import bp as main_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        app.logger.exception("Unhandled application error")
        return render_template("errors/500.html"), 500

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "intellinvest"}, 200

    if app.config.get("AUTO_CREATE_DB"):
        with app.app_context():
            db.create_all()

    return app
