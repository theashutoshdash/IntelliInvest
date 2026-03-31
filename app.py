import os
import json
import numpy as np
import pandas as pd
import joblib
import plotly
import plotly.graph_objects as go
import yfinance as yf
from types import SimpleNamespace

from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash)
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (accuracy_score, precision_score,
                              recall_score, classification_report,
                              confusion_matrix)

# ─────────────────────────────────────────────────────────────────────────
#  APP CONFIG
# ─────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "intellinvest_secret_key_2026"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# ─────────────────────────────────────────────────────────────────────────
#  NSE STOCK UNIVERSE
# ─────────────────────────────────────────────────────────────────────────
NSE_TOP_250 = {
    "Reliance Industries": "RELIANCE", "Tata Consultancy Services": "TCS",
    "HDFC Bank": "HDFCBANK", "Infosys": "INFY", "ICICI Bank": "ICICIBANK",
    "State Bank of India": "SBIN", "Hindustan Unilever": "HINDUNILVR",
    "ITC": "ITC", "Bharti Airtel": "BHARTIARTL", "Kotak Mahindra Bank": "KOTAKBANK",
    "Wipro": "WIPRO", "HCL Technologies": "HCLTECH", "Axis Bank": "AXISBANK",
    "Larsen & Toubro": "LT", "Bajaj Finance": "BAJFINANCE",
    "Asian Paints": "ASIANPAINT", "Maruti Suzuki": "MARUTI",
    "Sun Pharmaceuticals": "SUNPHARMA", "Titan Company": "TITAN",
    "Ultratech Cement": "ULTRACEMCO", "Tech Mahindra": "TECHM",
    "NTPC": "NTPC", "Power Grid Corporation": "POWERGRID",
    "Bajaj Auto": "BAJAJ-AUTO", "Nestle India": "NESTLEIND",
    "Mahindra & Mahindra": "M&M", "JSW Steel": "JSWSTEEL",
    "Tata Steel": "TATASTEEL", "Adani Ports": "ADANIPORTS",
    "Adani Enterprises": "ADANIENT", "Adani Green Energy": "ADANIGREEN",
    "Adani Power": "ADANIPOWER", "Cipla": "CIPLA",
    "Dr Reddys Laboratories": "DRREDDY", "Divi's Laboratories": "DIVISLAB",
    "Grasim Industries": "GRASIM", "Hindalco Industries": "HINDALCO",
    "IndusInd Bank": "INDUSINDBK", "Bajaj Finserv": "BAJAJFINSV",
    "Britannia Industries": "BRITANNIA", "Coal India": "COALINDIA",
    "Eicher Motors": "EICHERMOT", "Hero MotoCorp": "HEROMOTOCO",
    "Tata Motors": "TATAMOTORS", "Tata Power": "TATAPOWER",
    "Tata Consumer Products": "TATACONSUM", "Havells India": "HAVELLS",
    "Pidilite Industries": "PIDILITIND", "SBI Life Insurance": "SBILIFE",
    "HDFC Life Insurance": "HDFCLIFE", "ICICI Prudential Life": "ICICIPRULI",
    "ICICI Lombard": "ICICIGI", "Shree Cement": "SHREECEM",
    "Ambuja Cements": "AMBUJACEM", "ACC": "ACC",
    "Godrej Consumer Products": "GODREJCP", "Dabur India": "DABUR",
    "Marico": "MARICO", "Colgate-Palmolive India": "COLPAL",
    "Trent": "TRENT", "Avenue Supermarts (DMart)": "DMART",
    "Zomato": "ZOMATO", "LIC of India": "LICI",
    "Vedanta": "VEDL", "Oil & Natural Gas Corp": "ONGC",
    "BPCL": "BPCL", "Indian Oil Corporation": "IOC",
    "HPCL": "HINDPETRO", "Gail India": "GAIL",
    "Bharat Electronics": "BEL", "HAL": "HAL",
    "IRCTC": "IRCTC", "IRFC": "IRFC", "RVNL": "RVNL",
    "Zydus Lifesciences": "ZYDUSLIFE", "Lupin": "LUPIN",
    "Torrent Pharma": "TORNTPHARM", "Apollo Hospitals": "APOLLOHOSP",
    "Max Healthcare": "MAXHEALTH", "Polycab India": "POLYCAB",
    "Torrent Power": "TORNTPOWER", "JSW Energy": "JSWENERGY",
    "Jubilant FoodWorks": "JUBLFOOD", "Indian Hotels": "INDHOTEL",
    "InterGlobe Aviation (Indigo)": "INDIGO", "Delhivery": "DELHIVERY",
    "Mphasis": "MPHASIS", "LTIMindtree": "LTIM",
    "Persistent Systems": "PERSISTENT", "Coforge": "COFORGE",
    "KPIT Technologies": "KPITTECH", "Tata Elxsi": "TATAELXSI",
    "Oracle Financial Services": "OFSS", "Muthoot Finance": "MUTHOOTFIN",
    "Cholamandalam Finance": "CHOLAFIN", "Shriram Finance": "SHRIRAMFIN",
    "IDFC First Bank": "IDFCFIRSTB", "Federal Bank": "FEDERALBNK",
    "Yes Bank": "YESBANK", "Bank of Baroda": "BANKBARODA",
    "Punjab National Bank": "PNB", "Canara Bank": "CANBK",
    "Union Bank of India": "UNIONBANK", "Bandhan Bank": "BANDHANBNK",
    "AU Small Finance Bank": "AUBANK", "Steel Authority of India": "SAIL",
    "NMDC": "NMDC", "Tata Chemicals": "TATACHEM",
    "Deepak Nitrite": "DEEPAKNTR", "SRF": "SRF",
    "PI Industries": "PIIND", "UPL": "UPL",
    "Tata Communications": "TATACOMM", "Indus Towers": "INDUSTOWER",
    "Bharat Dynamics": "BDL", "Mazagon Dock Shipbuilders": "MAZDOCK",
    "PFC": "PFC", "REC Limited": "RECLTD", "NHPC": "NHPC",
    "Suzlon Energy": "SUZLON", "Bosch": "BOSCHLTD",
    "Motherson Sumi": "MOTHERSON", "Dixon Technologies": "DIXON",
    "ABB India": "ABB", "Siemens India": "SIEMENS",
    "Thermax": "THERMAX", "Bharat Heavy Electricals": "BHEL",
    "CG Power": "CGPOWER", "KEC International": "KEC",
    "Dalmia Bharat": "DALBHARAT", "PVR Inox": "PVRINOX",
    "IndiaMart InterMesh": "INDIAMART", "Info Edge (Naukri)": "NAUKRI",
    "Paytm": "PAYTM", "Nykaa": "NYKAA", "PB Fintech": "POLICYBZR",
}

