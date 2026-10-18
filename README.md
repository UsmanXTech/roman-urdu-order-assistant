# Roman-Urdu Order Assistant

A chatbot side-hustle for small clothing sellers in Pakistan: customers chat in
Roman Urdu, ask about products/prices/sizes, and place orders — no app install,
no English required. Built for DEV Hacktoberfest Week 2 "Side Hustle".

## How it works

```
[ Chat UI (mobile-friendly) ] --fetch--> [ FastAPI ] --generate()--> [ LLM layer ]
                                                              |-> Ollama + Gemma (if available)
                                                              |-> Rule-based Roman-Urdu engine (offline fallback)
[ Order flow ] --> saved to data/orders.jsonl
```

## Quick start

```bash
cd hacktoberfest-week2
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — chat away. Try: `sab dikhao`, `kurta ki qimat`,
`jeans mein kaunse sizes hain`, `order karna hai`.

## LLM modes

`llm.py` exposes one interface — `generate(prompt)` — with two backends:

| Mode | Backend | When active |
|------|---------|-------------|
| `ollama/gemma2:2b` | Gemma open-weight model via local Ollama | Ollama running **and** model pulled |
| `rule-based (offline fallback)` | Deterministic Roman-Urdu intent engine | Always available |

`get_llm()` auto-detects at startup. Check the active mode:

```bash
curl localhost:8000/api/status
# {"ok": true, "llm_mode": "rule-based (offline fallback)", ...}
```

**To activate Gemma** (needs ~4GB RAM free):

```bash
# install Ollama: https://ollama.com/download
ollama pull gemma2:2b        # or: LLM_MODEL=gemma2:9b ollama pull gemma2:9b
ollama serve
python -m uvicorn app:app
```

Set `LLM_MODEL` / `OLLAMA_HOST` env vars to customize. The sandbox this was
developed in only had ~1GB free RAM, so the demo runs on the rule-based engine —
same API, same replies shape; Gemma takes over automatically wherever it can run.

## API

- `GET /` — chat UI
- `GET /api/status` — health + active LLM mode
- `GET /api/catalog` — product catalog (JSON)
- `POST /api/chat` — `{"message": str, "session_id": str}` → `{"reply": str, "order_state": str}`
- `POST /api/order` — direct order submit `{"name","phone","address","items":[{"id","size"}]}`

Order conversation states: `idle → collecting_name → collecting_phone →
collecting_address → collecting_item → confirming → idle`. Orders append to
`data/orders.jsonl` (git-ignored).

## Deploy (Render free tier — planned)

1. Push this repo to GitHub.
2. Render → New Web Service → connect repo.
3. Build: `pip install -r requirements.txt` · Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Add a persistent disk for `data/` if you want orders to survive restarts.

## Structure

```
app.py            FastAPI app + order state machine
llm.py            LLM abstraction (Ollama/Gemma + rule-based fallback)
catalog.json      10 clothing items, PKR prices, sizes/stock
static/index.html mobile-friendly chat UI (vanilla JS)
data/orders.jsonl placed orders (created at runtime, git-ignored)
requirements.txt
```

## Limitations / roadmap

- One shop, one catalog file — multi-tenant seller accounts are the obvious next step.
- Rule-based engine covers the happy paths; Gemma handles free-form chat better.
- No payment integration yet — Cash on Delivery only.
- Order notifications (SMS/WhatsApp to the seller) not built yet.
