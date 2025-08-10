# Market Sentiment (Real‑Time) — Render Ready

**What it does**
- Streams real‑time(ish) snapshots every ~20s via WebSockets (Flask‑SocketIO + eventlet)
- Pulls quotes for major FX pairs and equity indices/futures (ES, NQ, etc.) using `yfinance`
- Computes live sentiment from recent news headlines with `vaderSentiment` (no API keys needed)
- Simple Bootstrap UI cards with price %, and sentiment score + linked headlines

**Deploy (Render)**
1. Push this folder to a new GitHub repo.
2. Create **New → Web Service** in Render and connect the repo.
3. Render uses this:
   - Build: `pip install --upgrade pip && pip install -r requirements.txt`
   - Start: `gunicorn -k eventlet -w 1 -t 120 app:app`
   - Health check: `/healthz`
4. Optional env vars:
   - `REFRESH_SECONDS` (default 20)
   - `TICKERS` comma list (default covers ES, NQ, majors)

**Runtime**
- WebSockets served by eventlet worker; don’t scale to multiple workers on Free plan (stick to `-w 1`).
- No database required.

**Customize Tickers**
Set `TICKERS=ES=F,NQ=F,^GSPC,^NDX,AAPL,MSFT,EURUSD=X,GBPUSD=X,USDJPY=X` in Render → Environment.

**Notes**
- yfinance scrapes Yahoo; subject to rate throttles. This is for educational/dash display only.
- True tick-by-tick “real time” needs paid market data + vendor websockets.
