# eBay via the Browse API

eBay search pages block this host (`server: AkamaiGHost`, `403` on every path from the household CGNAT egress — the browser gets it too). Do **not** browse eBay, do not retry, do not "diagnose" the error page. Use the script.

## Command

```bash
python3 /opt/data/tools/ebay_search.py --q "harman kardon invoke" --limit 10
```

Host path is the same file: `~/.hermes/tools/ebay_search.py`.

| Flag | Meaning |
|---|---|
| `--q` | keywords (required) |
| `--limit` | results, default 20, max 200 |
| `--min-price` / `--max-price` | in the marketplace currency (AUD for `EBAY_AU`), integer |
| `--condition new\|used` | maps to eBay `conditions:{NEW}` / `{USED}` |
| `--buying fixed\|auction` | `buyingOptions:{FIXED_PRICE}` / `{AUCTION}` |
| `--location-country AU` | seller country filter; leave off for "ships anywhere" |
| `--sort newly\|price\|price-desc\|ending` | default `newly` |
| `--category <ids>` | comma-separated eBay category ids |
| `--marketplace EBAY_CA` | override the default marketplace (`EBAY_AU`, `EBAY_CA`, `EBAY_HK`, `EBAY_US`, `EBAY_GB`, `EBAY_DE`) |
| `--json` | JSON array instead of lines |
| `--no-cache` | skip the 15-minute result cache |
| `--verbose` | request/cache/total info on stderr |

Output fields per listing: title, price+currency, shipping (`free` when zero), condition, location, ends, buying options, url, item id.

## What it can and cannot tell you

- **Live listings only.** Sold/completed prices are the Marketplace Insights API, which needs separate approval — if the user asks "what do these actually sell for", say the API can't answer it and fall back to `web_search` on `site:ebay.com.au` sold filters.
- Prices are the marketplace currency; don't convert silently.
- `total` in the header is eBay's match count, not what you fetched.

## Quota and cost

Free production keyset: **5,000 calls/day** (Browse). The script:

- caches each distinct query+flag combination for 15 minutes — repeated asks cost nothing;
- appends one line per real call to `~/.hermes/logs/ebay-usage.log`;
- refuses to call once 4,500 calls are logged for the current UTC day (exit 5).

So never loop the script to page through results — raise `--limit` instead (one call, up to 200 items).

## Credentials

`~/.hermes/secrets/ebay.json`, mode 600, `{"client_id","client_secret","marketplace_id"}`. Never in this skill, never in git, never pasted into chat. Setup and the developer-account walkthrough live in `~/.opencode/plan/ecommerce-search-enablement-2026-11-24.md`.

## Exit codes

| Code | Meaning | What to say |
|---|---|---|
| 0 | ok | — |
| 2 | credentials missing/malformed | tell the user the file is missing; don't retry |
| 3 | token rejected | keyset likely still Non-Compliant (Marketplace Account Deletion exemption) |
| 4 | API error | quote the HTTP status + message once |
| 5 | daily cap reached | stop searching eBay today |

A 403 from `item_summary/search` usually means the marketplace is not enabled for the keyset; a repeated 401 after a token refresh means the credentials are wrong, not expired.
