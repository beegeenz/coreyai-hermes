#!/usr/bin/env python3
"""eBay Browse API search for Hermes.

Stdlib only: the Hermes container's /usr/bin/python has no requests/httpx.

  python3 ~/.hermes/tools/ebay_search.py --q "harman kardon invoke" --limit 5
  python3 ~/.hermes/tools/ebay_search.py --q "sennheiser hd600" --max-price 300 --condition used --json

Credentials (mode 600, never in git):

  ~/.hermes/secrets/ebay.json
  {"client_id": "...", "client_secret": "...", "marketplace_id": "EBAY_AU"}

Paths are resolved from the script location, so the same file works host-side
(~/.hermes/tools/) and in the container (/opt/data/tools/ -> /opt/data/...).
Override with EBAY_HERMES_HOME if the layout ever differs.

Exit codes: 0 ok, 2 config missing, 3 auth rejected, 4 API error, 5 quota guard.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

MARKET_CURRENCY = {
    "EBAY_AU": "AUD",
    "EBAY_CA": "CAD",
    "EBAY_HK": "HKD",
    "EBAY_US": "USD",
    "EBAY_GB": "GBP",
    "EBAY_DE": "EUR",
}

CACHE_TTL = 15 * 60          # repeat queries inside 15 min cost no API calls
DAILY_CALL_CAP = 4500        # eBay Browse default is 5000/day
TOKEN_SKEW = 5 * 60          # refresh this long before expiry


def base_dir() -> Path:
    override = os.environ.get("EBAY_HERMES_HOME")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent


BASE = base_dir()
SECRETS = BASE / "secrets" / "ebay.json"
TOKEN_CACHE = BASE / "cache" / "ebay-token.json"
RESULT_CACHE = BASE / "cache" / "ebay-results"
USAGE_LOG = BASE / "logs" / "ebay-usage.log"


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(code)


def load_config() -> dict:
    if not SECRETS.exists():
        fail(
            2,
            f"Missing eBay credentials at {SECRETS}\n"
            'Expected: {"client_id": "...", "client_secret": "...", "marketplace_id": "EBAY_AU"}\n'
            "Create it with umask 077 and chmod 600 (see references/ebay-browse.md).",
        )
    try:
        cfg = json.loads(SECRETS.read_text())
    except json.JSONDecodeError as exc:
        fail(2, f"{SECRETS} is not valid JSON: {exc}")
    missing = [k for k in ("client_id", "client_secret") if not cfg.get(k)]
    if missing:
        fail(2, f"{SECRETS} is missing: {', '.join(missing)}")
    cfg.setdefault("marketplace_id", "EBAY_AU")
    return cfg


def http_json(url: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:600]
        return {"__http_error__": exc.code, "__body__": body}
    except urllib.error.URLError as exc:
        fail(4, f"Network error talking to eBay: {exc.reason}")


def today_calls() -> int:
    """Count API calls already made today (UTC) from the usage log."""
    if not USAGE_LOG.exists():
        return 0
    today = time.strftime("%Y-%m-%d", time.gmtime())
    with USAGE_LOG.open() as fh:
        return sum(1 for line in fh if line.startswith(today))


def log_call(query: str, calls: int) -> None:
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\t{query}\t{calls}\n")


def get_token(cfg: dict, refresh: bool = False) -> str:
    if not refresh and TOKEN_CACHE.exists():
        try:
            cached = json.loads(TOKEN_CACHE.read_text())
            if cached.get("expires_at", 0) - TOKEN_SKEW > time.time() and cached.get("access_token"):
                return cached["access_token"]
        except (json.JSONDecodeError, OSError):
            pass

    basic = base64.b64encode(
        f"{cfg['client_id']}:{cfg['client_secret']}".encode()
    ).decode()
    payload = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "scope": SCOPE}
    ).encode()
    result = http_json(
        TOKEN_URL,
        data=payload,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if "__http_error__" in result:
        hint = " — is the production keyset still 'Non-Compliant' (Marketplace Account Deletion)?" if result["__http_error__"] in (400, 401) else ""
        fail(3, f"eBay rejected the token request (HTTP {result['__http_error__']}){hint}\n{result['__body__']}")

    token = result.get("access_token")
    if not token:
        fail(3, f"eBay returned no access_token: {json.dumps(result)[:400]}")

    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "access_token": token,
        "expires_at": time.time() + int(result.get("expires_in", 7200)),
    }))
    os.chmod(tmp, 0o600)
    tmp.replace(TOKEN_CACHE)
    return token


def build_params(args, marketplace: str) -> dict:
    currency = MARKET_CURRENCY.get(marketplace, "AUD")
    filters = []
    if args.min_price is not None or args.max_price is not None:
        lo = "" if args.min_price is None else str(int(args.min_price))
        hi = "" if args.max_price is None else str(int(args.max_price))
        filters.append(f"price:[{lo}..{hi}]")
        filters.append(f"priceCurrency:{currency}")
    if args.condition:
        filters.append("conditions:{" + args.condition.upper() + "}")
    if args.buying:
        filters.append("buyingOptions:{" + ("FIXED_PRICE" if args.buying == "fixed" else "AUCTION") + "}")
    if args.location_country:
        filters.append(f"itemLocationCountry:{args.location_country.upper()}")

    params = {"q": args.q, "limit": str(min(args.limit, 200))}
    if filters:
        params["filter"] = ",".join(filters)
    if args.sort:
        params["sort"] = {
            "newly": "newlyListed",
            "price": "price",
            "price-desc": "-price",
            "ending": "endTimeSoonest",
        }[args.sort]
    if args.category:
        params["category_ids"] = args.category
    return params


def cache_key(params: dict, marketplace: str) -> Path:
    blob = json.dumps({"p": params, "m": marketplace, "q": params.get("q")}, sort_keys=True)
    return RESULT_CACHE / (hashlib.sha1(blob.encode()).hexdigest() + ".json")


def simplify(item: dict) -> dict:
    price = item.get("price") or {}
    ship = None
    for opt in item.get("shippingOptions") or []:
        cost = opt.get("shippingCost") or {}
        if cost.get("value") not in (None, "0.00", 0):
            ship = f"{cost.get('currency', price.get('currency', ''))} {cost['value']}"
        else:
            ship = ship or "free"
        break
    loc = item.get("itemLocation") or {}
    parts = [loc.get("city"), loc.get("stateOrProvince"), loc.get("postalCode"), loc.get("country")]
    return {
        "title": item.get("title"),
        "price": f"{price.get('currency', '')} {price.get('value', '')}".strip(),
        "shipping": ship,
        "condition": item.get("condition"),
        "location": ", ".join(p for p in parts if p),
        "ends": item.get("itemEndDate"),
        "buying": ",".join(item.get("buyingOptions") or []),
        "url": item.get("itemWebUrl"),
        "id": item.get("itemId"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Search live eBay listings via the Browse API.")
    ap.add_argument("--q", required=True, help="search keywords")
    ap.add_argument("--limit", type=int, default=20, help="results to return (max 200)")
    ap.add_argument("--min-price", type=float, help="minimum price in the marketplace currency")
    ap.add_argument("--max-price", type=float, help="maximum price")
    ap.add_argument("--condition", choices=["new", "used"], help="listing condition")
    ap.add_argument("--buying", choices=["fixed", "auction"], help="Buy It Now vs auction")
    ap.add_argument("--location-country", help="seller country, e.g. AU (default: any)")
    ap.add_argument("--sort", choices=["newly", "price", "price-desc", "ending"], default="newly",
                    help="newly listed (default), price asc/desc, ending soonest")
    ap.add_argument("--category", help="eBay category ids, comma separated (see Taxonomy API)")
    ap.add_argument("--marketplace", help="override marketplace_id, e.g. EBAY_CA / EBAY_HK")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of lines")
    ap.add_argument("--no-cache", action="store_true", help="bypass the 15-minute result cache")
    ap.add_argument("--verbose", action="store_true", help="progress on stderr")
    args = ap.parse_args()

    cfg = load_config()
    marketplace = (args.marketplace or cfg["marketplace_id"]).upper()
    params = build_params(args, marketplace)
    key = cache_key(params, marketplace)

    if not args.no_cache and key.exists() and time.time() - key.stat().st_mtime < CACHE_TTL:
        if args.verbose:
            print(f"cache hit: {key.name}", file=sys.stderr)
        result = json.loads(key.read_text())
    else:
        calls = today_calls()
        if calls >= DAILY_CALL_CAP:
            fail(5, f"Refusing to call eBay: {calls} calls logged today (cap {DAILY_CALL_CAP}).")
        token = get_token(cfg)
        if args.verbose:
            print(f"GET {SEARCH_URL} {params}", file=sys.stderr)
        result = http_json(
            SEARCH_URL + "?" + urllib.parse.urlencode(params),
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": marketplace,
                "Accept": "application/json",
            },
        )
        if "__http_error__" in result:
            if result["__http_error__"] == 401:  # token may have been revoked: one retry
                token = get_token(cfg, refresh=True)
                result = http_json(
                    SEARCH_URL + "?" + urllib.parse.urlencode(params),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": marketplace,
                        "Accept": "application/json",
                    },
                )
            if "__http_error__" in result:
                fail(4, f"eBay search failed (HTTP {result['__http_error__']}) for {marketplace}\n{result['__body__']}")
        log_call(args.q, calls + 1)
        RESULT_CACHE.mkdir(parents=True, exist_ok=True)
        key.write_text(json.dumps(result))

    items = [simplify(i) for i in (result.get("itemSummaries") or [])]
    if args.verbose:
        print(f"{result.get('total', len(items))} total matches, {len(items)} returned", file=sys.stderr)

    if args.json:
        print(json.dumps(items, indent=2))
        return
    if not items:
        print(f"No live listings for '{args.q}' on {marketplace}.")
        return
    print(f"{len(items)} listing(s) for '{args.q}' on {marketplace}"
          f" (of {result.get('total', '?')} total)")
    for it in items:
        bits = [it["title"]]
        if it["price"]:
            bits.append(it["price"])
        if it["condition"]:
            bits.append(it["condition"])
        if it["shipping"]:
            bits.append("ship " + it["shipping"])
        if it["location"]:
            bits.append(it["location"])
        print(" - " + " | ".join(str(b) for b in bits if b))
        print(f"   {it['url']}")


if __name__ == "__main__":
    main()
