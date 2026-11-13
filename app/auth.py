from datetime import datetime, timezone
from flask import Blueprint, current_app, flash, redirect, url_for, session
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy.exc import IntegrityError
from .extensions import db, oauth
from .models import User

bp = Blueprint("auth", __name__)


@bp.get("/google")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if not (current_app.config.get("GOOGLE_CLIENT_ID") and current_app.config.get("GOOGLE_CLIENT_SECRET")):
        flash("Google sign-in is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to the environment.", "warning")
        return redirect(url_for("main.index"))
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI") or url_for(
        "auth.google_callback", _external=True
    )
    if current_app.config.get("ENV_NAME") == "production" and not current_app.config.get("GOOGLE_REDIRECT_URI"):
        flash("Set an explicit HTTPS GOOGLE_REDIRECT_URI before enabling Google sign-in in production.", "error")
        return redirect(url_for("main.index"))
    return oauth.google.authorize_redirect(redirect_uri)


@bp.get("/google/callback")
def google_callback():
    if not (current_app.config.get("GOOGLE_CLIENT_ID") and current_app.config.get("GOOGLE_CLIENT_SECRET")):
        flash("Google sign-in is not configured.", "warning")
        return redirect(url_for("main.index"))

    try:
        token = oauth.google.authorize_access_token()
        profile = token.get("userinfo") or oauth.google.userinfo(token=token)
        if not profile:
            raise ValueError("Google did not return a verified user profile.")

        google_sub = str(profile.get("sub", "")).strip()
        email = str(profile.get("email", "")).strip().lower()
        email_verified = profile.get("email_verified") is True or str(
            profile.get("email_verified", "")
        ).lower() == "true"
        if not google_sub or not email or not email_verified:
            raise ValueError("A verified Google email address is required.")

        user = User.query.filter_by(google_sub=google_sub).first()
        if user is None:
            # Linking is only permitted when Google asserts that the email is verified.
            user = User.query.filter_by(email=email).first()
            if user is not None:
                user.google_sub = google_sub
                user.email_verified = True
            else:
                user = User(
                    google_sub=google_sub,
                    email=email,
                    full_name=(profile.get("name") or email.split("@")[0])[:160],
                    avatar_url=profile.get("picture"),
                    email_verified=True,
                )
                db.session.add(user)

        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()

        # Discard temporary OAuth state before creating the authenticated session.
        session.clear()
        login_user(user, remember=False, fresh=True)
        session.permanent = True
        return redirect(url_for("main.dashboard"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Google OAuth callback failed")
        flash("Google sign-in could not be completed. Please try again.", "error")
        return redirect(url_for("main.index"))


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("main.index"))
