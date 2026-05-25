from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from opensearchpy import OpenSearch
from datetime import datetime
import yfinance as yf
import pandas as pd
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
import os
import httpx
import jwt
import time
import secrets

app = FastAPI(title="Stock Trader API")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Config ----------
STARTING_CASH = 100_000.0
OS_HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
OS_PORT = int(os.environ.get("OPENSEARCH_PORT", 9200))
OS_USER = os.environ.get("OPENSEARCH_USER", "admin")
OS_PASS = os.environ.get("OPENSEARCH_PASS", "admin")
OS_SCHEME = os.environ.get("OPENSEARCH_SCHEME", "https")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))

IDX_WATCHLIST = "stock-watchlist"
IDX_PORTFOLIO = "stock-portfolio"
IDX_TRANSACTIONS = "stock-transactions"
IDX_USERS = "stock-users"

# ---------- OpenSearch ----------
_client = None

def get_os():
    global _client
    if _client is None:
        _client = OpenSearch(
            hosts=[{"host": OS_HOST, "port": OS_PORT}],
            http_auth=(OS_USER, OS_PASS),
            use_ssl=(OS_SCHEME == "https"),
            verify_certs=False,
            ssl_show_warn=False,
        )
        _ensure_indices(_client)
    return _client

def _ensure_indices(client):
    indices = {
        IDX_WATCHLIST: {
            "mappings": {"properties": {
                "user_id": {"type": "keyword"},
                "ticker": {"type": "keyword"},
                "added_at": {"type": "date"},
            }}
        },
        IDX_PORTFOLIO: {
            "mappings": {"properties": {
                "user_id": {"type": "keyword"},
                "cash": {"type": "double"},
                "initial_value": {"type": "double"},
                "holdings": {"type": "object", "enabled": False},
                "updated_at": {"type": "date"},
            }}
        },
        IDX_TRANSACTIONS: {
            "mappings": {"properties": {
                "user_id": {"type": "keyword"},
                "date": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||epoch_millis"},
                "type": {"type": "keyword"},
                "ticker": {"type": "keyword"},
                "shares": {"type": "integer"},
                "price": {"type": "double"},
                "total": {"type": "double"},
                "cash_after": {"type": "double"},
                "portfolio_value": {"type": "double"},
            }}
        },
        IDX_USERS: {
            "mappings": {"properties": {
                "email": {"type": "keyword"},
                "name": {"type": "text"},
                "picture": {"type": "keyword"},
                "created_at": {"type": "date"},
                "last_login": {"type": "date"},
            }}
        },
    }
    for idx, body in indices.items():
        if not client.indices.exists(index=idx):
            client.indices.create(index=idx, body=body)

# ---------- Auth ----------
class GoogleAuthRequest(BaseModel):
    code: str
    redirect_uri: str

def _create_jwt(user_id: str, email: str, name: str, picture: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "iat": int(time.time()),
        "exp": int(time.time()) + 7 * 24 * 3600,  # 7 days
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def _get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

@app.post("/api/auth/google")
async def google_auth(req: GoogleAuthRequest):
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": req.code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": req.redirect_uri,
            "grant_type": "authorization_code",
        })
    if token_resp.status_code != 200:
        raise HTTPException(400, f"Google token exchange failed: {token_resp.text}")

    tokens = token_resp.json()
    access_token = tokens["access_token"]

    # Get user info
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if user_resp.status_code != 200:
        raise HTTPException(400, "Failed to get user info from Google")

    user_info = user_resp.json()
    user_id = user_info["id"]
    email = user_info["email"]
    name = user_info.get("name", email)
    picture = user_info.get("picture", "")

    # Upsert user in OpenSearch
    os_client = get_os()
    os_client.index(index=IDX_USERS, id=user_id, body={
        "email": email, "name": name, "picture": picture,
        "last_login": datetime.utcnow().isoformat(),
    }, refresh="wait_for")

    # Create JWT
    token = _create_jwt(user_id, email, name, picture)
    return {"token": token, "user": {"id": user_id, "email": email, "name": name, "picture": picture}}

