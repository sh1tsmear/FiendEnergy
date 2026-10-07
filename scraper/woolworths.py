"""Woolworths NZ adapter.

UNVERIFIED: the endpoint and field names below come from how the site has
looked in the past. Confirm them in DevTools (README, step 2) and edit
config.json / parse() if they differ.
"""
import requests
from common import build_row, is_monster

UA = {"User-Agent": "Mozilla/5.0 (compatible; nz-energy-prices hobby project)"}


def parse(data, store):
    rows = []
    items = (data.get("products") or {}).get("items") or []
    for p in items:
        if p.get("type") not in (None, "Product"):
            continue
        name = " ".join(filter(None, [p.get("brand"), p.get("name"), p.get("variety")]))
        if not is_monster(name):
            continue
        price_info = p.get("price") or {}
        size = p.get("size") or {}
        size_text = " ".join(filter(None, [size.get("volumeSize"), size.get("packageType")]))
        sale = price_info.get("salePrice")
        original = price_info.get("originalPrice")
        special = bool(price_info.get("isSpecial"))
        rows.append(build_row(
            "Woolworths", store, p.get("sku"), name, sale if sale is not None else original,
            barcode=p.get("barcode", ""),
            was_price=original if special else None,
            size_text=size_text,
            available=p.get("availabilityStatus", "In Stock") != "OutOfStock",
        ))
    return rows


def fetch(cfg, search_term):
    rows = []
    for store in cfg["stores"]:
        params = dict(cfg["params"], search=search_term)
        r = requests.get(cfg["search_url"], params=params,
                         headers={**UA, **cfg.get("headers", {})}, timeout=30)
        r.raise_for_status()
        rows += parse(r.json(), store)
    return rows
