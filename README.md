# NZ Monster price tracker

A static site (GitHub Pages) that shows Monster energy drink prices at Woolworths,
New World and PAK'nSAVE. A GitHub Action runs every morning, fetches today's
prices, rewrites `data/prices.json` (what the site shows) and adds dated rows to
`data/history.csv`.

## Set up

1. Create a GitHub repo and push this folder to it.
2. Settings → Pages → deploy from the `main` branch, root folder.
3. Settings → Actions → General → Workflow permissions → **Read and write**.
4. Test locally: `pip install -r requirements.txt`, then `python scraper/scrape.py --demo`
   and open `index.html` with a local server (`python -m http.server`).
   The demo fills the site with fake data. The first real run replaces it.

## Connecting the real sites (needed once)

The adapters in `scraper/woolworths.py` and `scraper/foodstuffs.py` are written from
memory of how the sites worked, and I couldn't test them against the live sites.
Check each one:

1. Open the chain's site, search "monster energy", press F12 → Network → Fetch/XHR.
2. Find the request that returns the product list as JSON and compare it with
   the URL in `scraper/config.json` and the field names in `parse()`.
3. Fix whatever differs, run `python scraper/scrape.py`, and check `data/prices.json`
   against what the website shows.

**New World / PAK'nSAVE store IDs:** while on the site with your store selected,
the search request contains your store ID. Put it in `scraper/config.json`
in place of `REPLACE_ME` (add more stores by copying the object).

If a chain can't be fetched, it is shown as "couldn't update" on the site, keeps its
last good prices, and never writes history rows. The Action turns red only if every
chain fails. Check each site's terms of use, and keep the request rate low.

## How the daily update works

- Today's fetch is the truth: a special that has ended just comes back at the normal price.
- Products that disappear from a chain show as unavailable once, then drop off.
- Running twice in one day replaces that day's rows instead of duplicating them.
- Dates use New Zealand time.
