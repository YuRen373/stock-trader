import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
from datetime import datetime, timedelta
import json
import os

# ---------- Config ----------
DATA_DIR = "data"
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
STARTING_CASH = 100000.00

os.makedirs(DATA_DIR, exist_ok=True)

# ---------- Persistence Helpers ----------
def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return default

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

def load_watchlist():
    return load_json(WATCHLIST_FILE, ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"])

def save_watchlist(tickers):
    save_json(WATCHLIST_FILE, sorted(set(tickers)))

def load_portfolio():
    default = {
        "cash": STARTING_CASH,
        "holdings": {},
        "transactions": [],
        "initial_value": STARTING_CASH,
    }
    return load_json(PORTFOLIO_FILE, default)

def save_portfolio(portfolio):
    save_json(PORTFOLIO_FILE, portfolio)

# ---------- Data ----------
@st.cache_data(ttl=300)
def fetch_stock_data(ticker, period="6mo"):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, auto_adjust=True)
    info = stock.info
    return df, info

@st.cache_data(ttl=60)
def get_current_price(ticker):
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")
    if not data.empty:
        return float(data["Close"].iloc[-1])
    return None

def compute_indicators(df):
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

# ---------- Analysis Engine ----------
def analyse_stock(df, info):
    if df.empty or len(df) < 50:
        return "HOLD", 0, ["Insufficient data for analysis."]

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []
    score = 0

    # 1. RSI
    rsi = latest["RSI"]
    if rsi < 30:
        score += 2
        signals.append(f"RSI ({rsi:.1f}) is oversold (<30) - Bullish")
    elif rsi < 40:
        score += 1
        signals.append(f"RSI ({rsi:.1f}) is approaching oversold - Slightly Bullish")
    elif rsi > 70:
        score -= 2
        signals.append(f"RSI ({rsi:.1f}) is overbought (>70) - Bearish")
    elif rsi > 60:
        score -= 1
        signals.append(f"RSI ({rsi:.1f}) is approaching overbought - Slightly Bearish")
    else:
        signals.append(f"RSI ({rsi:.1f}) is neutral")

    # 2. MACD
    macd_val = latest["MACD"]
    macd_sig = latest["MACD_Signal"]
    macd_hist = latest["MACD_Hist"]
    prev_hist = prev["MACD_Hist"]
    if macd_val > macd_sig and prev["MACD"] <= prev["MACD_Signal"]:
        score += 2
        signals.append("MACD bullish crossover just occurred - Strong Buy signal")
    elif macd_val < macd_sig and prev["MACD"] >= prev["MACD_Signal"]:
        score -= 2
        signals.append("MACD bearish crossover just occurred - Strong Sell signal")
    elif macd_val > macd_sig:
        score += 1
        signals.append("MACD is above signal line - Bullish")
    else:
        score -= 1
        signals.append("MACD is below signal line - Bearish")

    if macd_hist > prev_hist:
        score += 0.5
        signals.append("MACD histogram expanding - Momentum increasing")
    else:
        score -= 0.5
        signals.append("MACD histogram contracting - Momentum decreasing")

    # 3. Moving Average Trend
    price = latest["Close"]
    sma20 = latest["SMA_20"]
    sma50 = latest["SMA_50"]
    if price > sma20 > sma50:
        score += 2
        signals.append(f"Price (${price:.2f}) > SMA20 > SMA50 - Strong uptrend")
    elif price > sma20:
        score += 1
        signals.append(f"Price above SMA20 (${sma20:.2f}) - Short-term bullish")
    elif price < sma20 < sma50:
        score -= 2
        signals.append(f"Price (${price:.2f}) < SMA20 < SMA50 - Strong downtrend")
    elif price < sma20:
        score -= 1
        signals.append(f"Price below SMA20 (${sma20:.2f}) - Short-term bearish")

    # Golden/Death cross
    if len(df) >= 5:
        if sma20 > sma50 and df.iloc[-5]["SMA_20"] <= df.iloc[-5]["SMA_50"]:
            score += 2
            signals.append("Golden Cross forming (SMA20 crossing above SMA50) - Very Bullish")
        elif sma20 < sma50 and df.iloc[-5]["SMA_20"] >= df.iloc[-5]["SMA_50"]:
            score -= 2
            signals.append("Death Cross forming (SMA20 crossing below SMA50) - Very Bearish")

    # 4. Bollinger Bands
    bb_upper = latest["BB_Upper"]
    bb_lower = latest["BB_Lower"]
    bb_mid = latest["BB_Mid"]
    bb_width = (bb_upper - bb_lower) / bb_mid * 100
    if price <= bb_lower:
        score += 1.5
        signals.append("Price at lower Bollinger Band - Potential bounce (Buy)")
    elif price >= bb_upper:
        score -= 1.5
        signals.append("Price at upper Bollinger Band - Potential pullback (Sell)")
    if bb_width < 5:
        signals.append(f"Bollinger Bands are tight ({bb_width:.1f}%) - Breakout expected soon")

    # 5. Stochastic
    stoch_k = latest["Stoch_K"]
    stoch_d = latest["Stoch_D"]
    if stoch_k < 20 and stoch_d < 20:
        score += 1
        signals.append(f"Stochastic oversold (K:{stoch_k:.1f}, D:{stoch_d:.1f}) - Bullish")
    elif stoch_k > 80 and stoch_d > 80:
        score -= 1
        signals.append(f"Stochastic overbought (K:{stoch_k:.1f}, D:{stoch_d:.1f}) - Bearish")

    # 6. Volume trend
    vol_avg = df["Volume"].tail(20).mean()
    vol_today = latest["Volume"]
    if vol_today > vol_avg * 1.5:
        signals.append(f"Volume spike ({vol_today/vol_avg:.1f}x average) - High conviction move")
        if price > prev["Close"]:
            score += 1
        else:
            score -= 1

    # 7. Price momentum
    ret_5d = (price / df["Close"].iloc[-6] - 1) * 100 if len(df) >= 6 else 0
    ret_20d = (price / df["Close"].iloc[-21] - 1) * 100 if len(df) >= 21 else 0
    signals.append(f"5-day return: {ret_5d:+.2f}% | 20-day return: {ret_20d:+.2f}%")

    # 8. ATR
    atr = latest["ATR"]
    atr_pct = atr / price * 100
    signals.append(f"ATR: ${atr:.2f} ({atr_pct:.1f}% of price) - {'High' if atr_pct > 3 else 'Normal'} volatility")

    # Determine final signal
    if score >= 4:
        signal = "STRONG BUY"
    elif score >= 2:
        signal = "BUY"
    elif score <= -4:
        signal = "STRONG SELL"
    elif score <= -2:
        signal = "SELL"
    else:
        signal = "HOLD"

    return signal, score, signals