# ─────────────────────────────────────────────────────────────────────────
#  AUTO-GENERATE investor_data.csv  (if missing)
# ─────────────────────────────────────────────────────────────────────────
DATA_PATH = "investor_data.csv"
if not os.path.exists(DATA_PATH):
    np.random.seed(42)
    n = 600
    ages      = np.random.randint(22, 65, n)
    incomes   = np.random.randint(300_000, 5_000_000, n)
    horizons  = np.random.randint(1, 35, n)
    loss_tols = np.random.randint(5, 50, n)
    exps      = np.random.randint(0, 3, n)
    risk_types = []
    for i in range(n):
        sc = 0
        if ages[i] < 35:           sc += 2
        elif ages[i] < 50:         sc += 1
        if incomes[i] > 2_000_000: sc += 2
        elif incomes[i] > 800_000: sc += 1
        if horizons[i] > 15:       sc += 2
        elif horizons[i] > 7:      sc += 1
        if loss_tols[i] > 30:      sc += 2
        elif loss_tols[i] > 15:    sc += 1
        if exps[i] == 2:           sc += 2
        elif exps[i] == 1:         sc += 1
        risk_types.append(
            "Aggressive" if sc >= 7 else ("Moderate" if sc >= 4 else "Conservative")
        )
    pd.DataFrame({
        "age": ages, "income": incomes, "horizon": horizons,
        "loss_tolerance": loss_tols, "experience": exps,
        "risk_type": risk_types,
    }).to_csv(DATA_PATH, index=False)
    print("[INFO] Auto-generated investor_data.csv")

# ─────────────────────────────────────────────────────────────────────────
#  AUTO-TRAIN risk_model.pkl  (Decision Tree Classifier)
# ─────────────────────────────────────────────────────────────────────────
MODEL_PATH = "risk_model.pkl"
model = None
if not os.path.exists(MODEL_PATH):
    try:
        _df  = pd.read_csv(DATA_PATH)
        _X   = _df[["age", "income", "horizon", "loss_tolerance", "experience"]]
        _y   = _df["risk_type"]
        _clf = DecisionTreeClassifier(random_state=42)
        _clf.fit(_X, _y)
        joblib.dump(_clf, MODEL_PATH)
        model = _clf
        print("[INFO] Trained & saved risk_model.pkl")
    except Exception as _e:
        print(f"[ERROR] Could not train risk model: {_e}")
else:
    try:
        model = joblib.load(MODEL_PATH)
    except Exception as _e:
        print(f"[WARNING] Could not load risk_model.pkl: {_e}")

