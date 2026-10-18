<!--
PUBLISHING CHECKLIST — ye notes post ka hissa NAHI hain, publish se pehle delete kar dena:
1. DEV editor me sidebar me ye 2 tags lagana (required): devchallenge, hf26challenge
2. https://github.com/UsmanXTech/roman-urdu-order-assistant ki jagah GitHub repo ka link — apni line par paste karne se DEV repo auto-embed kar dega
3. [RENDER_URL] ki jagah Render wali live demo link (deploy ke baad)
4. Deadline: Monday Oct 19, 11:59 AM PKT (Oct 18, 11:59 PM PDT) — raat ko hi publish kar dena safe rahega
5. Agar Render deploy deadline tak live na ho sake to Demo section me 2-min ki screen recording laga dena — template "deployed link OR video demo" mangta hai
6. Prize Categories me "Best Use of Render" sirf tab rakho agar Render par deploy live hai; "Best Use of Gemma" har soorat me valid hai
-->

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

# I Built a Roman-Urdu Order Assistant for Small Clothing Sellers 🇵🇰

*My DEV Hacktoberfest Week 2 "Side Hustle" entry — an AI chatbot that lets
Pakistan's small clothing shops take orders in the language their customers
actually type in.*

## What I Built

### The problem

Thousands of small clothing sellers in Pakistan run their business on WhatsApp.
A customer messages "kurta ki qimat?", the seller is busy with a walk-in
customer, the reply comes 3 hours late — and the sale is gone.

The deeper issue is language. These customers type in **Roman Urdu** — Urdu
written in Latin script. Every off-the-shelf chatbot expects clean English.
Every "AI for business" demo is in English. The sellers who need help most are
locked out by a language barrier nobody built for.

### The side hustle

A drop-in order assistant for a clothing shop:

- Customer opens a simple chat page on their phone — no app install
- Asks in Roman Urdu: *"kurta ki qimat kya hai?"*, *"jeans mein kaunse sizes hain?"*
- The bot answers from the shop's real catalog (PKR prices, live sizes)
- Say *"order karna hai"* and it collects name → phone → address → item + size,
  shows a summary, confirms, and saves the order
- The seller gets every order in a clean log, ready to pack and ship (COD)

No English required. No training required. It meets the customer where they
already are.

**Who would pay for it:** the shop owner. One recovered sale a week pays for
the whole thing — and the pitch writes itself: "kabhi customer ka reply late
nahi hoga."

## Demo

**Live demo:** [RENDER_URL]

Ya locally try karo:

```bash
git clone https://github.com/UsmanXTech/roman-urdu-order-assistant && cd roman-urdu-order-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --port 8000
# open http://localhost:8000
```

Try: `sab dikhao` → `kurta ki qimat` → `order karna hai`, then walk the order
flow. With Ollama running (`ollama pull gemma2:2b`), the bot uses Gemma;
otherwise the offline engine answers — check `/api/status` to see which.

## Code

https://github.com/UsmanXTech/roman-urdu-order-assistant

Full source is open: Python + FastAPI backend, vanilla-JS chat UI, a
`catalog.json` any shop owner can edit without touching code, and orders
appended to a JSONL log. The LLM layer is one `generate(prompt)` interface —
swap `gemma2:2b` for any Ollama model with a single config change.

## How I Built It

**Stack:** Python + FastAPI backend, vanilla-JS chat UI, and **Gemma** —
Google's open-weight model — served locally via **Ollama** for the Roman-Urdu
conversation layer.

Why this stack:
- **Gemma (open weights):** a small seller can't pay per-token API bills. An
  open model running on cheap hardware (or even the shop's own laptop) means
  the unit economics actually work at Pakistani retail margins.
- **Ollama:** one command to serve the model, clean HTTP API, trivial to swap
  `gemma2:2b` for a bigger variant later.
- **FastAPI:** the order state machine (name → phone → address → item →
  confirm) is deterministic code, not LLM vibes — the model handles
  conversation, the code handles correctness. Phone numbers get validated,
  out-of-stock sizes get rejected, every order lands in a JSONL log.
- **Pragmatic fallback:** the LLM layer is a single `generate(prompt)`
  interface. Where Gemma can't run (tiny VPS, demo sandbox), a rule-based
  Roman-Urdu engine keeps every flow working offline. Same API, same replies
  shape — Gemma takes over automatically wherever it can run.

**Deploy:** Render free tier — `render.yaml` blueprint, `pip install -r
requirements.txt`, start with uvicorn, done. A free-tier web service is all a
single shop needs to start; that's the whole point of the hustle being
*deployable*, not just demoable.

## Why Does Open Innovation Matter?

Three reasons, all of them load-bearing for this project:

1. **The math only works open.** A per-token closed API turns every customer
   chat into a meter running against a shop's razor-thin margins. Gemma's
   open weights cost $0 at the margin — the bot can chat all day and the
   shop's bill doesn't move. With a closed API this side hustle is a
   subscription product; with open weights it's a one-time setup.
2. **Customer data never leaves the shop.** Names, phone numbers, home
   addresses — with a closed API, all of that flows to someone else's
   servers. With a locally-run open model, it stays on the shop's own
   machine. For customers trusting a small seller with their address, that
   matters.
3. **The niche belongs to open.** No closed model is tuned for Roman-Urdu
   shop banter — it's too small a market for the big labs to care about.
   Open weights can be fine-tuned on real shop conversations (that's the
   roadmap), which means the smallest languages get the best models, not the
   leftovers.

## My First User

My own clothing shop in Lahore.

I'm not building this for a hypothetical persona — I run a small clothing
business, and I watched orders slip through the exact cracks described above.
So the first deployment target is my own shop: my catalog, my prices, my
customers typing "bhai kurta kitne ka hai?" at 11pm.

That changed how I built it. The catalog has real items (shalwar kameez,
kurtis, jeans, hoodies — sizes S–XL, prices in PKR). The delivery note says
"2-3 din Lahore, 4-5 din baqi cities, COD available" because that's the actual
policy. If it can't survive my shop's WhatsApp rush, it doesn't ship.

## Prize Categories

- **Best Use of Gemma** — the entire conversation layer is built around
  Gemma's open weights served via Ollama; the `generate()` interface is
  model-first, with the rule-based engine strictly as an offline fallback.
- **Best Use of Render** — one-click deploy from the `render.yaml` blueprint
  on Render's free tier; the live demo above runs there.

## Honest limitations

- One shop, one catalog file. Multi-seller accounts are the real product — that's the roadmap.
- The rule-based engine covers happy paths; genuinely free-form chat wants the Gemma backend.
- No payments yet — Cash on Delivery only, which honestly matches how these shops operate today.
- No seller notifications (SMS/WhatsApp ping on new order) — next build.

## Roadmap

1. Seller dashboard: today's orders, low-stock alerts
2. WhatsApp integration (where the customers already live)
3. Multi-tenant: one deployment, many shops, each with their own catalog
4. Fine-tune a small model on real Roman-Urdu shop conversations

---

*Built with open weights and a free-tier deploy because the sellers this is for
can't afford anything else. If you run a small shop — or know someone who does
— I'd love to hear what would make this actually useful. Repo: https://github.com/UsmanXTech/roman-urdu-order-assistant*