# ---------- Charts ----------
def create_chart(df, ticker):
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=[f"{ticker} Price", "RSI", "MACD", "Volume"]
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="BB Upper",
                             line=dict(color="rgba(173,216,230,0.4)", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="BB Lower",
                             line=dict(color="rgba(173,216,230,0.4)", width=1),
                             fill="tonexty", fillcolor="rgba(173,216,230,0.1)"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20",
                             line=dict(color="#ff9800", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="SMA 50",
                             line=dict(color="#2196f3", width=1.5)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                             line=dict(color="#ab47bc", width=1.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.1)", line_width=0, row=2, col=1)

    colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_Hist"].dropna()]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="MACD Hist",
                         marker_color=colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                             line=dict(color="#2196f3", width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal",
                             line=dict(color="#ff9800", width=1.5)), row=3, col=1)

    vol_colors = ["#26a69a" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#ef5350"
                  for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
                         marker_color=vol_colors), row=4, col=1)

    fig.update_layout(
        height=800, xaxis_rangeslider_visible=False,
        template="plotly_dark", showlegend=False,
        margin=dict(t=40, b=20, l=50, r=20),
        font=dict(size=11)
    )
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_text="Vol", row=4, col=1)
    return fig

def create_portfolio_chart(portfolio):
    """Create portfolio value over time from transactions."""
    txns = portfolio["transactions"]
    if not txns:
        return None

    dates = [t["date"] for t in txns]
    values = [t["portfolio_value"] for t in txns]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values, mode="lines+markers",
        line=dict(color="#26a69a", width=2),
        fill="tozeroy", fillcolor="rgba(38,166,154,0.1)"
    ))
    fig.add_hline(y=STARTING_CASH, line_dash="dash", line_color="white",
                  annotation_text="Starting Capital")
    fig.update_layout(
        title="Portfolio Value Over Time",
        template="plotly_dark", height=300,
        yaxis_title="Value ($)", xaxis_title="",
        margin=dict(t=40, b=20, l=50, r=20)
    )
    return fig

