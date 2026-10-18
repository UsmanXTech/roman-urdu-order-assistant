"""
LLM abstraction layer.

Single interface: generate(prompt, context=None) -> str

Two backends:
  1. OllamaBackend  - Gemma open-weight model via local Ollama (LLM_MODEL env, default gemma2:2b)
  2. RuleBasedBackend - offline Roman-Urdu intent engine (no model needed)

get_llm() auto-detects: if Ollama is reachable with the model, use it;
otherwise fall back to the rule-based engine so the demo always works.
"""

import json
import os
import re
import urllib.request

SYSTEM_PROMPT = """\
You are a friendly shop assistant for a small clothing store in Lahore, Pakistan.
You ALWAYS reply in Roman Urdu (Urdu written in Latin script), short and warm.
You help customers with: product questions, prices (in PKR), size availability, and taking orders.
Keep replies to 1-3 short sentences. Never invent products or prices not given to you.
If the customer wants to order, ask for: name, phone number, delivery address, item + size.
"""


# ---------------------------------------------------------------------------
# Backend 1: Ollama + Gemma
# ---------------------------------------------------------------------------

class OllamaBackend:
    def __init__(self, model=None, host=None):
        self.model = model or os.environ.get("LLM_MODEL", "gemma2:2b")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self._name = f"ollama/{self.model}"

    @property
    def name(self):
        return self._name

    def is_available(self, timeout=3):
        try:
            req = urllib.request.Request(self.host + "/api/tags")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(self.model in m for m in models)
        except Exception:
            return False

    def generate(self, prompt, context=None):
        full_prompt = SYSTEM_PROMPT + "\nCustomer: " + prompt + "\nAssistant:"
        payload = json.dumps({
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 150},
        }).encode()
        req = urllib.request.Request(
            self.host + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        return data.get("response", "").strip()


# ---------------------------------------------------------------------------
# Backend 2: Rule-based Roman-Urdu engine (offline fallback)
# ---------------------------------------------------------------------------

class RuleBasedBackend:
    """Deterministic Roman-Urdu shop assistant. No model needed."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.items = catalog["items"]

    @property
    def name(self):
        return "rule-based (offline fallback)"

    @staticmethod
    def _norm(text):
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _find_product(self, text):
        t = self._norm(text)
        keywords = {
            "msk-01": ["shalwar kameez", "shalwar", "suit mard", "gents suit"],
            "mkur-02": ["kurta", "kurty"],
            "lkur-03": ["kurti", "kurty ladies"],
            "l3pc-04": ["3 piece", "3piece", "three piece", "lawn suit"],
            "mjea-05": ["jeans", "pant", "denim pant"],
            "mts-06": ["t shirt", "tshirt", "tee"],
            "mho-07": ["hoodie", "hood"],
            "mdj-08": ["jacket", "denim jacket"],
            "ksk-09": ["bachon", "bacha", "kids", "baby"],
            "ldp-10": ["dupatta", "dupata", "shawl", "chadar"],
        }
        for item in self.items:
            for kw in keywords.get(item["id"], []):
                if kw in t:
                    return item
            # also match against roman_urdu name words
            for word in self._norm(item["roman_urdu"]).split():
                if len(word) > 3 and word in t.split():
                    return item
        return None

    @staticmethod
    def _find_size(text):
        t = " " + RuleBasedBackend._norm(text) + " "
        for s in ["xl", "xxl"]:
            if f" {s} " in t:
                return s.upper()
        for s in ["s", "m", "l"]:
            if f" {s} " in t:
                return s.upper()
        m = re.search(r"\b(30|32|34|36)\b", t)
        if m:
            return m.group(1)
        if "one size" in t:
            return "One Size"
        return None

    def _fmt_item(self, item):
        sizes = ", ".join(
            f"{s} ({q} available)" if q > 0 else f"{s} (khatam)"
            for s, q in item["sizes"].items()
        )
        return (
            f"{item['name']} — Rs. {item['price_pkr']:,}. "
            f"Sizes: {sizes}. {item['description']}"
        )

    def _list_all(self):
        lines = ["Hamare paas ye items hain:\n"]
        for it in self.items:
            lines.append(f"- {it['name']}: Rs. {it['price_pkr']:,}")
        lines.append("\nKisi bhi item ka naam likhein, mein detail bata dunga!")
        return "\n".join(lines)

    def generate(self, prompt, context=None):
        t = self._norm(prompt)
        product = self._find_product(prompt)
        size = self._find_size(prompt)

        # order intent is handled by the app's state machine; here we just nudge
        if any(w in t for w in ["order", "mangwana", "book kar", "lena hai", "khareedna", "buy"]):
            return ("Zaroor! Order ke liye mujhe ye details chahiye: aapka naam, "
                    "phone number, aur delivery address. Pehle naam bata dein?")

        if any(w in t for w in ["salam", "assalam", "aoa", "hello", "hi ", " hey", "adaab"]):
            return ("Walaikum Assalam! Usman Clothing Store mein khush aamdeed. "
                    "Kapron ke baare mein kuch poochna hai ya order karna hai?")

        if any(w in t for w in ["shukriya", "thanks", "thank you", "meherbani"]):
            return "Khush aamdeed! Aur kuch chahiye ho to zaroor batayein."

        if any(w in t for w in ["allah hafiz", "khuda hafiz", "bye", "phir milenge"]):
            return "Allah Hafiz! Phir zaroor tashreef layein."

        if any(w in t for w in ["delivery", "pahunch", "pohnch", "kitne din", "dc charges", "cash on"]):
            return ("Delivery " + self.catalog["shop"]["delivery_note"])

        if any(w in t for w in ["qimat", "qeemat", "keemat", "price", "rate", "kitne ka", "kitnay ka",
                                "pese", "paisa", "daam"]):
            if product:
                return f"{product['name']} ki qimat Rs. {product['price_pkr']:,} hai."
            return ("Kis item ki qimat poochni hai? Naam likhein, masalan 'kurta ki qimat'.")

        if any(w in t for w in ["size", "naap", "bara", "chota", "fit"]):
            if product:
                avail = ", ".join(f"{s}" for s, q in product["sizes"].items() if q > 0)
                return f"{product['name']} mein ye sizes available hain: {avail}."
            return "Kis item ka size poochna hai? Item ka naam bhi likhein."

        if any(w in t for w in ["dikhao", "show", "kya kya", "kya hai", "items", "products",
                                "kapre", "kapray", "collection", "veriety", "variety", "sab"]):
            return self._list_all()

        if product:
            return self._fmt_item(product)

        if size and not product:
            return "Size to samajh gaya, lekin item ka naam bhi batayein taake check kar sakun."

        if any(w in t for w in ["kese ho", "kaise ho", "kia haal"]):
            return "Mein theek hoon, shukriya! Aap sunayein — kapron mein kya dekhna hai?"

        return ("Maaf kijiye, samajh nahi aaya. Aap item ka naam likh kar qimat ya size "
                "pooch sakte hain, ya 'sab dikhao' likhein poori list ke liye.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm(catalog=None):
    """Return (backend, active_name). Prefers Ollama/Gemma, else rule-based."""
    ollama = OllamaBackend()
    if ollama.is_available():
        return ollama, ollama.name
    rb = RuleBasedBackend(catalog or {"items": [], "shop": {"delivery_note": ""}})
    return rb, rb.name
