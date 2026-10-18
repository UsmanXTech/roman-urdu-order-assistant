"""
Roman-Urdu Order Assistant - FastAPI backend.

Endpoints:
  GET  /               -> chat UI
  GET  /api/status     -> health + active LLM mode
  GET  /api/catalog    -> product catalog
  POST /api/chat       -> {message, session_id} -> {reply, order_state}
  POST /api/order      -> manual order submit -> {order_id}

Order flow (per session_id, in-memory state machine):
  idle -> collecting_name -> collecting_phone -> collecting_address
       -> collecting_item -> confirming -> done (saved to data/orders.jsonl)
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm import get_llm, RuleBasedBackend

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "catalog.json")
ORDERS_PATH = os.path.join(BASE_DIR, "data", "orders.jsonl")
STATIC_DIR = os.path.join(BASE_DIR, "static")

with open(CATALOG_PATH, encoding="utf-8") as f:
    CATALOG = json.load(f)

llm, LLM_MODE = get_llm(CATALOG)
print(f"[llm] active backend: {LLM_MODE}", flush=True)

app = FastAPI(title="Roman-Urdu Order Assistant")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# session_id -> {"step": str, "order": {...}}
SESSIONS = {}


class ChatIn(BaseModel):
    message: str
    session_id: str = "default"


class OrderIn(BaseModel):
    name: str
    phone: str
    address: str
    items: list  # [{id, size}]
    session_id: str = "default"


def _new_order():
    return {"name": None, "phone": None, "address": None, "items": []}


def _get_session(sid):
    s = SESSIONS.get(sid)
    if not s:
        s = {"step": "idle", "order": _new_order()}
        SESSIONS[sid] = s
    return s


def _find_item(text):
    """Reuse the rule-based product/size matchers for the order flow."""
    rb = RuleBasedBackend(CATALOG)
    return rb._find_product(text), rb._find_size(text)


def _digits(text):
    return re.sub(r"\D", "", text)


def _order_summary(order):
    lines = ["Order summary:"]
    total = 0
    for it in order["items"]:
        lines.append(f"- {it['name']} (Size {it['size']}): Rs. {it['price_pkr']:,}")
        total += it["price_pkr"]
    lines.append(f"Total: Rs. {total:,}")
    lines.append(f"Naam: {order['name']}, Phone: {order['phone']}")
    lines.append(f"Address: {order['address']}")
    return "\n".join(lines), total


def _save_order(order, session_id):
    order_id = "ORD-" + uuid.uuid4().hex[:6].upper()
    total = sum(it["price_pkr"] for it in order["items"])
    record = {
        "order_id": order_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "name": order["name"],
        "phone": order["phone"],
        "address": order["address"],
        "items": order["items"],
        "total_pkr": total,
        "status": "received",
    }
    os.makedirs(os.path.dirname(ORDERS_PATH), exist_ok=True)
    with open(ORDERS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return order_id, total


def _handle_order_flow(session, text):
    """Deterministic Roman-Urdu order collection. Returns (reply, done)."""
    order = session["order"]
    step = session["step"]
    t = text.strip()

    if step == "collecting_name":
        if len(t) < 2:
            return "Naam thora wazeh likhein please.", False
        order["name"] = t
        session["step"] = "collecting_phone"
        return (f"Shukriya {t}! Ab apna phone number likhein "
                "(masalan 0300-1234567).", False)

    if step == "collecting_phone":
        d = _digits(t)
        if not (10 <= len(d) <= 13):
            return "Phone number samajh nahi aaya. 11 digits wala number likhein.", False
        order["phone"] = d
        session["step"] = "collecting_address"
        return "Number note kar liya. Ab delivery address likhein.", False

    if step == "collecting_address":
        if len(t) < 8:
            return "Address thora detail se likhein (gali/mohalla + city).", False
        order["address"] = t
        session["step"] = "collecting_item"
        return ("Address save ho gaya. Ab item aur size batayein, "
                "masalan 'kurta size L' ya 'jeans 32'."), False

    if step == "collecting_item":
        product, size = _find_item(t)
        if not product:
            return ("Item samajh nahi aaya. Ye items hain: " +
                    ", ".join(i["name"] for i in CATALOG["items"][:6]) +
                    "... naam ke saath size likhein.", False)
        if not size:
            avail = ", ".join(s for s, q in product["sizes"].items() if q > 0)
            return (f"{product['name']} mil gaya! Size batayein ({avail}).", False)
        if size not in product["sizes"] or product["sizes"][size] <= 0:
            avail = ", ".join(s for s, q in product["sizes"].items() if q > 0)
            return (f"Maaf kijiye, {product['name']} mein size {size} khatam hai. "
                    f"Available: {avail}.", False)
        order["items"].append({
            "id": product["id"], "name": product["name"],
            "size": size, "price_pkr": product["price_pkr"],
        })
        session["step"] = "confirming"
        summary, _ = _order_summary(order)
        return (summary + "\n\nYe order confirm karun? 'haan' ya 'naheen' likhein.", False)

    if step == "confirming":
        tl = t.lower()
        if any(w in tl for w in ["haan", "han", "yes", "confirm", "theek", "ok"]):
            order_id, total = _save_order(order, session.get("sid", ""))
            session["step"] = "idle"
            session["order"] = _new_order()
            return (f"Order confirm ho gaya! Order ID: {order_id}. "
                    f"Total Rs. {total:,} (Cash on Delivery). "
                    f"Shukriya, jald rabta karenge!", True)
        if any(w in tl for w in ["naheen", "nahi", "nahin", "no", "cancel"]):
            session["step"] = "idle"
            session["order"] = _new_order()
            return "Koi baat nahi, order cancel kar diya. Kuch aur chahiye ho to batayein.", True
        return "Please 'haan' likhein confirm karne ke liye, ya 'naheen' cancel ke liye.", False

    return None, False


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/status")
def status():
    return {
        "ok": True,
        "shop": CATALOG["shop"]["name"],
        "llm_mode": LLM_MODE,
        "items": len(CATALOG["items"]),
    }


@app.get("/api/catalog")
def catalog():
    return CATALOG


@app.post("/api/chat")
def chat(inp: ChatIn):
    session = _get_session(inp.session_id)
    session["sid"] = inp.session_id
    text = inp.message.strip()
    if not text:
        return {"reply": "Kuch likhein to mein jawab dun!", "order_state": session["step"]}

    # 1) continue an in-progress order flow
    if session["step"] != "idle":
        reply, _ = _handle_order_flow(session, text)
        return {"reply": reply, "order_state": session["step"]}

    # 2) detect fresh order intent
    tl = text.lower()
    if any(w in tl for w in ["order", "mangwana", "book kar", "khareedna", "lena hai"]):
        session["step"] = "collecting_name"
        return {"reply": ("Zaroor! Order ke liye pehle aapka naam chahiye. "
                          "Apna naam likhein."), "order_state": session["step"]}

    # 3) free-form: let the LLM backend reply
    try:
        reply = llm.generate(text)
    except Exception as e:
        print(f"[llm] error: {e}, using fallback text", flush=True)
        reply = ("Maaf kijiye, abhi jawab nahi de saka. Dobara koshish karein "
                 "ya 'sab dikhao' likhein.")
    return {"reply": reply, "order_state": session["step"]}


@app.post("/api/order")
def place_order(inp: OrderIn):
    order = _new_order()
    order["name"] = inp.name
    order["phone"] = _digits(inp.phone)
    order["address"] = inp.address
    for req in inp.items:
        match = next((i for i in CATALOG["items"] if i["id"] == req.get("id")), None)
        if not match:
            return {"ok": False, "error": f"unknown item id: {req.get('id')}"}
        size = req.get("size")
        if size not in match["sizes"] or match["sizes"][size] <= 0:
            return {"ok": False, "error": f"size {size} unavailable for {match['name']}"}
        order["items"].append({
            "id": match["id"], "name": match["name"],
            "size": size, "price_pkr": match["price_pkr"],
        })
    if not order["items"]:
        return {"ok": False, "error": "no items"}
    order_id, total = _save_order(order, inp.session_id)
    return {"ok": True, "order_id": order_id, "total_pkr": total}
