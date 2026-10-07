"""Shared helpers: size parsing, row building, snapshot + history writing."""
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = DATA_DIR / "prices.json"
HISTORY = DATA_DIR / "history.csv"

FIELDS = [
    "date", "chain", "store_id", "store_name", "region", "product_id", "barcode",
    "name", "flavour", "image", "size_ml", "pack_count", "price", "was_price", "promo_text",
    "promo_ends", "on_special", "price_per_can", "price_per_100ml", "available",
]


def nz_now():
    return datetime.now(ZoneInfo("Pacific/Auckland"))


def nz_today():
    return nz_now().date().isoformat()


def _to_ml(value, unit):
    v = float(value)
    return v * 1000 if unit.lower() == "l" else v


def parse_size(text):
    """Return (ml_per_can, pack_count) from text like '4 x 500ml', '500ml x 4', '12pk', '1.5L'."""
    t = (text or "").lower().replace("×", "x")
    m = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(ml|l)\b", t)
    if m:
        return _to_ml(m[2], m[3]), int(m[1])
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ml|l)\b\s*x\s*(\d+)", t)
    if m:
        return _to_ml(m[1], m[2]), int(m[3])
    ml, pack = None, 1
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ml|l)\b", t)
    if m:
        ml = _to_ml(m[1], m[2])
    m = re.search(r"(\d+)\s*(?:pk|pack)\b", t)
    if m:
        pack = int(m[1])
    return ml, pack


def build_row(chain, store, product_id, name, price, barcode="", was_price=None,
              promo_text="", promo_ends="", size_text="", available=True, image=""):
    ml, pack = parse_size(f"{name} {size_text}")
    price = round(float(price), 2) if price is not None else None
    was_price = round(float(was_price), 2) if was_price else None
    on_special = bool(price is not None and ((was_price and was_price > price) or promo_text))
    per_can = round(price / pack, 2) if price is not None else None
    per_100 = round(price / (ml * pack) * 100, 2) if (price is not None and ml) else None
    return {
        "date": nz_today(), "chain": chain, "store_id": store["store_id"],
        "store_name": store["store_name"], "region": store.get("region", ""),
        "product_id": str(product_id), "barcode": barcode or "", "name": name,
        "flavour": flavour(name), "image": image or "",
        "size_ml": ml, "pack_count": pack, "price": price, "was_price": was_price,
        "promo_text": promo_text or "", "promo_ends": promo_ends or "",
        "on_special": on_special, "price_per_can": per_can, "price_per_100ml": per_100,
        "available": available,
    }


# Known Monster flavours (longest match wins). Anything not listed still works:
# the flavour is derived from the product name, so new flavours show up on their own.
FLAVOURS = [
    "Ultra White", "Ultra Paradise", "Ultra Violet", "Ultra Gold", "Ultra Red", "Ultra Blue",
    "Ultra Fiesta", "Ultra Peachy Keen", "Ultra Rosa", "Ultra Strawberry Dreams", "Ultra Watermelon",
    "Ultra Sunrise", "Ultra Black", "Ultra Zero", "Zero Sugar", "Mango Loco", "Pipeline Punch",
    "Pacific Punch", "Aussie Lemonade", "Juiced Khaotic", "Juiced Monarch", "Juiced Bad Apple",
    "Juiced Ripper", "Juiced Mule", "Rehab Peach Tea", "Rehab Lemonade", "Rehab Tea", "Java Mean Bean",
    "Java Salted Caramel", "Reserve White Pineapple", "Reserve Watermelon", "Lewis Hamilton",
    "Doctor", "Khaos", "Assault", "Absolutely Zero", "Original",
]
_EXCLUDE = ("munch", "mash", "truck", "toy")


def is_monster(name):
    n = (name or "").lower()
    return "monster" in n and not any(w in n for w in _EXCLUDE)


def flavour(name):
    n = (name or "").lower()
    for f in sorted(FLAVOURS, key=len, reverse=True):
        if f.lower() in n:
            return f
    t = re.sub(r"\b(monster|energy|drink|can|cans)\b", " ", n)
    t = re.sub(r"\d+(\.\d+)?\s*(x|ml|l|pk|pack)\b", " ", t)
    t = re.sub(r"[^a-z' ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.title() if t else "Original"


def _key(r):
    return (r["chain"], r["store_id"], r["product_id"])


def load_snapshot():
    if SNAPSHOT.exists():
        return json.loads(SNAPSHOT.read_text())
    return {"chains": {}, "items": []}


def write_snapshot(new_rows, ok_chains, failed_chains):
    """Rebuild today's snapshot. Successful chains come only from today's fetch
    (so expired specials vanish). Failed chains keep their last good data, flagged stale."""
    prev = load_snapshot()
    today = nz_today()
    items, chains = [], {}

    for chain in ok_chains:
        today_rows = [r for r in new_rows if r["chain"] == chain]
        today_keys = {_key(r) for r in today_rows}
        items += today_rows
        # Previously available but missing today -> show once as unavailable.
        for old in prev["items"]:
            if old["chain"] == chain and old.get("available") and _key(old) not in today_keys:
                gone = dict(old, date=today, available=False, price=None, was_price=None,
                            on_special=False, promo_text="", promo_ends="",
                            price_per_can=None, price_per_100ml=None)
                items.append(gone)
                new_rows.append(gone)
        chains[chain] = {"status": "ok", "last_success": today}

    for chain in failed_chains:
        items += [r for r in prev["items"] if r["chain"] == chain]
        last = prev.get("chains", {}).get(chain, {}).get("last_success")
        chains[chain] = {"status": "stale", "last_success": last}

    out = {"updated": nz_now().isoformat(timespec="seconds"), "date": today,
           "chains": chains, "items": items}
    DATA_DIR.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(out, indent=1))


def upsert_history(new_rows, ok_chains):
    """Replace today's rows for successful chains; keep everything older."""
    today = nz_today()
    existing = []
    if HISTORY.exists():
        with HISTORY.open(newline="") as f:
            existing = list(csv.DictReader(f))
    kept = [r for r in existing if not (r["date"] == today and r["chain"] in ok_chains)]
    with HISTORY.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(kept)
        w.writerows([{k: r.get(k, "") for k in FIELDS} for r in new_rows])


def probe(label, response):
    """Set PROBE=1 to print the raw response so adapters can be checked against the live site."""
    import os
    if os.environ.get("PROBE"):
        print(f"--- PROBE {label}: HTTP {response.status_code} {response.url}")
        print(response.text[:3000])
        print("--- end probe")