# ─────────────────────────────────────────────────────────────────────────
#  AUTO-TRAIN cluster_model.pkl  (K-Means)
# ─────────────────────────────────────────────────────────────────────────
CLUSTER_MODEL_PATH = "cluster_model.pkl"
cluster_bundle = None
if not os.path.exists(CLUSTER_MODEL_PATH):
    try:
        _df = pd.read_csv(DATA_PATH)
        _rm = {"Conservative": 0, "Moderate": 1, "Aggressive": 2}
        _df["risk_score"] = _df["risk_type"].map(_rm)
        _Xc = _df[["age", "income", "horizon", "loss_tolerance", "risk_score"]].values
        _sc = StandardScaler()
        _Xs = _sc.fit_transform(_Xc)
        _km = KMeans(n_clusters=3, random_state=42, n_init=10)
        _km.fit(_Xs)
        _cents  = _sc.inverse_transform(_km.cluster_centers_)
        _sorted = sorted(enumerate(_cents[:, 0]), key=lambda x: x[1])
        _label_map = {
            _sorted[0][0]: "Young Aggressive Investor",
            _sorted[1][0]: "Mid-Age Balanced Investor",
            _sorted[2][0]: "Retired Conservative Investor",
        }
        cluster_bundle = {"model": _km, "scaler": _sc, "label_map": _label_map}
        joblib.dump(cluster_bundle, CLUSTER_MODEL_PATH)
        print("[INFO] Trained & saved cluster_model.pkl")
    except Exception as _e:
        print(f"[ERROR] Could not train cluster model: {_e}")
else:
    try:
        cluster_bundle = joblib.load(CLUSTER_MODEL_PATH)
    except Exception as _e:
        print(f"[WARNING] Could not load cluster_model.pkl: {_e}")

# ─────────────────────────────────────────────────────────────────────────
#  AUTH DECORATOR  +  CONTEXT PROCESSOR
# ─────────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_globals():
    """
    Wraps the session username into an object so templates can call
    current_user.username  and  current_user.username[0].upper()
    without errors.
    """
    username = session.get("username")
    if username:
        return {"current_user": SimpleNamespace(username=username)}
    return {"current_user": None}

# ─────────────────────────────────────────────────────────────────────────
#  MARKET / CHART HELPERS
# ─────────────────────────────────────────────────────────────────────────
def get_market_data():
    tickers = {
        "Reliance": "RELIANCE.NS", "TCS": "TCS.NS",    "HDFC": "HDFCBANK.NS",
        "ICICI":    "ICICIBANK.NS","Infosys": "INFY.NS","ITC": "ITC.NS",
        "SBI":      "SBIN.NS",     "Airtel": "BHARTIARTL.NS",
        "Kotak":    "KOTAKBANK.NS","HUL": "HINDUNILVR.NS",
    }
    market = []
    for name, sym in tickers.items():
        try:
            data = yf.Ticker(sym).history(period="1d")
            if data.empty:
                continue
            price      = round(data["Close"].iloc[-1], 2)
            open_price = round(data["Open"].iloc[-1], 2)
            change     = price - open_price
            change_pct = round((change / open_price) * 100, 2) if open_price else 0
            market.append({
                "name": name, "price": price, "change": change_pct,
                "color": "up" if change > 0 else "dn"
            })
        except Exception:
            continue
    return market

