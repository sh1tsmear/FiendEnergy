"""Fetch Monster prices from Woolworths, New World and PAK'nSAVE.

  python scraper/scrape.py          real run
  python scraper/scrape.py --demo   fake data, to test the pipeline and website

A chain that errors keeps its previous data and is marked stale; it never
wipes prices or writes history rows.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import foodstuffs
import woolworths

CONFIG = json.loads((Path(__file__).resolve().parent / "config.json").read_text())


def usable_stores(cfg):
    stores = [s for s in cfg["stores"] if not str(s["store_id"]).startswith("REPLACE")]
    skipped = len(cfg["stores"]) - len(stores)
    if skipped:
        print(f"  skipping {skipped} store(s) with placeholder IDs")
    return dict(cfg, stores=stores)


def demo_rows():
    ws = {"store_id": "national", "store_name": "Woolworths NZ (online)", "region": "National"}
    nw = {"store_id": "demo-nw", "store_name": "New World Demo", "region": "Bay of Plenty"}
    ps = {"store_id": "demo-ps", "store_name": "PAK'nSAVE Demo", "region": "Bay of Plenty"}
    b = common.build_row
    return {
        "Woolworths": [
            b("Woolworths", ws, "w1", "Monster Energy Drink Ultra White", 3.50, size_text="500ml can"),
            b("Woolworths", ws, "w2", "Monster Energy Drink Original", 3.60, was_price=4.20, size_text="500ml can"),
            b("Woolworths", ws, "w3", "Monster Energy Drink Mango Loco", 3.80, size_text="500ml can"),
            b("Woolworths", ws, "w4", "Monster Energy Drink Original 4 x 500ml", 13.00),
        ],
        "New World": [
            b("New World", nw, "n1", "Monster Energy Drink Ultra White 500ml", 3.79),
            b("New World", nw, "n2", "Monster Energy Drink Original 500ml", 3.89),
            b("New World", nw, "n3", "Monster Ultra Paradise 500ml", 3.79),
        ],
        "PAK'nSAVE": [
            b("PAK'nSAVE", ps, "p1", "Monster Energy Drink Ultra White 500ml", 3.29),
            b("PAK'nSAVE", ps, "p2", "Monster Energy Drink Original 500ml", 3.29, was_price=3.89),
            b("PAK'nSAVE", ps, "p3", "Monster Energy Drink Mango Loco 500ml", 3.49, promo_text="2 for $6"),
        ],
    }


def real_rows():
    terms, delay = CONFIG["search_terms"], CONFIG["request_delay_seconds"]
    jobs = {
        "Woolworths": lambda: woolworths.fetch(usable_stores(CONFIG["woolworths"]), terms, delay),
        "New World": lambda: foodstuffs.fetch("New World", usable_stores(CONFIG["newworld"]), terms, delay),
        "PAK'nSAVE": lambda: foodstuffs.fetch("PAK'nSAVE", usable_stores(CONFIG["paknsave"]), terms, delay),
    }
    enabled = {"Woolworths": "woolworths", "New World": "newworld", "PAK'nSAVE": "paknsave"}
    out = {}
    for chain, job in jobs.items():
        if not CONFIG[enabled[chain]].get("enabled", True):
            continue
        print(f"{chain}...")
        try:
            out[chain] = job()
            print(f"  {len(out[chain])} Monster product(s) parsed")
            if not out[chain]:
                print("  0 parsed: the response format probably differs from the adapter. "
                      "Run with PROBE=1 to see the raw response.")
        except Exception as e:
            print(f"  FAILED: {e}")
            out[chain] = None
    return out


def main():
    results = demo_rows() if "--demo" in sys.argv else real_rows()
    ok, failed, rows = [], [], []
    for chain, r in results.items():
        # None = error. An empty list from a "successful" call is also treated
        # as a failure, so an outage or blocked request can't look like "everything sold out".
        if r:
            ok.append(chain)
            rows += r
        else:
            failed.append(chain)
    # Single cans only (multipacks are dropped after the success check above,
    # so a chain that only returned multipacks isn't mistaken for an outage).
    rows = [r for r in rows if r["pack_count"] == 1]
    common.write_snapshot(rows, ok, failed)
    common.upsert_history(rows, ok)
    print(f"Done. ok={ok} stale={failed}")
    if not ok:
        sys.exit(1)  # makes the GitHub Action show red when everything failed


if __name__ == "__main__":
    main()
