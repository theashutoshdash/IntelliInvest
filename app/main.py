from __future__ import annotations

import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import (Blueprint, current_app, flash, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_login import current_user, login_required
from sqlalchemy import desc, text
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import PortfolioRun, RiskAssessment, SavedWatchlist, WatchlistItem
from .services.market_data import (index_series, market_clock, market_snapshot,
                                   quotes_for_symbols)
from .services.portfolio_optimizer import STRATEGIC_ALLOCATIONS, optimize_portfolio
from .services.news_data import get_market_news
from .services.return_forecaster import forecast_return
from .services.risk_engine import assess_investor, evaluation_metrics
from .services.stock_recommendations import recommend_stocks
from .services.universe_lists import BUILTIN_WATCHLISTS

bp = Blueprint("main", __name__)
UNIVERSE_PATH = Path(__file__).resolve().parents[1] / "data" / "nse_universe.json"
try:
    with UNIVERSE_PATH.open(encoding="utf-8") as source:
        NSE_UNIVERSE = json.load(source)
except (OSError, json.JSONDecodeError):
    NSE_UNIVERSE = {}


def _latest_risk_assessment():
    return RiskAssessment.query.filter_by(user_id=current_user.id).order_by(
        desc(RiskAssessment.created_at)
    ).first()


def _normalise_watchlist_symbol(raw: str) -> str:
    symbol = raw.strip().upper()
    if symbol.endswith(".NS"):
        symbol = symbol[:-3]
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9&_-]{0,19}", symbol):
        raise ValueError("Enter a valid NSE ticker, for example RELIANCE or HDFCBANK.")
    return symbol


def _ensure_default_watchlist() -> SavedWatchlist:
    default = SavedWatchlist.query.filter_by(user_id=current_user.id, name="My Watchlist").first()
    if default:
        return default
    legacy = WatchlistItem.query.filter_by(user_id=current_user.id).order_by(WatchlistItem.created_at.asc()).all()
    default = SavedWatchlist(user_id=current_user.id, name="My Watchlist",
                             symbols=list(dict.fromkeys(item.symbol for item in legacy)))
    db.session.add(default)
    db.session.commit()
    return default


def _watchlist_count() -> int:
    lists = SavedWatchlist.query.filter_by(user_id=current_user.id).all()
    total = sum(len(item.symbols or []) for item in lists)
    if total == 0:
        total = WatchlistItem.query.filter_by(user_id=current_user.id).count()
    return total


def _watchlist_name_map():
    return {symbol: name for name, symbol in NSE_UNIVERSE.items()}


def _safe_list_name(raw: str) -> str:
    name = " ".join((raw or "").split()).strip()
    if not 2 <= len(name) <= 64:
        raise ValueError("A watchlist name must contain between 2 and 64 characters.")
    return name


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("login.html")


@bp.get("/dashboard")
@login_required
def dashboard():
    latest = _latest_risk_assessment()
    watchlist_count = _watchlist_count()
    portfolio_count = PortfolioRun.query.filter_by(user_id=current_user.id).count()
    recent_runs = PortfolioRun.query.filter_by(user_id=current_user.id).order_by(
        desc(PortfolioRun.created_at)
    ).limit(3).all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        chart_future = pool.submit(index_series, "^NSEI", "1y")
        news_future = pool.submit(get_market_news)
        chart = chart_future.result()
        news = news_future.result()
    if chart:
        chart["name"] = "NIFTY 50"
        chart["symbol"] = "NIFTY50"
    return render_template(
        "dashboard.html", index_chart=chart,
        latest_assessment=latest, watchlist_count=watchlist_count,
        portfolio_count=portfolio_count, recent_runs=recent_runs, news=news,
    )


@bp.route("/predictor", methods=["GET", "POST"])
@login_required
def predictor():
    result = None
    form_data = {"age": "", "income": "", "horizon": "", "loss_tolerance": "", "experience": "0"}
    if request.method == "POST":
        form_data.update({key: request.form.get(key, "") for key in form_data})
        try:
            result = assess_investor(form_data)
            result["recommendations"] = recommend_stocks(result["risk_category"])
            assessment = RiskAssessment(
                user_id=current_user.id,
                risk_category=result["risk_category"],
                probability_by_class=result["probabilities"],
                input_snapshot=result["inputs"],
                model_version=result["model_version"],
            )
            db.session.add(assessment)
            db.session.commit()
            result["assessment_id"] = assessment.id
            flash("Your updated risk profile is saved.", "success")
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Risk assessment failed")
            flash("Assessment could not be completed. Please retry.", "error")
    return render_template("predictor.html", result=result, form_data=form_data)