def get_nifty_chart():
    try:
        data = yf.Ticker("^NSEI").history(period="1y", interval="1d").dropna()
        fig  = go.Figure()
        fig.add_trace(go.Candlestick(
            x=data.index, open=data["Open"], high=data["High"],
            low=data["Low"],  close=data["Close"],
            increasing_line_color="#00ff9c",
            decreasing_line_color="#ff4d4d",
        ))
        fig.update_layout(
            template="plotly_dark", height=500,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=30, b=10),
        )
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    except Exception as e:
        print(f"[ERROR] NIFTY chart: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────
#  ML HELPERS  — predict_return must be defined BEFORE
#                get_portfolio_recommendation & get_evaluation_metrics
# ─────────────────────────────────────────────────────────────────────────
def get_layman_summary(predicted_return, r2, beta, week52_pos, mse, sector):
    if predicted_return >= 2.0:
        verdict, verdict_color = "Strong Buy Signal", "green"
        pred_line = f"Strong upward momentum. A gain of ~{predicted_return:.2f}% is expected."
    elif predicted_return >= 0.5:
        verdict, verdict_color = "Mild Positive Outlook", "green"
        pred_line = f"Gentle positive momentum. A modest gain of ~{predicted_return:.2f}% is expected."
    elif predicted_return >= -0.5:
        verdict, verdict_color = "Sideways / Neutral", "gold"
        pred_line = f"Likely to stay flat, moving within {abs(predicted_return):.2f}% of today's price."
    elif predicted_return >= -2.0:
        verdict, verdict_color = "Mild Caution", "red"
        pred_line = f"Slight downward pressure. A dip of ~{abs(predicted_return):.2f}% is expected."
    else:
        verdict, verdict_color = "Strong Sell Signal", "red"
        pred_line = f"Significant selling pressure. A drop of ~{abs(predicted_return):.2f}% may occur."

    if r2 >= 0.5:
        confidence_line = f"Reasonably confident — explains {r2*100:.1f}% of past price movements."
    elif r2 >= 0.2:
        confidence_line = f"Moderate confidence — captures {r2*100:.1f}% of historical patterns."
    else:
        confidence_line = f"Low confidence — explains only {r2*100:.1f}% of past movements."

    if beta is None:
        beta_line = "Volatility data unavailable."
    elif beta > 1.5:
        beta_line = f"Highly volatile (Beta: {beta:.2f}) — high risk, high reward."
    elif beta > 1.0:
        beta_line = f"Moderately volatile (Beta: {beta:.2f})."
    elif beta > 0.5:
        beta_line = f"Relatively stable (Beta: {beta:.2f})."
    else:
        beta_line = f"Low-volatility asset (Beta: {beta:.2f})."

    if week52_pos >= 0.85:
        position_line = "Near its 52-week HIGH — strong momentum, but could be overbought."
    elif week52_pos >= 0.60:
        position_line = "Upper half of 52-week range — performing well."
    elif week52_pos >= 0.40:
        position_line = "Middle of its 52-week range."
    elif week52_pos >= 0.15:
        position_line = "Lower half of 52-week range — possible buying opportunity."
    else:
        position_line = "Near its 52-week LOW — deep value or continued weakness."

    return {
        "verdict": verdict, "verdict_color": verdict_color,
        "pred_line": pred_line, "confidence_line": confidence_line,
        "beta_line": beta_line, "position_line": position_line,
    }


def predict_return(nse_code, period="1y"):
    try:
        ticker_symbol = nse_code.strip().upper() + ".NS"
        ticker        = yf.Ticker(ticker_symbol)
        hist          = ticker.history(period=period, interval="1d")
        if hist.empty or len(hist) < 30:
            return {"error": f"No data found for NSE code '{nse_code}'."}

        info      = ticker.info
        name      = info.get("longName") or info.get("shortName") or nse_code.upper()
        sector    = info.get("sector", "N/A")
        industry  = info.get("industry", "N/A")
        mkt_cap   = info.get("marketCap")
        beta      = info.get("beta")
        pe_ratio  = info.get("trailingPE")
        eps       = info.get("trailingEps")
        div_yld   = info.get("dividendYield")
        week52h   = info.get("fiftyTwoWeekHigh")
        week52l   = info.get("fiftyTwoWeekLow")
        ebit_m    = info.get("ebitdaMargins")
        rev_grow  = info.get("revenueGrowth")
        cur_price = info.get("currentPrice") or round(hist["Close"].iloc[-1], 2)
        avg50     = info.get("fiftyDayAverage")
        avg200    = info.get("twoHundredDayAverage")
        roe       = info.get("returnOnEquity")
        debt_eq   = info.get("debtToEquity")
        fcf       = info.get("freeCashflow")

        try:
            nifty_hist = yf.Ticker("^NSEI").history(period=period, interval="1d").dropna()
            n          = min(len(hist), len(nifty_hist))
            stock_ret  = (hist["Close"].iloc[-1] / hist["Close"].iloc[-n]) - 1
            nifty_ret  = (nifty_hist["Close"].iloc[-1] / nifty_hist["Close"].iloc[-n]) - 1
            alpha      = round((stock_ret - (beta or 1.0) * nifty_ret) * 100, 2) if beta else None
            stock_yoy  = round(stock_ret * 100, 2)
            nifty_yoy  = round(nifty_ret * 100, 2)
        except Exception:
            alpha = stock_yoy = nifty_yoy = None

        week52_pos = (
            round((cur_price - week52l) / (week52h - week52l), 4)
            if week52h and week52l and week52h != week52l else 0.5
        )

        hist = hist.copy()
        hist["Return"] = hist["Close"].pct_change() * 100
        hist["Lag_1"]  = hist["Return"].shift(1)
        hist["Lag_2"]  = hist["Return"].shift(2)
        hist["Lag_3"]  = hist["Return"].shift(3)
        hist["Lag_5"]  = hist["Return"].shift(5)
        hist["MA_5"]   = hist["Return"].rolling(5).mean()
        hist["MA_10"]  = hist["Return"].rolling(10).mean()
        hist = hist.dropna()

        features = ["Lag_1","Lag_2","Lag_3","Lag_5","MA_5","MA_10"]
        X     = hist[features].values
        y     = hist["Return"].values
        dates = hist.index.strftime("%Y-%m-%d").tolist()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False)
        lr     = LinearRegression()
        lr.fit(X_train, y_train)
        y_pred = lr.predict(X_test)
        mse    = round(mean_squared_error(y_test, y_pred), 4)
        r2     = round(r2_score(y_test, y_pred), 4)
        predicted_return = round(float(lr.predict(X[-1].reshape(1, -1))[0]), 4)
        layman = get_layman_summary(predicted_return, r2, beta,
                                    week52_pos, mse, sector)

        def fmt_cr(v):
            if v is None: return "N/A"
            cr = v / 1e7
            if cr >= 1e5: return f"₹{cr/1e5:.2f}L Cr"
            if cr >= 1e3: return f"₹{cr/1e3:.2f}K Cr"
            return f"₹{cr:.2f} Cr"
        def fmt_pct(v):  return "N/A" if v is None else f"{v*100:.2f}%"
        def fmt_num(v, dec=2): return "N/A" if v is None else f"{v:.{dec}f}"

        return {
            "error": None,  "nse_code": nse_code.upper(), "ticker": ticker_symbol,
            "name": name,   "sector": sector,  "industry": industry,
            "cur_price": cur_price,  "mkt_cap": fmt_cr(mkt_cap),
            "beta": fmt_num(beta),   "beta_raw": beta,
            "pe_ratio": fmt_num(pe_ratio),  "eps": fmt_num(eps),
            "div_yield": fmt_pct(div_yld),
            "week52h": fmt_num(week52h),    "week52l": fmt_num(week52l),
            "week52_pos": week52_pos,
            "ebit_margin": fmt_pct(ebit_m), "rev_growth": fmt_pct(rev_grow),
            "stock_yoy": fmt_num(stock_yoy),"nifty_yoy": fmt_num(nifty_yoy),
            "alpha": fmt_num(alpha),  "avg50": fmt_num(avg50),
            "avg200": fmt_num(avg200),"roe": fmt_pct(roe),
            "debt_equity": fmt_num(debt_eq), "fcf": fmt_cr(fcf),
            "mse": mse, "r2": r2, "predicted_return": predicted_return,
            "actual_returns":  [round(float(v), 4) for v in y.tolist()],
            "predicted_line":  [round(float(v), 4) for v in lr.predict(X).tolist()],
            "dates": dates,  "layman": layman,
        }
    except Exception as e:
        return {"error": f"Something went wrong: {str(e)}"}


