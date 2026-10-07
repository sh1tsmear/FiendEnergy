"""List New World / PAK'nSAVE stores so you can copy their IDs into config.json.

  python scraper/find_stores.py newworld tauranga
  python scraper/find_stores.py paknsave "mount maunganui"

UNVERIFIED: the store-list endpoint is from memory. If nothing prints, the raw
response is shown so the endpoint can be corrected, or take the store ID from the
search request in DevTools (README).
"""
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foodstuffs import ORIGINS, UA, get_token

cfg = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
key = sys.argv[1] if len(sys.argv) > 1 else "newworld"
query = " ".join(sys.argv[2:]).lower()
c = cfg[key]
origin = ORIGINS["New World" if key == "newworld" else "PAK'nSAVE"]
token = get_token(c["token_url"], origin)
r = requests.get(c["stores_url"], headers={**UA, "Authorization": f"Bearer {token}", "Origin": origin}, timeout=30)
r.raise_for_status()
data = r.json()
stores = data if isinstance(data, list) else data.get("stores", [])
hits = [s for s in stores if query in json.dumps(s).lower()]
for s in hits:
    print(s.get("id"), "|", s.get("name"), "|", s.get("address") or s.get("region") or "")
if not hits:
    print("No stores matched. Raw response (first 1500 chars):")
    print(json.dumps(data)[:1500])