@app.get("/api/auth/me")
def get_me(user: dict = Depends(_get_current_user)):
    return {"id": user["sub"], "email": user["email"], "name": user["name"], "picture": user["picture"]}

# ---------- Pydantic Models ----------
class TradeRequest(BaseModel):
    ticker: str
    shares: int

# ---------- Helpers ----------
def _get_current_price(ticker: str) -> float | None:
    data = yf.Ticker(ticker).history(period="1d")
    if not data.empty:
        return float(data["Close"].iloc[-1])
    return None

def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    df["SMA_20"] = SMAIndicator(close, window=20).sma_indicator()
    df["SMA_50"] = SMAIndicator(close, window=50).sma_indicator()
    df["EMA_12"] = EMAIndicator(close, window=12).ema_indicator()
    df["EMA_26"] = EMAIndicator(close, window=26).ema_indicator()
    df["RSI"] = RSIIndicator(close, window=14).rsi()
    macd = MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()
    bb = BollingerBands(close, window=20, window_dev=2)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Lower"] = bb.bollinger_lband()
    df["BB_Mid"] = bb.bollinger_mavg()
    stoch = StochasticOscillator(df["High"], df["Low"], close)
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()
    df["ATR"] = AverageTrueRange(df["High"], df["Low"], close).average_true_range()
    df["OBV"] = OnBalanceVolumeIndicator(close, df["Volume"]).on_balance_volume()
    return df