@bp.route("/portfolio", methods=["GET", "POST"])
@login_required
def portfolio():
    latest = _latest_risk_assessment()
    risk_category = request.values.get("risk_category") or (latest.risk_category if latest else "Moderate")
    if risk_category not in STRATEGIC_ALLOCATIONS:
        risk_category = "Moderate"
    optimisation = None
    symbols = request.form.get("symbols", "RELIANCE,HDFCBANK,INFY,TCS,ITC,BHARTIARTL") if request.method == "POST" else "RELIANCE,HDFCBANK,INFY,TCS,ITC,BHARTIARTL"
    if request.method == "POST":
        try:
            optimisation = optimize_portfolio(symbols, risk_category, period="3y")
            run = PortfolioRun(
                user_id=current_user.id,
                symbols=[row["symbol"] for row in optimisation["allocations"]],
                weights={row["symbol"]: row["weight"] for row in optimisation["allocations"]},
                risk_category=risk_category,
                statistics={
                    "historical_tail_loss": optimisation["historical_tail_loss"],
                    "historical_cvar": optimisation["historical_cvar"],
                    "historical_var": optimisation["historical_var"],
                    "annualised_historical_return": optimisation["annualised_historical_return"],
                    "annualised_volatility": optimisation["annualised_volatility"],
                    "observations": optimisation["observations"],
                    "method": optimisation["method"],
                },
            )
            db.session.add(run)
            db.session.commit()
            flash("Portfolio weights calculated and saved.", "success")
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Portfolio optimisation failed")
            flash("The portfolio calculation failed. Market data may be unavailable.", "error")
    return render_template("portfolio.html", risk_category=risk_category,
                           optimisation=optimisation, symbols=symbols, stock_universe=NSE_UNIVERSE)


@bp.route("/return-predict", methods=["GET", "POST"])
@login_required
def return_predict():
    result = None
    symbol = request.form.get("symbol", "RELIANCE").strip().upper() if request.method == "POST" else request.args.get("symbol", "RELIANCE").strip().upper()
    period = request.form.get("period", "3y") if request.method == "POST" else request.args.get("period", "3y")
    if request.method == "POST":
        try:
            result = forecast_return(symbol, period)
        except ValueError as error:
            flash(str(error), "error")
        except Exception:
            current_app.logger.exception("Return forecast failed")
            flash("The research run could not be completed. Please retry.", "error")
    return render_template("return_predict.html", result=result, symbol=symbol, period=period)


