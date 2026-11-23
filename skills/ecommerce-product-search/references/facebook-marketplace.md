# Facebook Marketplace (logged out, no login)

Verified 2026-11-24 through the host headless Chrome, no session, no cookies:

| URL slug | Results page said | Item links |
|---|---|---|
| `sydney` | "Sydney, Australia · Within 65 km" | 24 |
| `toronto` | "Toronto, Ontario" | 24 |
| `vancouver` | "Vancouver, British Columbia" | 24 |

Prices render with local currency and seller city (`CA$280 Harman Kardon Aura Studio 4 Bluetooth Speaker – Black Vancouver, BC`).

**Do not log in "to change the region".** The slug does that. Logging in adds account-ban risk for nothing.

## Procedure

1. Navigate to `https://www.facebook.com/marketplace/<city>/search/?query=<url-encoded query>`.
   Useful slugs: `sydney`, `melbourne`, `brisbane`, `toronto`, `vancouver`, `montreal`, `hongkong`.
2. **Read the location line before trusting results.** A slug Facebook does not recognise falls back to a default city silently, and a zero-result page then means nothing. If the line names a city you did not ask for, re-issue the URL rather than typing in the region pill (its autocomplete rejects injected text).
3. Extract in one JS call:

```js
(() => {
  const seen = new Set(), out = [];
  document.querySelectorAll('a[href*="/marketplace/item/"]').forEach(a => {
    const href = a.href.split('?')[0];
    if (seen.has(href)) return;
    const text = (a.innerText || '').replace(/\s+/g, ' ').trim();
    if (!text) return;
    seen.add(href);
    out.push({ text: text.slice(0, 120), href });
  });
  return JSON.stringify(out.slice(0, 30));
})()
```

4. The grid is virtualised: one `scrollBy` pass with a short wait, then re-extract, before concluding anything is absent.
5. The search engine is fuzzy — it returns concert tickets, phones and unrelated categories for a speaker query. Filter by the model keyword before reporting, and state which product the prices belong to when a model name spans generations.
6. Item pages render logged out too — open one when you need exact price, condition, location or listed date.

## Notes

- "Marketplace" is login-walled as a *site*; the search results page is not. Do not confuse the two and do not attempt `facebook.com/marketplace` root (it redirects to a default city).
- Personal-data handling: listing text can include seller names. Report listing facts, not seller identities.
- If Facebook starts challenging (login prompt mid-search), stop and report that marketplace as unavailable rather than retrying — this route has no fallback other than `web_search site:facebook.com/marketplace`.