def _analyse(df: pd.DataFrame, info: dict) -> dict:
    if df.empty or len(df) < 50:
        return {"signal": "HOLD", "score": 0, "details": ["Insufficient data for analysis."]}

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []
    score = 0.0

    rsi = latest["RSI"]
    if rsi < 30:
        score += 2; signals.append(f"RSI ({rsi:.1f}) is oversold (<30) - Bullish")
    elif rsi < 40:
        score += 1; signals.append(f"RSI ({rsi:.1f}) is approaching oversold - Slightly Bullish")
    elif rsi > 70:
        score -= 2; signals.append(f"RSI ({rsi:.1f}) is overbought (>70) - Bearish")
    elif rsi > 60:
        score -= 1; signals.append(f"RSI ({rsi:.1f}) is approaching overbought - Slightly Bearish")
    else:
        signals.append(f"RSI ({rsi:.1f}) is neutral")

    macd_val, macd_sig = latest["MACD"], latest["MACD_Signal"]
    if macd_val > macd_sig and prev["MACD"] <= prev["MACD_Signal"]:
        score += 2; signals.append("MACD bullish crossover just occurred - Strong Buy signal")
    elif macd_val < macd_sig and prev["MACD"] >= prev["MACD_Signal"]:
        score -= 2; signals.append("MACD bearish crossover just occurred - Strong Sell signal")
    elif macd_val > macd_sig:
        score += 1; signals.append("MACD is above signal line - Bullish")
    else:
        score -= 1; signals.append("MACD is below signal line - Bearish")

    if latest["MACD_Hist"] > prev["MACD_Hist"]:
        score += 0.5; signals.append("MACD histogram expanding - Momentum increasing")
    else:
        score -= 0.5; signals.append("MACD histogram contracting - Momentum decreasing")

    price, sma20, sma50 = latest["Close"], latest["SMA_20"], latest["SMA_50"]
    if price > sma20 > sma50:
        score += 2; signals.append(f"Price (${price:.2f}) > SMA20 > SMA50 - Strong uptrend")
    elif price > sma20:
        score += 1; signals.append(f"Price above SMA20 (${sma20:.2f}) - Short-term bullish")
    elif price < sma20 < sma50:
        score -= 2; signals.append(f"Price (${price:.2f}) < SMA20 < SMA50 - Strong downtrend")
    elif price < sma20:
        score -= 1; signals.append(f"Price below SMA20 (${sma20:.2f}) - Short-term bearish")

    if len(df) >= 5:
        if sma20 > sma50 and df.iloc[-5]["SMA_20"] <= df.iloc[-5]["SMA_50"]:
            score += 2; signals.append("Golden Cross forming (SMA20 crossing above SMA50) - Very Bullish")
        elif sma20 < sma50 and df.iloc[-5]["SMA_20"] >= df.iloc[-5]["SMA_50"]:
            score -= 2; signals.append("Death Cross forming (SMA20 crossing below SMA50) - Very Bearish")

    bb_upper, bb_lower, bb_mid = latest["BB_Upper"], latest["BB_Lower"], latest["BB_Mid"]
    bb_width = (bb_upper - bb_lower) / bb_mid * 100
    if price <= bb_lower:
        score += 1.5; signals.append("Price at lower Bollinger Band - Potential bounce (Buy)")
    elif price >= bb_upper:
        score -= 1.5; signals.append("Price at upper Bollinger Band - Potential pullback (Sell)")
    if bb_width < 5:
        signals.append(f"Bollinger Bands are tight ({bb_width:.1f}%) - Breakout expected soon")

    stoch_k, stoch_d = latest["Stoch_K"], latest["Stoch_D"]
    if stoch_k < 20 and stoch_d < 20:
        score += 1; signals.append(f"Stochastic oversold (K:{stoch_k:.1f}, D:{stoch_d:.1f}) - Bullish")
    elif stoch_k > 80 and stoch_d > 80:
        score -= 1; signals.append(f"Stochastic overbought (K:{stoch_k:.1f}, D:{stoch_d:.1f}) - Bearish")

    vol_avg = df["Volume"].tail(20).mean()
    vol_today = latest["Volume"]
    if vol_today > vol_avg * 1.5:
        signals.append(f"Volume spike ({vol_today/vol_avg:.1f}x average) - High conviction move")
        score += 1 if price > prev["Close"] else -1

    ret_5d = (price / df["Close"].iloc[-6] - 1) * 100 if len(df) >= 6 else 0
    ret_20d = (price / df["Close"].iloc[-21] - 1) * 100 if len(df) >= 21 else 0
    signals.append(f"5-day return: {ret_5d:+.2f}% | 20-day return: {ret_20d:+.2f}%")

    atr = latest["ATR"]
    atr_pct = atr / price * 100
    signals.append(f"ATR: ${atr:.2f} ({atr_pct:.1f}% of price) - {'High' if atr_pct > 3 else 'Normal'} volatility")

    if score >= 4: signal = "STRONG BUY"
    elif score >= 2: signal = "BUY"
    elif score <= -4: signal = "STRONG SELL"
    elif score <= -2: signal = "SELL"
    else: signal = "HOLD"

    return {"signal": signal, "score": score, "details": signals}

def _portfolio_value(portfolio: dict) -> float:
    total = portfolio["cash"]
    for ticker, h in portfolio.get("holdings", {}).items():
        p = _get_current_price(ticker)
        if p:
            total += h["shares"] * p
    return total

def _load_portfolio(user_id: str) -> dict:
    client = get_os()
    default = {"user_id": user_id, "cash": STARTING_CASH, "holdings": {}, "initial_value": STARTING_CASH}
    try:
        return client.get(index=IDX_PORTFOLIO, id=user_id)["_source"]
    except Exception:
        client.index(index=IDX_PORTFOLIO, id=user_id,
                     body={**default, "updated_at": datetime.utcnow().isoformat()},
                     refresh="wait_for")
        return default

def _save_portfolio(portfolio: dict, user_id: str):
    client = get_os()
    portfolio["updated_at"] = datetime.utcnow().isoformat()
    client.index(index=IDX_PORTFOLIO, id=user_id, body=portfolio, refresh="wait_for")

# ==================== ENDPOINTS ====================

