# Prediction Arena

[中文 →](README.md) · English

A binary-forecasting demo built for **ICDM 2026 · Shenyang, China**.

Participants state a YES probability for a past event, compare it with a real pre-event prediction-market snapshot, then score their confidence with the Brier Score — a hands-on introduction to probability calibration.

## Run

```bash
cd prediction-arena
pip install -r requirements.txt
python app.py          # on Windows: double-click start_arena.bat
```

- Participants: open `http://<notebook-ip>:5000/` on the same Wi-Fi
- Organizer dashboard: `http://127.0.0.1:5000/dashboard`
- After changing networks: `python make_qrcode.py --print`
- Pre-event checklist: `python preflight.py`

## What's inside

- 150 scored questions + 3 warm-up, 30 per category; bilingual ZH/EN interface
- Public historical snapshots from Polymarket / Manifold / Kalshi / Betfair Exchange
- Local Flask + SQLite only — no server, domain, ICP filing or internet connection needed
- Full documentation: [prediction-arena/README.md](prediction-arena/README.md)

> For educational display only — no trading, betting or payments. Display licensing for the source platforms is still pending manual review.