@bp.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    lists = SavedWatchlist.query.filter_by(user_id=current_user.id).order_by(SavedWatchlist.created_at.asc()).all()
    if not lists:
        _ensure_default_watchlist()
        lists = SavedWatchlist.query.filter_by(user_id=current_user.id).order_by(SavedWatchlist.created_at.asc()).all()

    if request.method == "POST":
        action = request.form.get("action", "add")
        try:
            if action == "create":
                name = _safe_list_name(request.form.get("name", ""))
                new_list = SavedWatchlist(user_id=current_user.id, name=name, symbols=[])
                db.session.add(new_list)
                db.session.commit()
                flash("Watchlist created.", "success")
                return redirect(url_for("main.watchlist", view=new_list.id))
            if action == "clone":
                slug = request.form.get("slug", "")
                preset = BUILTIN_WATCHLISTS.get(slug)
                if not preset:
                    raise ValueError("Choose a valid predefined watchlist.")
                base_name = preset["name"].split(" · ")[0]
                name = f"{base_name} Copy"
                suffix = 2
                while SavedWatchlist.query.filter_by(user_id=current_user.id, name=name).first():
                    name = f"{base_name} Copy {suffix}"
                    suffix += 1
                new_list = SavedWatchlist(user_id=current_user.id, name=name, symbols=preset["symbols"][:])
                db.session.add(new_list)
                db.session.commit()
                flash("Predefined universe copied to your lists. You can edit it now.", "success")
                return redirect(url_for("main.watchlist", view=new_list.id))
            if action in {"add", "remove", "rename", "delete"}:
                list_id = int(request.form.get("list_id", "0"))
                selected = SavedWatchlist.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
                if action == "add":
                    symbol = _normalise_watchlist_symbol(request.form.get("symbol", ""))
                    current_symbols = list(selected.symbols or [])
                    if symbol in current_symbols:
                        flash(f"{symbol} is already in this list.", "info")
                    else:
                        current_symbols.append(symbol)
                        selected.symbols = current_symbols
                        db.session.commit()
                        flash(f"{symbol} added.", "success")
                elif action == "remove":
                    symbol = _normalise_watchlist_symbol(request.form.get("symbol", ""))
                    selected.symbols = [item for item in (selected.symbols or []) if item != symbol]
                    db.session.commit()
                    flash(f"{symbol} removed.", "success")
                elif action == "rename":
                    selected.name = _safe_list_name(request.form.get("name", ""))
                    db.session.commit()
                    flash("Watchlist renamed.", "success")
                elif action == "delete":
                    if selected.name == "My Watchlist":
                        raise ValueError("The default watchlist cannot be deleted.")
                    db.session.delete(selected)
                    db.session.commit()
                    selected = _ensure_default_watchlist()
                    flash("Watchlist deleted.", "success")
                    return redirect(url_for("main.watchlist", view=selected.id))
                return redirect(url_for("main.watchlist", view=selected.id))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")
        except IntegrityError:
            db.session.rollback()
            flash("A watchlist with that name already exists.", "error")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Watchlist update failed")
            flash("Watchlist could not be updated.", "error")
        return redirect(url_for("main.watchlist"))

    view = request.args.get("view", "")
    builtin = BUILTIN_WATCHLISTS.get(view)
    current_list = None
    if builtin:
        symbols = builtin["symbols"]
        view_type = "builtin"
    else:
        try:
            requested_id = int(view) if view else lists[0].id
        except ValueError:
            requested_id = lists[0].id
        current_list = next((item for item in lists if item.id == requested_id), None) or lists[0]
        symbols = list(current_list.symbols or [])
        view_type = "custom"
    name_by_symbol = _watchlist_name_map()
    names = [name_by_symbol.get(symbol, symbol) for symbol in symbols]
    quotes = quotes_for_symbols(symbols, names)
    rows = [{"symbol": symbol, "name": names[index], "quote": quotes[index]} for index, symbol in enumerate(symbols)]
    return render_template("watchlist.html", rows=rows, lists=lists, current_list=current_list,
                           builtin=builtin, builtin_lists=BUILTIN_WATCHLISTS,
                           view=view, view_type=view_type, stock_universe=NSE_UNIVERSE)


@bp.get("/api/watchlist")
@login_required
def api_watchlist():
    view = request.args.get("view", "")
    builtin = BUILTIN_WATCHLISTS.get(view)
    if builtin:
        symbols = builtin["symbols"]
    else:
        try:
            selected = SavedWatchlist.query.filter_by(id=int(view), user_id=current_user.id).first()
        except ValueError:
            selected = None
        if selected is None:
            selected = _ensure_default_watchlist()
        symbols = list(selected.symbols or [])
    return jsonify(quotes_for_symbols(symbols))


@bp.get("/evaluation")
@login_required
def evaluation():
    try:
        metrics = evaluation_metrics()
    except Exception:
        current_app.logger.exception("Model evaluation failed")
        metrics = {"error": "Model evaluation is unavailable. Check the investor dataset."}
    system_status = {"database": "Unknown", "dataset": "Missing", "market_data": "External provider"}
    try:
        db.session.execute(text("SELECT 1"))
        system_status["database"] = "Connected"
    except Exception:
        system_status["database"] = "Unavailable"
        db.session.rollback()
    investor_dataset = Path(__file__).resolve().parents[1] / "data" / "investor_profiles.csv"
    system_status["dataset"] = "Available" if investor_dataset.exists() and UNIVERSE_PATH.exists() else "Incomplete"
    system_status["market_data"] = "Yahoo Finance · retry + cached fallback"
    return render_template("evaluation.html", metrics=metrics, system_status=system_status)


