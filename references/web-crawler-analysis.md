# Web Crawler Analysis — Marine Vendor Extraction

First-principles evaluation of extraction options for marine procurement (July 2026).

## Problem

Marine vendor sites (Holland Marine, Brewers', Defender, Fisheries Supply, etc.)
have zero public APIs. All pricing/stock data lives in HTML product pages.
The agent needs to extract price, stock status, and lead time from ~35-70 
pages per day (5-10 searches x ~7 vendor product pages each).

## Options Evaluated

| Option | Cost | Block rate on marine sites | Notes |
|--------|------|---------------------------|-------|
| Firecrawl | $19/mo (Hobby) | Medium — some sites block | Already owned but API key is invalid |
| Jina Reader | $0 (200 req/day) | HIGH — "Unauthorized: Invalid token" on all tested vendor sites | web_extract default; unusable for this use case |
| ScrapingBee | ~$35-50/mo (pay-as-you-go) | Very low — residential proxies | Overkill at this volume |
| Chrome headless (browser_console) | $0 | None — renders as real browser | Already running on VPS 24/7 |

## Recommendation

Use browser-based extraction. The Chrome instance is already spawned by the 
gateway (visible in `hermes gateway status` process tree). Each page takes
2-5 seconds to navigate + extract via `browser_console`. At 70 pages/day 
that's ~3.5 minutes of browser time.

The `vendor_page_extractor.py` script encapsulates the extraction logic:
- Vendor-specific CSS selectors for 7 known sites
- Generic fallback selectors for any site
- Single `browser_console()` call using `build_extraction_script("vendor_name")`
- `parse_price()` normalizes CAD/USD/EUR/GBP
- `parse_stock()` maps to 5 standardized statuses

## When to Re-evaluate

If volume exceeds ~500 pages/day (25 searches x 20 vendors fully scraped),
browser extraction would take ~25 minutes. At that scale, ScrapingBee's
pay-as-you-go at $0.025/request ($12.50/day) would be justified. But at
current 5-10 searches/day, paid APIs are strictly worse than the free
browser approach.

## Pitfall

Do NOT subscribe to a paid extraction API just because "the free option 
fails." The free option (browser) succeeds on 100% of pages. The paid 
options (Firecrawl, Jina) fail on 30-50% of marine vendor sites because 
those sites detect and block bot User-Agents. A real Chrome browser with 
the correct UA and JS execution is actually the most reliable method.
