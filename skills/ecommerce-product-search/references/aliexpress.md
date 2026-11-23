# AliExpress notes

## URL patterns

- Search: `https://www.aliexpress.com/w/wholesale-<query-words-dashed>.html` (redirects from `/wholesale?SearchText=...` too).
- Product: `https://www.aliexpress.com/item/<id>.html`.
- Currency displays per locale (e.g. AUD when session is AU).

## Listing extraction (proven JS)

```js
(() => {
  const cards = document.querySelectorAll('a[href*="/item/"]');
  const seen = new Set(); const out = [];
  cards.forEach(a => {
    const href = a.href.split('?')[0];
    const title = (a.textContent || '').trim().replace(/\s+/g, ' ');
    if (!title || title.length < 15 || seen.has(href)) return;
    seen.add(href);
    out.push({title: title.slice(0,150), href});
  });
  return JSON.stringify(out.slice(0, 25));
})()
```

Prices are embedded in the title text (duplicated strings, strike price after the selling price) — regex them out rather than hunting a separate price node.

## Product page facts

- Spec table lives behind a lazy 'Specifications' tab; the 'Supply Voltage' style fields can literally be blank.
- 'Description' tab content lazy-loads on click + scroll; text grepping `document.body.innerText` after one scroll pass usually captures only header/footer + AI overview.
- Heavy pages: `Page.captureScreenshot` can exceed 60s IPC timeout — avoid full-page shots, scroll + JS-extract instead.
- No login wall for reading listings at browsing volume encountered; bot-walls handled by `blocked-page-recovery` if they appear.

## Domain note: ZMCT103C current-sensor boards (asked 2026-11)

- Bare ZMCT103C is a 1000:1 CT (5A:5mA) — AC only, needs burden resistor.
- Ubiquitous AU$1-3 'Active Output Onboard' boards (38x18.5mm, op-amp + gain trimmer): output is amplified AC centered on ~2.5V DC bias — NOT current-proportional DC. Verified via Arduino forum thread on the identical board.
- The Seeed Studio 'Active Current Transformer Sensor ZMCT103C' (rectifier + smoothing, true 0-5V DC out) is discontinued; no Seeed-style clone found on AliExpress — hence 'buy the cheap board + rectify/RMS in software' is the standing recommendation for a DC-output requirement.