@bp.get("/profile")
@login_required
def profile():
    assessments = RiskAssessment.query.filter_by(user_id=current_user.id).order_by(
        desc(RiskAssessment.created_at)
    ).limit(10).all()
    portfolio_runs = PortfolioRun.query.filter_by(user_id=current_user.id).order_by(
        desc(PortfolioRun.created_at)
    ).limit(10).all()
    return render_template("profile.html", assessments=assessments, portfolio_runs=portfolio_runs,
                           watchlist_count=_watchlist_count())


@bp.post("/profile/settings")
@login_required
def profile_settings():
    display_name = " ".join((request.form.get("display_name") or "").split()).strip()
    theme = request.form.get("theme", "dark")
    if not 2 <= len(display_name) <= 48:
        flash("Display name must contain between 2 and 48 characters.", "error")
    elif theme not in {"dark", "light"}:
        flash("Choose a valid appearance setting.", "error")
    else:
        current_user.display_name = display_name
        current_user.theme = theme
        db.session.commit()
        flash("Profile preferences saved.", "success")
    return redirect(url_for("main.profile"))


@bp.post("/profile/avatar")
@login_required
def profile_avatar_upload():
    upload = request.files.get("avatar")
    if not upload or not upload.filename:
        flash("Choose a profile image first.", "error")
        return redirect(url_for("main.profile"))
    payload = upload.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        flash("Profile image must be 2 MB or smaller.", "error")
        return redirect(url_for("main.profile"))
    signatures = {
        ".jpg": payload.startswith(b"\xff\xd8\xff"),
        ".jpeg": payload.startswith(b"\xff\xd8\xff"),
        ".png": payload.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": payload[:4] == b"RIFF" and payload[8:12] == b"WEBP",
    }
    extension = Path(upload.filename).suffix.lower()
    if not signatures.get(extension, False):
        flash("Use a valid JPG, PNG or WebP image.", "error")
        return redirect(url_for("main.profile"))
    folder = Path(current_app.config["PROFILE_UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"user-{current_user.id}-{uuid.uuid4().hex[:12]}{extension}"
    (folder / filename).write_bytes(payload)
    old_file = current_user.avatar_file
    current_user.avatar_file = filename
    db.session.commit()
    if old_file:
        try:
            (folder / old_file).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Could not remove previous profile photo")
    flash("Profile photo updated.", "success")
    return redirect(url_for("main.profile"))


@bp.get("/profile/avatar/<path:filename>")
@login_required
def profile_avatar(filename):
    if filename != current_user.avatar_file:
        return "Not found", 404
    return send_from_directory(current_app.config["PROFILE_UPLOAD_FOLDER"], filename)


@bp.get("/api/market-overview")
def market_overview():
    return jsonify({"quotes": market_snapshot(), "clock": market_clock()})


@bp.get("/api/market-clock")
def market_clock_api():
    return jsonify(market_clock())


@bp.get("/api/index-chart")
@login_required
def api_index_chart():
    period = request.args.get("period", "1y")
    symbol_key = request.args.get("symbol", "NIFTY50").upper()

    indices = {
        "NIFTY50": ("^NSEI", "NIFTY 50"),
        "NIFTYBANK": ("^NSEBANK", "NIFTY BANK"),
        "SENSEX": ("^BSESN", "SENSEX"),
    }

    selected = indices.get(symbol_key)

    if not selected:
        return jsonify({"error": "Unsupported index"}), 400

    series = index_series(selected[0], period)

    if series is None:
        return jsonify({"error": "Market data unavailable"}), 503

    series["symbol"] = symbol_key
    series["name"] = selected[1]

    return jsonify(series)


@bp.get("/api/system-status")
@login_required
def api_system_status():
    checks = {"database": False, "risk_dataset": UNIVERSE_PATH.exists(), "market_data": "external"}
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        db.session.rollback()
    return jsonify(checks)


@bp.get("/api/news")
@login_required
def api_news():
    return jsonify(get_market_news(limit=10))