def predict_investor(age, income, horizon, loss, experience):
    if model is None:
        return "Model unavailable"
    return model.predict(
        pd.DataFrame([[age, income, horizon, loss, experience]],
                     columns=["age","income","horizon","loss_tolerance","experience"])
    )[0]


def get_investor_segment(age, income, horizon, loss_tolerance, risk_type):
    if cluster_bundle is None:
        return {"label": "Unavailable", "cluster": -1,
                "description": "cluster_model.pkl not found — will auto-train on next restart."}
    risk_map   = {"Conservative": 0, "Moderate": 1, "Aggressive": 2}
    risk_score = risk_map.get(risk_type, 1)
    X_scaled   = cluster_bundle["scaler"].transform(
        [[age, income, horizon, loss_tolerance, risk_score]])
    cluster_id = int(cluster_bundle["model"].predict(X_scaled)[0])
    label      = cluster_bundle["label_map"].get(cluster_id, f"Cluster {cluster_id}")
    icons = {
        "Young Aggressive Investor":     "🚀",
        "Mid-Age Balanced Investor":     "⚖️",
        "Retired Conservative Investor": "🛡️",
    }
    descriptions = {
        "Young Aggressive Investor":
            "Long time horizon & high risk appetite. Small-caps and sectoral equities suit you best.",
        "Mid-Age Balanced Investor":
            "Balanced approach with moderate risk. Blue-chip equity + mutual funds + some bonds.",
        "Retired Conservative Investor":
            "Capital preservation is priority. Debt instruments, sovereign gold bonds, dividend stocks.",
    }
    return {
        "label": label, "icon": icons.get(label, "📊"),
        "cluster": cluster_id, "description": descriptions.get(label, ""),
    }


