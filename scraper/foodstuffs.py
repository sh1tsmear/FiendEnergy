"""New World + PAK'nSAVE adapter (both run on the Foodstuffs system).

UNVERIFIED: endpoints, request body and response fields are from memory of how
the sites worked. Run PROBE=1 python scraper/scrape.py to see the real
response, then edit parse()/body. Prices are usually returned in CENTS.
"""
import time
import requests
from common import build_row, is_monster, probe

UA = {"User-Agent": "Mozilla/5.0 (compatible; nz-energy-prices hobby project)"}
ORIGINS = {"New World": "https://www.newworld.co.nz", "PAK'nSAVE": "https://www.paknsave.co.nz"}


def get_token(token_url, site_origin):
    r = requests.post(token_url, headers={**UA, "Origin": site_origin}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def image_url(p):
    if p.get("image"):
        return p["image"]
    pid = str(p.get("productId") or "").split("-")[0]
    # UNVERIFIED pattern for Foodstuffs product photos.
    return f"https://a.fsimg.co.nz/product/retail/fan/image/400x400/{pid}.png" if pid else ""


def parse(data, chain, store):
    rows = []
    for p in data.get("products", []):
        name = " ".join(filter(None, [p.get("brand"), p.get("name")]))
        if not is_monster(name):
            continue
        single = (p.get("singlePrice") or {}).get("price")
        if single is None:
            continue
        price = single / 100
        promo = (p.get("promotions") or [{}])[0] if p.get("promotions") else {}
        reward = promo.get("rewardValue")
        was = None
        promo_text = ""
        if reward:
            # Fixed-price promo: rewardValue is the sale price in cents.
            was, price = price, reward / 100
            if was <= price:
                was, promo_text = None, "Promo"
        rows.append(build_row(
            chain, store, p.get("productId"), name, price,
            barcode=p.get("barcode", ""), was_price=was, promo_text=promo_text,
            size_text=p.get("displayName", ""), image=image_url(p),
        ))
    return rows


def fetch(chain, cfg, terms, delay=3):
    origin = ORIGINS[chain]
    token = get_token(cfg["token_url"], origin)
    found = {}
    for store in cfg["stores"]:
        sid = store["store_id"]
        for term in terms:
            body = {
                "algoliaQuery": {"query": term, "hitsPerPage": 50, "page": 0,
                                 "filters": f"stores:{sid}"},
                "storeId": sid, "hitsPerPage": 50, "page": 0,
                "sortOrder": "NI_POPULARITY_ASC", "tobaccoQuery": False,
            }
            r = requests.post(cfg["search_url"], json=body, timeout=30,
                              headers={**UA, "Authorization": f"Bearer {token}", "Origin": origin})
            probe(chain, r)
            r.raise_for_status()
            for row in parse(r.json(), chain, store):
                found[(row["store_id"], row["product_id"])] = row
            time.sleep(delay)
    return list(found.values())
