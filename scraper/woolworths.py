"""Woolworths NZ adapter.

UNVERIFIED: the endpoint and field names below come from how the site has
looked in the past. Run PROBE=1 python scraper/scrape.py to see the real
response, then edit config.json / parse() if it differs.
"""
import time
import requests
from common import build_row, is_monster, probe

UA = {"User-Agent": "Mozilla/5.0 (compatible; nz-energy-prices hobby project)"}


def parse(data, store):
    rows = []
    items = (data.get("products") or {}).get("items") or []
    for p in items:
        if p.get("type") not in (None, "Product"):
            continue
        # Woolworths already puts brand and flavour inside "name"; only add the brand if missing.
        name = p.get("name") or ""
        brand = p.get("brand") or ""
        if brand and brand.lower() not in name.lower():
            name = f"{brand} {name}"
        if not is_monster(name):
            continue
        price_info = p.get("price") or {}
        size = p.get("size") or {}
        size_text = " ".join(filter(None, [size.get("volumeSize"), size.get("packageType")]))
        sale = price_info.get("salePrice")
        original = price_info.get("originalPrice")
        special = bool(price_info.get("isSpecial"))
        images = p.get("images") or {}
        rows.append(build_row(
            "Woolworths", store, p.get("sku"), name, sale if sale is not None else original,
            barcode=p.get("barcode", ""),
            was_price=original if special else None,
            size_text=size_text,
            available=p.get("availabilityStatus", "In Stock") not in ("OutOfStock", "Out Of Stock", "Unavailable"),
            variety=p.get("variety") or "",
            image=images.get("big") or images.get("small") or "",
        ))
    return rows


def fetch(cfg, terms, delay=3):
    found = {}
    for store in cfg["stores"]:
        for term in terms:
            params = dict(cfg["params"], search=term)
            r = requests.get(cfg["search_url"], params=params,
                             headers={**UA, **cfg.get("headers", {})}, timeout=30)
            probe("Woolworths", r)
            r.raise_for_status()
            for row in parse(r.json(), store):
                found[(row["store_id"], row["product_id"])] = row  # de-dupe across terms
            time.sleep(delay)
    return list(found.values())