def get_portfolio_recommendation(risk_type):
    allocations = {
        "Conservative": {"Equity": 20, "Gold": 30, "Bonds / Liquid": 50},
        "Moderate":     {"Equity": 50, "Gold": 20, "Bonds / Liquid": 30},
        "Aggressive":   {"Equity": 80, "Gold": 10, "Bonds / Liquid": 10},
    }
    stock_pool = {
        "Conservative": [("HINDUNILVR","HUL"), ("ITC","ITC Ltd"),
                         ("NESTLEIND","Nestle India"), ("COALINDIA","Coal India")],
        "Moderate":     [("RELIANCE","Reliance"), ("HDFCBANK","HDFC Bank"),
                         ("INFY","Infosys"), ("TATAMOTORS","Tata Motors")],
        "Aggressive":   [("ZOMATO","Zomato"), ("BAJFINANCE","Bajaj Finance"),
                         ("BHARTIARTL","Airtel"), ("IRCTC","IRCTC")],
    }
    alloc  = allocations.get(risk_type, allocations["Moderate"])
    stocks = stock_pool.get(risk_type, stock_pool["Moderate"])

    equity_picks = []
    for nse_code, name in stocks:
        try:
            r = predict_return(nse_code, period="6mo")
            if not r.get("error"):
                equity_picks.append({
                    "name": name, "nse_code": nse_code,
                    "predicted_return": r["predicted_return"],
                    "beta": r["beta"], "pe": r["pe_ratio"],
                    "r2":  r["r2"],    "sector": r.get("sector","N/A"),
                })
            else:
                raise Exception(r["error"])
        except Exception:
            equity_picks.append({
                "name": name, "nse_code": nse_code,
                "predicted_return": "N/A", "beta": "N/A",
                "pe":  "N/A",             "r2":   "N/A",
                "sector": "N/A",
            })

    equity_picks.sort(
        key=lambda x: float(x["predicted_return"])
            if isinstance(x["predicted_return"], float) else 0,
        reverse=True,
    )

    colors = {"Equity": "#00E5A0", "Gold": "#F0B90B", "Bonds / Liquid": "#4f8ef7"}
    fig = go.Figure(data=[go.Pie(
        labels=list(alloc.keys()), values=list(alloc.values()), hole=0.45,
        marker=dict(colors=[colors.get(k,"#aaa") for k in alloc.keys()]),
        textinfo="label+percent", textfont=dict(size=13),
    )])
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=360,
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation="h", y=-0.15, font=dict(size=11)),
    )
    return {
        "risk_type": risk_type, "allocation": alloc,
        "equity_picks": equity_picks,
        "pie_json": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
    }


def get_evaluation_metrics():
    try:
        data_df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        return {"error": "investor_data.csv not found."}
    except Exception as e:
        return {"error": str(e)}

    X = data_df[["age","income","horizon","loss_tolerance","experience"]]
    y = data_df["risk_type"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)
    clf = DecisionTreeClassifier(random_state=42)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    accuracy  = round(accuracy_score(y_test, y_pred)  * 100, 2)
    precision = round(precision_score(y_test, y_pred,
                      average="weighted", zero_division=0) * 100, 2)
    recall    = round(recall_score(y_test, y_pred,
                      average="weighted", zero_division=0) * 100, 2)
    report    = classification_report(y_test, y_pred, output_dict=True)

    classes = []
    for cls in ["Aggressive","Moderate","Conservative"]:
        if cls in report:
            classes.append({
                "name":      cls,
                "precision": round(report[cls]["precision"] * 100, 1),
                "recall":    round(report[cls]["recall"]    * 100, 1),
                "f1":        round(report[cls]["f1-score"]  * 100, 1),
                "support":   int(report[cls]["support"]),
            })

    cm = confusion_matrix(y_test, y_pred,
                          labels=["Aggressive","Moderate","Conservative"])
    cm_fig = go.Figure(data=go.Heatmap(
        z=cm,
        x=["Aggressive","Moderate","Conservative"],
        y=["Aggressive","Moderate","Conservative"],
        colorscale=[[0,"#0b0e1a"],[1,"#00E5A0"]],
        text=cm, texttemplate="%{text}", showscale=False,
    ))
    cm_fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=300,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Predicted", yaxis_title="Actual",
    )
    cm_json = json.dumps(cm_fig, cls=plotly.utils.PlotlyJSONEncoder)

    reg_result = predict_return("RELIANCE", "1y")
    reg_mse    = reg_result.get("mse","N/A") if not reg_result.get("error") else "N/A"
    reg_r2     = reg_result.get("r2","N/A")  if not reg_result.get("error") else "N/A"

    return {
        "accuracy": accuracy, "precision": precision, "recall": recall,
        "classes": classes,   "cm_json": cm_json,
        "reg_mse": reg_mse,   "reg_r2": reg_r2,
    }

# ─────────────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────────────

@app.route("/")
def login_page():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["username"] = username
        return redirect(url_for("dashboard"))
    flash("Invalid username or password. Please try again.", "error")
    return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    market = get_market_data()
    chart  = get_nifty_chart()
    return render_template("dashboard.html",
                           market=market, chart=chart, stocks=NSE_TOP_250)


