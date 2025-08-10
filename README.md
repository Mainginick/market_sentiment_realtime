
# Market Speculation — Railway

**Deploy on Railway**

1) Push this folder to GitHub → Railway → New Project → Deploy from GitHub.
2) Variables:
   - SECRET_KEY = any-random-string
   - POLL_SECONDS = 30
   - (optional) ALPHA_VANTAGE_API_KEY, NEWSAPI_API_KEY, FINNHUB_API_KEY
3) Start Command: `gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT -t 120 app:app`
4) Visit your URL.

Troubleshooting: check Deployments → Logs. We fail-safe sentiment and handle missing API keys.
