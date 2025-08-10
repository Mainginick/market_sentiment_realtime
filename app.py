
import os
import time
import threading
from datetime import datetime, timezone
from collections import defaultdict

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ----------------------
# Config
# ----------------------
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "20"))
TICKERS = os.environ.get("TICKERS", "ES=F,NQ=F,^GSPC,^NDX,AAPL,MSFT,EURUSD=X,GBPUSD=X,USDJPY=X,USDCAD=X,USDCHF=X,AUDUSD=X").split(",")
ANALYZER = SentimentIntensityAnalyzer()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev-key")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")  # eventlet in Procfile

# in-memory cache
state = {
    "last_update": None,
    "quotes": {},
    "sentiment": {},
}

# friendly names
ALIASES = {
    "ES=F": "S&P 500 Futures (ES)",
    "NQ=F": "Nasdaq 100 Futures (NQ)",
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCAD=X": "USD/CAD",
    "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
}

def compute_sentiment_for_symbol(sym):
    """Pull recent news (when available) from yfinance and compute VADER compound score."""
    try:
        t = yf.Ticker(sym)
        # yfinance .news can be missing for FX; if so, try a proxy symbol like ^GSPC
        news_items = getattr(t, "news", []) or []
        if not news_items:
            # fallback to general market news to avoid empty sentiment
            news_items = getattr(yf.Ticker("^GSPC"), "news", []) or []

        scores = []
        titles = []
        for item in news_items[:15]:
            title = item.get("title") or ""
            if not title:
                continue
            s = ANALYZER.polarity_scores(title)["compound"]
            scores.append(s)
            titles.append({"title": title, "score": s, "link": item.get("link")})
        if not scores:
            return {"score": 0.0, "samples": []}
        avg = sum(scores) / len(scores)
        return {"score": round(avg, 4), "samples": titles[:6]}
    except Exception as e:
        return {"score": 0.0, "samples": [], "error": str(e)[:120]}

def fetch_quotes():
    """Fetch latest prices and daily change for all symbols."""
    data = {}
    try:
        y = yf.Tickers(" ".join(TICKERS))
        for sym in TICKERS:
            tk = y.tickers.get(sym) or yf.Ticker(sym)
            hist = tk.history(period="1d", interval="1m")
            last_price = None
            pct = None
            if not hist.empty:
                last_price = float(hist["Close"][-1])
                open_price = float(hist["Open"][0])
                if open_price:
                    pct = (last_price - open_price) / open_price * 100.0
            data[sym] = {
                "symbol": sym,
                "name": ALIASES.get(sym, sym),
                "last": last_price,
                "changePct": pct,
            }
    except Exception as e:
        # Best-effort; keep partials
        pass
    return data

def refresh_loop():
    while True:
        quotes = fetch_quotes()
        sentiments = {}
        for sym in TICKERS:
            sentiments[sym] = compute_sentiment_for_symbol(sym)
        state["quotes"] = quotes
        state["sentiment"] = sentiments
        state["last_update"] = datetime.now(timezone.utc).isoformat()
        socketio.emit("snapshot", state)
        socketio.sleep(REFRESH_SECONDS)

@app.route("/")
def index():
    return render_template("index.html", tickers=TICKERS, aliases=ALIASES)

@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/api/snapshot")
def api_snapshot():
    return jsonify(state)

if __name__ == "__main__":
    # Start background task
    socketio.start_background_task(refresh_loop)
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