@app.route("/predictor", methods=["GET", "POST"])
@login_required
def predictor_page():
    prediction = segment = portfolio = None
    form_data  = {}
    if request.method == "POST":
        try:
            age        = int(request.form["age"])
            income     = int(request.form["income"])
            horizon    = int(request.form["horizon"])
            loss       = int(request.form["loss"])
            experience = int(request.form["experience"])
            form_data  = dict(age=age, income=income, horizon=horizon,
                              loss=loss, experience=experience)
            prediction = predict_investor(age, income, horizon, loss, experience)
            if prediction != "Model unavailable":
                segment   = get_investor_segment(age, income, horizon,
                                                 loss, prediction)
                portfolio = get_portfolio_recommendation(prediction)
        except (KeyError, ValueError) as e:
            flash(f"Invalid input — {e}", "error")
    market = get_market_data()
    return render_template("predictor.html",
                           prediction=prediction, segment=segment,
                           portfolio=portfolio, form_data=form_data,
                           market=market)


# Backward-compatible alias for any form still posting to /predict
@app.route("/predict", methods=["POST"])
@login_required
def predict():
    return redirect(url_for("predictor_page"), code=307)


@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    result = chart_json = None
    query = ""
    if request.method == "POST":
        query  = request.form.get("nsecode", "").strip().upper()
        period = request.form.get("period", "1y")
        if query:
            result = predict_return(query, period)
            if result and not result.get("error"):
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=result["dates"], y=result["actual_returns"],
                    mode="lines", name="Actual Daily Return (%)",
                    line=dict(color="#00E5A0", width=1.2),
                ))
                fig.add_trace(go.Scatter(
                    x=result["dates"], y=result["predicted_line"],
                    mode="lines", name="Model Predicted Return (%)",
                    line=dict(color="#F0B90B", width=1.5, dash="dash"),
                ))
                fig.update_layout(
                    template="plotly_dark", height=340,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", showspikes=True,
                               spikecolor="rgba(255,255,255,0.15)", spikethickness=1),
                    yaxis=dict(title=dict(text="Daily Return (%)", font=dict(size=10)),
                               gridcolor="rgba(255,255,255,0.04)"),
                    legend=dict(orientation="h", y=1.08, font=dict(size=10)),
                    margin=dict(l=10, r=10, t=10, b=10),
                    hovermode="x unified",
                )
                chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    market = get_market_data()
    return render_template("watchlist.html", stocks=NSE_TOP_250, market=market,
                           result=result, chart_json=chart_json, query=query)


@app.route("/api/watchlist")
@login_required
def api_watchlist():
    symbols = request.args.get("symbols", "")
    if not symbols:
        return json.dumps([])
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    data = []
    for sym in sym_list:
        try:
            ticker  = yf.Ticker(sym + ".NS")
            hist    = ticker.history(period="2d")
            if hist.empty:
                raise ValueError("no data")
            info    = ticker.info
            price   = round(hist["Close"].iloc[-1], 2)
            open_p  = round(hist["Open"].iloc[-1], 2)
            chg_pct = round((price - open_p) / open_p * 100, 2) if open_p else 0
            w52h    = info.get("fiftyTwoWeekHigh")
            w52l    = info.get("fiftyTwoWeekLow")
            cap     = info.get("marketCap")
            name    = info.get("shortName") or info.get("longName") or sym
            def fc(v):
                if not v: return "N/A"
                return f"₹{v/1e12:.1f}T" if v >= 1e12 else f"₹{v/1e9:.0f}B"
            signal  = "BUY"  if chg_pct > 0.5  else ("SELL" if chg_pct < -0.5 else "HOLD")
            sig_cls = "up"   if chg_pct > 0.5  else ("dn"   if chg_pct < -0.5 else "neu")
            data.append({
                "sym": sym, "name": name, "price": price, "change": chg_pct,
                "week52h": round(w52h) if isinstance(w52h, float) else "N/A",
                "week52l": round(w52l) if isinstance(w52l, float) else "N/A",
                "mkt_cap": fc(cap), "signal": signal, "sig_cls": sig_cls,
            })
        except Exception:
            data.append({
                "sym": sym, "name": sym, "price": "—", "change": 0,
                "week52h": "N/A", "week52l": "N/A", "mkt_cap": "N/A",
                "signal": "N/A", "sig_cls": "neu",
            })
    return json.dumps(data)