# ---------- Trading Functions ----------
def execute_buy(ticker, shares, price, portfolio):
    cost = shares * price
    if cost > portfolio["cash"]:
        return False, "Insufficient funds"

    portfolio["cash"] -= cost
    if ticker in portfolio["holdings"]:
        holding = portfolio["holdings"][ticker]
        total_shares = holding["shares"] + shares
        total_cost = holding["avg_price"] * holding["shares"] + cost
        holding["avg_price"] = total_cost / total_shares
        holding["shares"] = total_shares
    else:
        portfolio["holdings"][ticker] = {
            "shares": shares,
            "avg_price": price,
        }

    # Calculate current portfolio value
    port_value = get_portfolio_value(portfolio)

    portfolio["transactions"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "BUY",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "total": cost,
        "cash_after": portfolio["cash"],
        "portfolio_value": port_value,
    })

    save_portfolio(portfolio)
    return True, f"Bought {shares} shares of {ticker} at ${price:.2f}"

def execute_sell(ticker, shares, price, portfolio):
    if ticker not in portfolio["holdings"]:
        return False, f"You don't own any {ticker}"

    holding = portfolio["holdings"][ticker]
    if shares > holding["shares"]:
        return False, f"You only own {holding['shares']} shares of {ticker}"

    revenue = shares * price
    portfolio["cash"] += revenue
    holding["shares"] -= shares

    if holding["shares"] == 0:
        del portfolio["holdings"][ticker]

    port_value = get_portfolio_value(portfolio)

    portfolio["transactions"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "SELL",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "total": revenue,
        "cash_after": portfolio["cash"],
        "portfolio_value": port_value,
    })

    save_portfolio(portfolio)
    return True, f"Sold {shares} shares of {ticker} at ${price:.2f}"

def get_portfolio_value(portfolio):
    total = portfolio["cash"]
    for ticker, holding in portfolio["holdings"].items():
        price = get_current_price(ticker)
        if price:
            total += holding["shares"] * price
    return total

def reset_portfolio():
    portfolio = {
        "cash": STARTING_CASH,
        "holdings": {},
        "transactions": [],
        "initial_value": STARTING_CASH,
    }
    save_portfolio(portfolio)
    return portfolio

# ---------- UI ----------
st.set_page_config(page_title="Stock Trader & Analyser", page_icon="$", layout="wide")

