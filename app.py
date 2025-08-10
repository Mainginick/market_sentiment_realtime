
import os, threading
from datetime import datetime, timezone
from collections import defaultdict

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler

# Providers
from providers.alpha_vantage_provider import AlphaVantageProvider
from providers.newsapi_provider import NewsAPIProvider
from providers.finnhub_provider import FinnhubProvider
from providers.sentiment import SentimentEngine

INSTRUMENTS = {
    "forex": ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD"],
    "indices": ["ES","NQ"]
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev-key")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Setup providers from env
providers = []
if os.environ.get("ALPHA_VANTAGE_API_KEY"):
    providers.append(AlphaVantageProvider(os.environ["ALPHA_VANTAGE_API_KEY"]))
if os.environ.get("NEWSAPI_API_KEY"):
    providers.append(NewsAPIProvider(os.environ["NEWSAPI_API_KEY"]))
if os.environ.get("FINNHUB_API_KEY"):
    providers.append(FinnhubProvider(os.environ["FINNHUB_API_KEY"]))

sentiment_engine = SentimentEngine()

state = {
    "last_updated": None,
    "prices": {},
    "sentiment": {},
    "headlines": defaultdict(list),
    "errors": []
}
lock = threading.Lock()

def merge_sentiment(entries):
    if not entries:
        return None
    score = sum(e[0] for e in entries) / len(entries)
    sources = list({e[1] for e in entries})
    return {"score": score, "samples": len(entries), "sources": sources}

def poll_once():
    local_errors = []
    sentiments_acc = defaultdict(list)

    for p in providers or []:
        try:
            prices = p.get_prices(INSTRUMENTS) or {}
            headlines = p.get_headlines(INSTRUMENTS) or {}
        except Exception as e:
            local_errors.append(f"{p.name}: {e}")
            continue

        for sym, v in prices.items():
            state["prices"][sym] = v

        for sym, items in headlines.items():
            enriched = []
            for item in items:
                txt = f"{item.get('title','')} {item.get('summary','')}"
                score = sentiment_engine.score(txt)
                enriched.append({
                    "title": item.get("title"),
                    "summary": item.get("summary",""),
                    "url": item.get("url"),
                    "source": item.get("source"),
                    "time": item.get("time"),
                    "score": score
                })
                sentiments_acc[sym].append((score, p.name, item))
            prev = state["headlines"].get(sym, [])
            combined = (enriched + prev)[:20]
            seen = set()
            uniq = []
            for it in combined:
                t = it.get("title","")
                if t in seen: continue
                seen.add(t)
                uniq.append(it)
            state["headlines"][sym] = uniq

    for sym, entries in sentiments_acc.items():
        state["sentiment"][sym] = merge_sentiment(entries)

    with lock:
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        state["errors"] = local_errors

    socketio.emit("snapshot", snapshot())

def snapshot():
    with lock:
        return {
            "last_updated": state["last_updated"],
            "prices": state["prices"],
            "sentiment": state["sentiment"],
            "headlines": state["headlines"],
            "errors": state["errors"],
            "instruments": INSTRUMENTS
        }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/snapshot")
def api_snapshot():
    return jsonify(snapshot())

@app.route("/healthz")
def healthz():
    return "ok", 200

@socketio.on("connect")
def on_connect():
    emit("snapshot", snapshot())

def start_scheduler():
    interval = int(os.environ.get("POLL_SECONDS", "30"))
    sched = BackgroundScheduler()
    sched.add_job(poll_once, "interval", seconds=interval, max_instances=1, coalesce=True)
    sched.start()
    poll_once()

# Start scheduler under Gunicorn only once
if not getattr(app, "_scheduler_started", False):
    start_scheduler()
    app._scheduler_started = True

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
