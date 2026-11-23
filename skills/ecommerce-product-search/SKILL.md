---
name: ecommerce-product-search
description: "Use when shopping or searching listings on AliExpress, eBay, Facebook Marketplace, Carousell, Gumtree, or Kijiji."
version: 0.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Shopping, Products, Browser, Marketplace]
    related_skills: [product-price-monitor, blocked-page-recovery]
---

# E-commerce Product Search

One-off "find me X on AliExpress/Amazon" research: produce a shortlist (title, price, link) plus an honest spec-fit verdict. Pick the route by site first — the browser is the wrong tool for eBay and the right one for Facebook.

## Route by site

| Marketplace | Route | Why |
|---|---|---|
| **eBay** (any locale) | `python3 /opt/data/tools/ebay_search.py --q "<model>"` — API. **Never the browser.** | eBay 403s this egress (`AkamaiGHost`) at every path; the Browse API is free, structured and unblocked. Details: `references/ebay-browse.md`. |
| **Facebook Marketplace** | browser, logged-out `marketplace/<city>/search/?query=` | Works with no session; the city slug sets the region. Details: `references/facebook-marketplace.md`. |
| **AliExpress** | browser, wholesale URL pattern | Renders headless. Details: `references/aliexpress.md`. |
| **Carousell HK** | browser first (works with the host Chrome's pinned UA); `site:` search if it stalls >2 min | Cloudflare passes on its own in ~10 s. |
| **Kijiji** | browser (`document.body.innerText` in one call) | Renders headless. |
| **Gumtree AU** | `web_search site:gumtree.com.au "<model>"` only | PeakHOUR WAF 403s every HTML path from a CGNAT egress. Say results are snippet-sourced. |
| Pinduoduo / JD / Taobao | out of scope (login-walled) | Ask before trying. |


## When to Use

- "Search AliExpress/Amazon for <part>" — one-off product hunt where listings must be spec-vetted against a stated requirement.
- "Find me a module with <spec X>" on a shopping marketplace.

Don't use for: recurring price watching (`product-price-monitor`), or a plain price lookup on a known URL (`web_extract` directly).

## Procedure

1. **Search via the wholesale URL pattern** — navigate to `https://www.aliexpress.com/w/wholesale-<dashed-query>.html` (also try keyword variants that encode the user's *requirement*, e.g. "<part> 0-5V", not just the part name).
2. **Extract listings in one JS call** — collect `a[href*="/item/"]`, dedupe on the query-stripped href, drop titles under ~15 chars (they are image/price fragments), and print title+price+href. Don't open product pages during the search phase.
3. **Verify the load-bearing spec off-site, not on the listing** — marketplace spec tables are near-worthless (see Pitfalls). For a component, check the reference design, datasheet, and user forum threads (Arduino forum etc.) for the actual measured behavior of the board type. Do this before promising the listing matches the user's requirement; the match usually hinges on one spec the sellers all omit or misstate.
4. **Deliver**: shortlist of 3-5 links with prices, then a short 'the catch' section if the requirement isn't literally met by what exists, plus a concrete recommendation (e.g. add software RMS/rectification, pick the alternate variant).

## Second-hand marketplaces (Carousell, Facebook, eBay)

Used-goods hunts ("check Carousell/FB/eBay for <model>, any condition") run differently from the wholesale flow above — per-site mechanics:

- **Disambiguate the model name before reporting**: one model name often spans two product classes (headphones vs smart speaker generations). Filter listings by product category, not just the model string, and state which product the prices belong to.
- **Facebook Marketplace works logged-out, and the city slug is honoured** — `https://www.facebook.com/marketplace/<city>/search/?query=<q>` returns real local results with no session (verified 2026-11-24: sydney → "Sydney, Australia · Within 65 km", toronto → "Toronto, Ontario", vancouver → "Vancouver, British Columbia", 24 cards each, local currency). Do **not** log in to switch cities, and do not trust a zero-result page until you have read the location line — an unknown slug falls back to a default city silently. Extract `a[href*="/marketplace/item/"]`, dedupe on the bare href, take title+price from each card's innerText; the grid is virtualized, so one `scrollBy` pass then re-extract before concluding. The search engine is fuzzy — it mixes in unrelated categories (concert tickets, phones); filter by the model keyword before reporting. Item pages render logged-out too. Full procedure: `references/facebook-marketplace.md`.
- **Carousell HK passes Cloudflare on its own** when the browser carries a real Chrome User-Agent (the host unit pins one): the interstitial clears in ~10 s and `cf_clearance` then persists in the profile. Give it ~15 s with one reload before assuming a wall; if it still won't clear, pivot to `web_search` with `site:carousell.com.hk "<model>"` — the indexed `/q` and `/p/` pages carry title+price+condition in snippets.
- **eBay: use the Browse API, never the browser** — the browser and `web_extract` both get an Akamai 403 on `/sch/` URLs from this host, and it is not fixable browser-side (IP reputation on a CGNAT egress). Run `python3 /opt/data/tools/ebay_search.py --q "<model>" [--max-price N] [--condition used] [--marketplace EBAY_AU]`; see `references/ebay-browse.md` for flags, quota and exit codes. Only use `web_search site:ebay.com.au` when you specifically need *sold* prices, which the Browse API does not expose.
- **Classify a marketplace's browser-friendliness before burning browser calls**: Kijiji and Facebook render headless (Kijiji ad titles/prices extract from `document.body.innerText` in one call; the `.vine-asset` card selector works on category-listing pages but not on `/q` search pages). **Gumtree answers every HTML path with `403` + `peakhour-challenge: 1`** — a WAF on a shared CGNAT address, not a UA problem, and `robots.txt` is the only path that answers 200. One attempt at most, then `web_search`/`site:`; never retry the browser loop.
- **Prove absence cheaply on Kijiji**: search the model keyword under All Categories for the whole province — one page of snippet text shows whether the product exists at all; expect same-word homonyms (books, backpacks, shoes) in the hits and filter them out rather than concluding the product is absent.
- **A pinned browser-level UA does move Cloudflare — a per-tab override does not.** Measured on this host 2026-11-24: `--user-agent="…Chrome/158…"` at Chrome launch cleared Carousell's interstitial in ~10 s, while a CDP `Network.setUserAgentOverride` on the same page stayed walled. The difference is that the launch flag also keeps `sec-ch-ua` consistent with the UA, and the override drops those client hints entirely. That reads the other way for Akamai/PeakHOUR walls (eBay, Gumtree), where no header change helps at all — so: fix the browser's identity once, at launch, and treat remaining walls as egress reputation rather than something to re-litigate with headers.
- **State freshness on index-sourced listings**: search-cache data can be months old (possibly sold). Flag it per-listing rather than presenting index hits as live, and separate truly relevant hits from index noise (adjacent models/gens) the way you'd separate fuzzy FB matches.

## Pitfalls

- **Do not fight the product page for specs.** Description content is lazy-loaded and mostly images; seller attribute tables are frequently blank or wrong; the 'AI overview' is boilerplate. Give a page ONE innerText/JS extraction attempt — if the spec isn't there, go off-site. Full-page `capture_screenshot` on heavy product pages can time out (60s+); prefer JS text extraction over screenshots here.
- **Gallery-image vision analysis misleads** — the first images returned may be unrelated vendor promos; don't spec a board from them.
- **Reference designs get discontinued** (404 product pages); verify availability rather than citing a classic part the user can't buy.
- **Advertise ≠ deliver on marketplace listings**: 'Active Output' CT boards, e.g., are op-amp AC biased at 2.5V, not rectified 0-5V DC — measure-or-forum evidence beats every title keyword. When nothing literally satisfies the requirement, say so and offer the workaround instead of stretching the shortlist.
- AliExpress keyword search is loose — 'no results with my exact phrase' is not evidence the product doesn't exist; re-run with fewer terms before concluding.
