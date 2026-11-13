
    
  
from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, Index
from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    google_sub = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(320), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    avatar_url = db.Column(db.String(1000))
    avatar_file = db.Column(db.String(255))
    display_name = db.Column(db.String(48))
    theme = db.Column(db.String(12), nullable=False, default="dark", server_default="dark")
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    watchlist_items = db.relationship(
        "WatchlistItem", back_populates="user", cascade="all, delete-orphan"
    )
    assessments = db.relationship(
        "RiskAssessment", back_populates="user", cascade="all, delete-orphan"
    )
    portfolio_runs = db.relationship(
        "PortfolioRun", back_populates="user", cascade="all, delete-orphan"
    )
    watchlists = db.relationship(
        "SavedWatchlist", back_populates="user", cascade="all, delete-orphan",
        order_by="SavedWatchlist.created_at.asc()"
    )


class WatchlistItem(db.Model):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = db.Column(db.String(24), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    user = db.relationship("User", back_populates="watchlist_items")


class RiskAssessment(db.Model):
    __tablename__ = "risk_assessments"
    __table_args__ = (Index("ix_assessment_user_created", "user_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    risk_category = db.Column(db.String(32), nullable=False)
    probability_by_class = db.Column(db.JSON, nullable=False)
    input_snapshot = db.Column(db.JSON, nullable=False)
    model_version = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    user = db.relationship("User", back_populates="assessments")


class PortfolioRun(db.Model):
    __tablename__ = "portfolio_runs"
    __table_args__ = (Index("ix_portfolio_user_created", "user_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbols = db.Column(db.JSON, nullable=False)
    weights = db.Column(db.JSON, nullable=False)
    risk_category = db.Column(db.String(32), nullable=False)
    statistics = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    user = db.relationship("User", back_populates="portfolio_runs")


class SavedWatchlist(db.Model):
    __tablename__ = "saved_watchlists"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_watchlist_user_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    symbols = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    user = db.relationship("User", back_populates="watchlists")


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