@app.route("/return-predict", methods=["GET", "POST"])
@login_required
def return_predict():
    result = chart_json = None
    query  = ""
    if request.method == "POST":
        query  = request.form.get("nse_code", "").strip().upper()
        period = request.form.get("period", "1y")
        if query:
            result = predict_return(query, period)
            if result and not result.get("error"):
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=result["dates"], y=result["actual_returns"],
                    mode="lines", name="Actual Daily Return (%)",
                    line=dict(color="#00E5A0", width=1.2),
                ))
                fig.add_trace(go.Scatter(
                    x=result["dates"], y=result["predicted_line"],
                    mode="lines", name="Model Predicted Return (%)",
                    line=dict(color="#F0B90B", width=1.5, dash="dash"),
                ))
                fig.update_layout(
                    template="plotly_dark", height=340,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(gridcolor="rgba(255,255,255,0.04)",
                               showspikes=True,
                               spikecolor="rgba(255,255,255,0.15)",
                               spikethickness=1),
                    yaxis=dict(title=dict(text="Daily Return (%)",
                                         font=dict(size=10)),
                               gridcolor="rgba(255,255,255,0.04)"),
                    legend=dict(orientation="h", y=1.08, font=dict(size=10)),
                    margin=dict(l=10, r=10, t=10, b=10),
                    hovermode="x unified",
                )
                chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    market = get_market_data()
    return render_template("return_predict.html",
                           stocks=NSE_TOP_250, query=query,
                           result=result, chart_json=chart_json,
                           market=market)


@app.route("/portfolio", methods=["GET", "POST"])
@login_required
def portfolio():
    risk_type     = (request.args.get("risk_type") or
                     request.form.get("risk_type") or "Moderate")
    segment_label = request.args.get("segment", "")
    market        = get_market_data()
    result        = get_portfolio_recommendation(risk_type)
    return render_template("portfolio.html",
                           result=result, segment_label=segment_label,
                           market=market)


@app.route("/evaluation")
@login_required
def evaluation():
    market  = get_market_data()
    metrics = get_evaluation_metrics()
    return render_template("evaluation.html", metrics=metrics, market=market)


@app.route("/profile")
@login_required
def profile():
    market  = get_market_data()
    metrics = get_evaluation_metrics()
    return render_template("profile.html", market=market, metrics=metrics)
@app.route("/api/market-overview")
def market_overview():
    """Public — no login needed. Used by login page."""
    items = [("NIFTY 50","^NSEI"), ("SENSEX","^BSESN"), ("USD/INR","USDINR=X"), ("GOLD","GC=F")]
    out, _fx = [], None
    for name, sym in items:
        try:
            hist   = yf.Ticker(sym).history(period="2d")
            if hist.empty: raise ValueError
            price  = float(hist["Close"].iloc[-1])
            open_p = float(hist["Open"].iloc[-1])
            chg    = round((price - open_p) / open_p * 100, 2) if open_p else 0
            if name == "GOLD":
                if _fx is None:
                    try: _fx = float(yf.Ticker("USDINR=X").history(period="1d")["Close"].iloc[-1])
                    except: _fx = 84.0
                display = f"₹{round(price * _fx / 31.1035 * 10):,}"
            elif name == "USD/INR":
                display = f"₹{price:.2f}"
            else:
                display = f"{price:,.2f}"
            out.append({"name": name, "price": display, "change": chg,
                        "color": "up" if chg > 0 else "dn"})
        except:
            out.append({"name": name, "price": "—", "change": 0, "color": "neu"})
    return json.dumps(out)
@app.route("/api/news")
@login_required
def api_news():
    import urllib.request, xml.etree.ElementTree as ET, email.utils
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    feeds = [
        "https://economictimes.indiatimes.com/markets/rss.cms",
        "https://www.moneycontrol.com/rss/marketreports.xml",
    ]
    news = []
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                root = ET.fromstring(r.read())
            ch = root.find("channel") or root
            for item in ch.findall("item"):
                title = (item.findtext("title") or "").strip()
                pub   = item.findtext("pubDate") or ""
                link  = item.findtext("link") or "#"
                try:
                    ts = email.utils.parsedate_to_datetime(pub).astimezone(IST).strftime("%H:%M IST · %d %b")
                except: ts = "Just now"
                if title:
                    news.append({"title": title[:120], "time": ts, "link": link})
                if len(news) >= 5: break
        except: continue
        if len(news) >= 5: break
    if not news:
        from datetime import datetime
        now_ts = datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime("%H:%M IST")
        news = [
            {"title": "Nifty 50 tracking global cues — visit NSE for live prices", "time": now_ts, "link": "#"},
            {"title": "RBI watch: repo rate and liquidity stance in focus",         "time": now_ts, "link": "#"},
            {"title": "FII/DII flows: net data available post-market close",        "time": now_ts, "link": "#"},
            {"title": "Sectoral performance: IT, Banking, FMCG in spotlight",       "time": now_ts, "link": "#"},
            {"title": "Market breadth: advances vs declines tracking on NSE",       "time": now_ts, "link": "#"},
        ]
    return json.dumps(news[:5])
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)