st.markdown("""
<style>
    .signal-buy { background: linear-gradient(135deg, #1b5e20, #2e7d32); color: white;
        padding: 20px; border-radius: 12px; text-align: center; font-size: 24px; font-weight: bold; }
    .signal-sell { background: linear-gradient(135deg, #b71c1c, #c62828); color: white;
        padding: 20px; border-radius: 12px; text-align: center; font-size: 24px; font-weight: bold; }
    .signal-hold { background: linear-gradient(135deg, #e65100, #f57c00); color: white;
        padding: 20px; border-radius: 12px; text-align: center; font-size: 24px; font-weight: bold; }
    .portfolio-card { background: linear-gradient(135deg, #1a237e, #283593); color: white;
        padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 10px; }
    .profit { color: #4caf50; font-weight: bold; }
    .loss { color: #f44336; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("Navigation")
    page = st.radio("", ["Market Analysis", "Paper Trading", "Portfolio"], label_visibility="collapsed")

    st.divider()
    st.header("Watchlist")
    watchlist = load_watchlist()

    new_ticker = st.text_input("Add ticker symbol", placeholder="e.g. AMZN").upper().strip()
    if st.button("Add to Watchlist", use_container_width=True) and new_ticker:
        if new_ticker not in watchlist:
            watchlist.append(new_ticker)
            save_watchlist(watchlist)
            st.success(f"Added {new_ticker}")
            st.rerun()
        else:
            st.warning(f"{new_ticker} already in watchlist")

    st.divider()
    st.subheader("Current Watchlist")
    for t in sorted(watchlist):
        col1, col2 = st.columns([3, 1])
        col1.write(t)
        if col2.button("X", key=f"del_{t}"):
            watchlist.remove(t)
            save_watchlist(watchlist)
            st.rerun()

    st.divider()
    period = st.selectbox("Chart Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)

    st.divider()
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("Data from Yahoo Finance | Paper Trading Simulator")

# ==================== PAGE: MARKET ANALYSIS ====================
if page == "Market Analysis":
    st.title("Market Analysis")

    if not watchlist:
        st.info("Add a ticker in the sidebar to get started.")
        st.stop()

    tabs = st.tabs(sorted(watchlist))

    for tab, ticker in zip(tabs, sorted(watchlist)):
        with tab:
            try:
                df, info = fetch_stock_data(ticker, period)
                if df.empty:
                    st.error(f"No data found for {ticker}. Check the ticker symbol.")
                    continue

                df = compute_indicators(df)
                signal, score, details = analyse_stock(df, info)
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                change = latest["Close"] - prev["Close"]
                change_pct = change / prev["Close"] * 100

                col_info, col_signal = st.columns([2, 1])
                with col_info:
                    name = info.get("shortName", ticker)
                    sector = info.get("sector", "N/A")
                    industry = info.get("industry", "N/A")
                    st.markdown(f"### {name} ({ticker})")
                    st.caption(f"{sector} | {industry}")

                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    mcol1.metric("Price", f"${latest['Close']:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
                    mcol2.metric("Day High", f"${latest['High']:.2f}")
                    mcol3.metric("Day Low", f"${latest['Low']:.2f}")
                    vol_fmt = f"{latest['Volume']/1e6:.1f}M" if latest['Volume'] > 1e6 else f"{latest['Volume']:,.0f}"
                    mcol4.metric("Volume", vol_fmt)

                with col_signal:
                    css_class = "signal-buy" if "BUY" in signal else ("signal-sell" if "SELL" in signal else "signal-hold")
                    st.markdown(f'<div class="{css_class}">{signal}<br><span style="font-size:14px">Score: {score:+.1f}</span></div>',
                                unsafe_allow_html=True)

                with st.expander("Fundamentals", expanded=False):
                    f1, f2, f3, f4, f5 = st.columns(5)
                    f1.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get('marketCap') else "N/A")
                    f2.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A'):.1f}" if isinstance(info.get('trailingPE'), (int, float)) else "N/A")
                    f3.metric("EPS", f"${info.get('trailingEps', 'N/A'):.2f}" if isinstance(info.get('trailingEps'), (int, float)) else "N/A")
                    f4.metric("Div Yield", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A")
                    f5.metric("52W Range", f"${info.get('fiftyTwoWeekLow', 0):.0f}-${info.get('fiftyTwoWeekHigh', 0):.0f}")

                    low52 = info.get('fiftyTwoWeekLow', 0)
                    high52 = info.get('fiftyTwoWeekHigh', 0)
                    if high52 > low52:
                        pct_in_range = (latest['Close'] - low52) / (high52 - low52) * 100
                        st.progress(min(pct_in_range / 100, 1.0), text=f"Price is at {pct_in_range:.0f}% of 52-week range")

                fig = create_chart(df, ticker)
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("Analysis Breakdown", expanded=True):
                    for detail in details:
                        if "Bullish" in detail or "Buy" in detail or "uptrend" in detail or "bounce" in detail:
                            st.markdown(f"- :green[{detail}]")
                        elif "Bearish" in detail or "Sell" in detail or "downtrend" in detail or "pullback" in detail:
                            st.markdown(f"- :red[{detail}]")
                        else:
                            st.markdown(f"- {detail}")

                    st.caption("**Disclaimer:** This is based on technical indicators only and is not financial advice.")

            except Exception as e:
                st.error(f"Error loading {ticker}: {str(e)}")

# ==================== PAGE: PAPER TRADING ====================
elif page == "Paper Trading":
    st.title("Paper Trading")
    st.caption("Trade with $100,000 virtual cash. Prices are real-time from Yahoo Finance.")

    portfolio = load_portfolio()

    # Portfolio summary at top
    port_value = get_portfolio_value(portfolio)
    total_pnl = port_value - portfolio["initial_value"]
    pnl_pct = (total_pnl / portfolio["initial_value"]) * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Value", f"${port_value:,.2f}", f"{total_pnl:+,.2f} ({pnl_pct:+.2f}%)")
    col2.metric("Cash Available", f"${portfolio['cash']:,.2f}")
    col3.metric("Invested", f"${port_value - portfolio['cash']:,.2f}")
    col4.metric("Total Trades", f"{len(portfolio['transactions'])}")

    st.divider()

    # Trading interface
    trade_col1, trade_col2 = st.columns([1, 1])

    with trade_col1:
        st.subheader("Buy Stock")
        buy_ticker = st.selectbox("Select stock to buy", sorted(watchlist), key="buy_ticker")
        buy_price = get_current_price(buy_ticker) if buy_ticker else None

        if buy_price:
            st.info(f"Current price of {buy_ticker}: **${buy_price:.2f}**")
            max_shares = int(portfolio["cash"] // buy_price)
            buy_shares = st.number_input(
                f"Number of shares (max: {max_shares})",
                min_value=1, max_value=max(max_shares, 1), value=1, step=1, key="buy_shares"
            )
            buy_cost = buy_shares * buy_price
            st.write(f"Total cost: **${buy_cost:,.2f}**")

            if st.button("Execute Buy", type="primary", use_container_width=True):
                success, msg = execute_buy(buy_ticker, buy_shares, buy_price, portfolio)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        elif buy_ticker:
            st.warning(f"Could not fetch price for {buy_ticker}")

    with trade_col2:
        st.subheader("Sell Stock")
        owned_tickers = list(portfolio["holdings"].keys())
        if owned_tickers:
            sell_ticker = st.selectbox("Select stock to sell", sorted(owned_tickers), key="sell_ticker")
            sell_price = get_current_price(sell_ticker) if sell_ticker else None

            if sell_price and sell_ticker in portfolio["holdings"]:
                holding = portfolio["holdings"][sell_ticker]
                st.info(f"Current price: **${sell_price:.2f}** | You own: **{holding['shares']} shares** | Avg cost: **${holding['avg_price']:.2f}**")

                pnl_per_share = sell_price - holding["avg_price"]
                pnl_color = "green" if pnl_per_share >= 0 else "red"
                st.markdown(f"P&L per share: :{pnl_color}[${pnl_per_share:+.2f} ({pnl_per_share/holding['avg_price']*100:+.1f}%)]")

                sell_shares = st.number_input(
                    f"Shares to sell (max: {holding['shares']})",
                    min_value=1, max_value=holding["shares"], value=1, step=1, key="sell_shares"
                )
                sell_revenue = sell_shares * sell_price
                st.write(f"Revenue: **${sell_revenue:,.2f}**")

                if st.button("Execute Sell", type="primary", use_container_width=True):
                    success, msg = execute_sell(sell_ticker, sell_shares, sell_price, portfolio)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.info("No holdings to sell. Buy some stocks first!")

    st.divider()

    # Quick trade from analysis recommendation
    st.subheader("AI-Suggested Trades")
    rec_cols = st.columns(min(len(watchlist), 5))
    for i, ticker in enumerate(sorted(watchlist)[:5]):
        with rec_cols[i]:
            try:
                df, info = fetch_stock_data(ticker, "6mo")
                if not df.empty and len(df) >= 50:
                    df = compute_indicators(df)
                    signal, score, _ = analyse_stock(df, info)
                    price = df.iloc[-1]["Close"]
                    css = "signal-buy" if "BUY" in signal else ("signal-sell" if "SELL" in signal else "signal-hold")
                    st.markdown(f"**{ticker}** ${price:.2f}")
                    st.markdown(f'<div class="{css}" style="padding:10px;font-size:14px">{signal}</div>', unsafe_allow_html=True)
            except:
                st.write(f"{ticker}: N/A")

    st.divider()

    # Recent transactions
    st.subheader("Recent Transactions")
    if portfolio["transactions"]:
        txn_df = pd.DataFrame(portfolio["transactions"][-20:][::-1])
        txn_df["total"] = txn_df["total"].apply(lambda x: f"${x:,.2f}")
        txn_df["price"] = txn_df["price"].apply(lambda x: f"${x:.2f}")
        txn_df["cash_after"] = txn_df["cash_after"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(
            txn_df[["date", "type", "ticker", "shares", "price", "total", "cash_after"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No transactions yet. Start trading!")

    # Reset button
    st.divider()
    if st.button("Reset Portfolio (Start Over with $100K)", type="secondary"):
        portfolio = reset_portfolio()
        st.success("Portfolio reset to $100,000!")
        st.rerun()

# ==================== PAGE: PORTFOLIO ====================
elif page == "Portfolio":
    st.title("Portfolio Dashboard")

    portfolio = load_portfolio()
    port_value = get_portfolio_value(portfolio)
    total_pnl = port_value - portfolio["initial_value"]
    pnl_pct = (total_pnl / portfolio["initial_value"]) * 100

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", f"${port_value:,.2f}", f"{pnl_pct:+.2f}%")
    col2.metric("Cash", f"${portfolio['cash']:,.2f}")
    invested = port_value - portfolio["cash"]
    col3.metric("Invested", f"${invested:,.2f}")
    col4.metric("Total P&L", f"${total_pnl:+,.2f}",
                f"{'Profit' if total_pnl >= 0 else 'Loss'}")

    # Portfolio value chart
    fig = create_portfolio_chart(portfolio)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Holdings breakdown
    st.subheader("Current Holdings")
    if portfolio["holdings"]:
        holdings_data = []
        for ticker, holding in portfolio["holdings"].items():
            current_price = get_current_price(ticker)
            if current_price:
                market_value = holding["shares"] * current_price
                cost_basis = holding["shares"] * holding["avg_price"]
                pnl = market_value - cost_basis
                pnl_pct_h = (pnl / cost_basis) * 100
                holdings_data.append({
                    "Ticker": ticker,
                    "Shares": holding["shares"],
                    "Avg Cost": f"${holding['avg_price']:.2f}",
                    "Current Price": f"${current_price:.2f}",
                    "Market Value": f"${market_value:,.2f}",
                    "Cost Basis": f"${cost_basis:,.2f}",
                    "P&L": f"${pnl:+,.2f}",
                    "P&L %": f"{pnl_pct_h:+.2f}%",
                    "% of Portfolio": f"{market_value/port_value*100:.1f}%",
                })

        holdings_df = pd.DataFrame(holdings_data)
        st.dataframe(holdings_df, use_container_width=True, hide_index=True)

        # Pie chart of allocation
        if holdings_data:
            labels = [h["Ticker"] for h in holdings_data]
            values = [float(h["Market Value"].replace("$", "").replace(",", "")) for h in holdings_data]
            if portfolio["cash"] > 0:
                labels.append("Cash")
                values.append(portfolio["cash"])

            fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
            fig_pie.update_layout(
                title="Portfolio Allocation",
                template="plotly_dark", height=400,
                margin=dict(t=40, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No holdings yet. Go to Paper Trading to buy stocks!")

    # Performance stats
    st.divider()
    st.subheader("Performance Statistics")
    if portfolio["transactions"]:
        txns = portfolio["transactions"]
        buys = [t for t in txns if t["type"] == "BUY"]
        sells = [t for t in txns if t["type"] == "SELL"]

        stat1, stat2, stat3, stat4 = st.columns(4)
        stat1.metric("Total Buys", len(buys))
        stat2.metric("Total Sells", len(sells))
        total_bought = sum(t["total"] for t in buys)
        total_sold = sum(t["total"] for t in sells)
        stat3.metric("Total Bought", f"${total_bought:,.2f}")
        stat4.metric("Total Sold", f"${total_sold:,.2f}")

        # Transaction history table
        st.subheader("Full Transaction History")
        all_txn_df = pd.DataFrame(txns[::-1])
        all_txn_df["total"] = all_txn_df["total"].apply(lambda x: f"${x:,.2f}")
        all_txn_df["price"] = all_txn_df["price"].apply(lambda x: f"${x:.2f}")
        all_txn_df["portfolio_value"] = all_txn_df["portfolio_value"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(
            all_txn_df[["date", "type", "ticker", "shares", "price", "total", "portfolio_value"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No transaction history yet.")