# --- Watchlist (per-user) ---
@app.get("/api/watchlist")
def get_watchlist(user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    client = get_os()
    resp = client.search(index=IDX_WATCHLIST, body={
        "query": {"term": {"user_id": uid}}, "size": 200,
    })
    tickers = sorted({hit["_source"]["ticker"] for hit in resp["hits"]["hits"]})
    if not tickers:
        for t in ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]:
            client.index(index=IDX_WATCHLIST, id=f"{uid}_{t}",
                         body={"user_id": uid, "ticker": t, "added_at": datetime.utcnow().isoformat()},
                         refresh="wait_for")
        tickers = ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA"]
    return {"tickers": tickers}

@app.post("/api/watchlist/{ticker}")
def add_watchlist(ticker: str, user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    ticker = ticker.upper().strip()
    client = get_os()
    client.index(index=IDX_WATCHLIST, id=f"{uid}_{ticker}",
                 body={"user_id": uid, "ticker": ticker, "added_at": datetime.utcnow().isoformat()},
                 refresh="wait_for")
    return {"status": "ok", "ticker": ticker}

@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str, user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    client = get_os()
    try:
        client.delete(index=IDX_WATCHLIST, id=f"{uid}_{ticker.upper()}", refresh="wait_for")
    except Exception:
        pass
    return {"status": "ok"}

# --- Stock Data (public - no auth needed) ---
@app.get("/api/stock/{ticker}")
def get_stock(ticker: str, period: str = "6mo"):
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, auto_adjust=True)
    info = stock.info

    if df.empty:
        raise HTTPException(404, f"No data for {ticker}")

    df = _compute_indicators(df)
    analysis = _analyse(df, info)

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = latest["Close"] - prev["Close"]
    change_pct = change / prev["Close"] * 100

    chart_df = df[["Open", "High", "Low", "Close", "Volume",
                   "SMA_20", "SMA_50", "BB_Upper", "BB_Lower",
                   "RSI", "MACD", "MACD_Signal", "MACD_Hist"]].copy()
    chart_df.index = chart_df.index.strftime("%Y-%m-%d")
    chart_data = chart_df.reset_index().rename(columns={"Date": "date"}).where(pd.notnull(chart_df.reset_index()), None).to_dict("records")

    return {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "price": round(latest["Close"], 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "high": round(latest["High"], 2),
        "low": round(latest["Low"], 2),
        "volume": int(latest["Volume"]),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "dividend_yield": info.get("dividendYield"),
        "week52_low": info.get("fiftyTwoWeekLow"),
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "analysis": analysis,
        "chart": chart_data,
    }

@app.get("/api/stock/{ticker}/price")
def get_price(ticker: str):
    price = _get_current_price(ticker.upper())
    if price is None:
        raise HTTPException(404, f"No price for {ticker}")
    return {"ticker": ticker.upper(), "price": price}

# --- Portfolio (per-user) ---
@app.get("/api/portfolio")
def get_portfolio(user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    portfolio = _load_portfolio(uid)
    port_value = _portfolio_value(portfolio)
    total_pnl = port_value - portfolio["initial_value"]

    holdings_detail = []
    for ticker, h in portfolio.get("holdings", {}).items():
        cp = _get_current_price(ticker)
        if cp:
            mv = h["shares"] * cp
            cb = h["shares"] * h["avg_price"]
            pnl = mv - cb
            holdings_detail.append({
                "ticker": ticker,
                "shares": h["shares"],
                "avg_price": round(h["avg_price"], 2),
                "current_price": round(cp, 2),
                "market_value": round(mv, 2),
                "cost_basis": round(cb, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round((pnl / cb) * 100, 2) if cb else 0,
                "allocation_pct": round((mv / port_value) * 100, 1) if port_value else 0,
            })

    return {
        "cash": round(portfolio["cash"], 2),
        "portfolio_value": round(port_value, 2),
        "initial_value": portfolio["initial_value"],
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round((total_pnl / portfolio["initial_value"]) * 100, 2),
        "holdings": holdings_detail,
    }

# --- Trading (per-user) ---
@app.post("/api/trade/buy")
def trade_buy(req: TradeRequest, user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    ticker = req.ticker.upper()
    price = _get_current_price(ticker)
    if price is None:
        raise HTTPException(400, f"Cannot fetch price for {ticker}")

    portfolio = _load_portfolio(uid)
    cost = req.shares * price
    if cost > portfolio["cash"]:
        raise HTTPException(400, f"Insufficient funds. Need ${cost:,.2f}, have ${portfolio['cash']:,.2f}")

    portfolio["cash"] -= cost
    holdings = portfolio.get("holdings", {})
    if ticker in holdings:
        h = holdings[ticker]
        total_shares = h["shares"] + req.shares
        total_cost = h["avg_price"] * h["shares"] + cost
        h["avg_price"] = total_cost / total_shares
        h["shares"] = total_shares
    else:
        holdings[ticker] = {"shares": req.shares, "avg_price": price}
    portfolio["holdings"] = holdings

    port_value = _portfolio_value(portfolio)
    _save_portfolio(portfolio, uid)

    txn = {
        "user_id": uid,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "BUY", "ticker": ticker, "shares": req.shares,
        "price": price, "total": cost,
        "cash_after": portfolio["cash"], "portfolio_value": port_value,
    }
    get_os().index(index=IDX_TRANSACTIONS, body=txn, refresh="wait_for")

    return {"status": "ok", "message": f"Bought {req.shares} shares of {ticker} at ${price:.2f}", "transaction": txn}

@app.post("/api/trade/sell")
def trade_sell(req: TradeRequest, user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    ticker = req.ticker.upper()
    price = _get_current_price(ticker)
    if price is None:
        raise HTTPException(400, f"Cannot fetch price for {ticker}")

    portfolio = _load_portfolio(uid)
    holdings = portfolio.get("holdings", {})
    if ticker not in holdings:
        raise HTTPException(400, f"You don't own any {ticker}")
    if req.shares > holdings[ticker]["shares"]:
        raise HTTPException(400, f"You only own {holdings[ticker]['shares']} shares of {ticker}")

    revenue = req.shares * price
    portfolio["cash"] += revenue
    holdings[ticker]["shares"] -= req.shares
    if holdings[ticker]["shares"] == 0:
        del holdings[ticker]
    portfolio["holdings"] = holdings

    port_value = _portfolio_value(portfolio)
    _save_portfolio(portfolio, uid)

    txn = {
        "user_id": uid,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "SELL", "ticker": ticker, "shares": req.shares,
        "price": price, "total": revenue,
        "cash_after": portfolio["cash"], "portfolio_value": port_value,
    }
    get_os().index(index=IDX_TRANSACTIONS, body=txn, refresh="wait_for")

    return {"status": "ok", "message": f"Sold {req.shares} shares of {ticker} at ${price:.2f}", "transaction": txn}

# --- Transactions (per-user) ---
@app.get("/api/transactions")
def get_transactions(limit: int = 200, user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    client = get_os()
    resp = client.search(
        index=IDX_TRANSACTIONS,
        body={"query": {"term": {"user_id": uid}}, "sort": [{"date": {"order": "desc"}}], "size": limit},
    )
    return {"transactions": [hit["_source"] for hit in resp["hits"]["hits"]]}

# --- Reset (per-user) ---
@app.post("/api/portfolio/reset")
def reset_portfolio(user: dict = Depends(_get_current_user)):
    uid = user["sub"]
    client = get_os()
    default = {
        "user_id": uid, "cash": STARTING_CASH, "holdings": {}, "initial_value": STARTING_CASH,
        "updated_at": datetime.utcnow().isoformat(),
    }
    client.index(index=IDX_PORTFOLIO, id=uid, body=default, refresh="wait_for")
    # Delete only this user's transactions
    client.delete_by_query(index=IDX_TRANSACTIONS, body={
        "query": {"term": {"user_id": uid}}
    }, refresh=True)
    return {"status": "ok", "message": "Portfolio reset to $100,000"}
