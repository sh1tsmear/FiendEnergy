"""New World + PAK'nSAVE adapter (both run on the Foodstuffs system).

UNVERIFIED: endpoints, request body and response fields are from memory of how
the sites worked. Confirm in DevTools (README, step 2) and edit parse()/body.
Prices are usually returned in CENTS.
"""
import requests
from common import build_row, is_monster

UA = {"User-Agent": "Mozilla/5.0 (compatible; nz-energy-prices hobby project)"}


def get_token(token_url, site_origin):
    r = requests.post(token_url, headers={**UA, "Origin": site_origin}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


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
            size_text=p.get("displayName", ""),
        ))
    return rows


def fetch(chain, cfg, search_term):
    origin = "https://www.newworld.co.nz" if chain == "New World" else "https://www.paknsave.co.nz"
    token = get_token(cfg["token_url"], origin)
    rows = []
    for store in cfg["stores"]:
        sid = store["store_id"]
        body = {
            "algoliaQuery": {"query": search_term, "hitsPerPage": 50, "page": 0,
                             "filters": f"stores:{sid}"},
            "storeId": sid, "hitsPerPage": 50, "page": 0,
            "sortOrder": "NI_POPULARITY_ASC", "tobaccoQuery": False,
        }
        r = requests.post(cfg["search_url"], json=body, timeout=30,
                          headers={**UA, "Authorization": f"Bearer {token}", "Origin": origin})
        r.raise_for_status()
        rows += parse(r.json(), chain, store)
    return rows
