#!/usr/bin/env python3
"""
Browser-Based Vendor Page Extractor
====================================
Uses Hermes browser tools (browser_navigate, browser_snapshot, browser_console)
to extract pricing, stock, and lead time from marine vendor product pages.

NOT a CLI tool — this is imported by the agent during procurement workflow.
The agent calls browser_navigate + browser_console per vendor page, then
uses these extraction patterns to parse the results.

Extraction Strategy (per vendor):
  1. browser_navigate to product/search URL
  2. browser_snapshot to see page structure
  3. browser_console(expression=...) to extract DOM nodes for price/stock
  4. Parse the returned text into structured data

This file documents the CSS selectors and extraction patterns for each
known vendor, plus provides a parsing function for the agent to use.
"""

import json
import re

# ─── Vendor-specific extraction selectors ───
# Each vendor has different HTML structure. These are the known patterns.
# Format: {css_selector: [field_name, transform_fn]}

VENDOR_EXTRACTORS = {
    "Holland Marine Products": {
        "url_pattern": "hollandmarine.com",
        "price_selectors": [
            ".price", ".product-price", ".woocommerce-Price-amount",
            '[itemprop="price"]', ".regular-price"
        ],
        "stock_selectors": [
            ".stock", ".availability", ".in-stock", ".out-of-stock",
            '[itemprop="availability"]', ".product-inventory"
        ],
        "title_selectors": [
            ".product_title", "h1", '[itemprop="name"]', ".entry-title"
        ],
    },
    "Brewers' Marine Supply": {
        "url_pattern": "brewersmarine.com",
        "price_selectors": [".price", ".product-price", ".woocommerce-Price-amount"],
        "stock_selectors": [".stock", ".availability", ".in-stock"],
        "title_selectors": [".product_title", "h1", ".entry-title"],
    },
    "Marine Outfitters": {
        "url_pattern": "marineoutfitters.ca",
        "price_selectors": [".price", ".product-price", ".ourprice", ".saleprice"],
        "stock_selectors": [".stock", ".availability", ".inv"],
        "title_selectors": ["h1", ".productname", ".item-title"],
    },
    "Defender Marine": {
        "url_pattern": "defender.com",
        "price_selectors": ['.price', '[data-price-type="finalPrice"]', '.special-price .price', '.regular-price .price'],
        "stock_selectors": ['.stock', '.availability', '[data-stock]', '.delivery-message'],
        "title_selectors": ['[data-ui-id="page-title-wrapper"]', 'h1', '.product-name'],
    },
    "Fisheries Supply": {
        "url_pattern": "fisheriessupply.com",
        "price_selectors": [".price", ".product-price", ".our-price"],
        "stock_selectors": [".stock", ".availability", ".ship-message"],
        "title_selectors": ["h1", ".product-name", ".item-name"],
    },
    "Hamilton Marine": {
        "url_pattern": "hamiltonmarine.com",
        "price_selectors": [".price", ".product-price", ".pricing"],
        "stock_selectors": [".stock", ".availability"],
        "title_selectors": ["h1", ".product-title"],
    },
    "Steveston Marine": {
        "url_pattern": "stevestonmarine.com",
        "price_selectors": [".price", ".product-price"],
        "stock_selectors": [".stock", ".availability"],
        "title_selectors": ["h1", ".product-title"],
    },
}

# ─── Generic fallback selectors (tried when vendor not in known list) ───
GENERIC_SELECTORS = {
    "price": [
        ".price", '[itemprop="price"]', '.product-price', '.woocommerce-Price-amount',
        '.regular-price', '.sale-price', '.our-price', '[data-price]',
        'meta[itemprop="price"]', '.product__price', '.pdp-price',
        'span:contains("$")', '.amount', '.woocommerce-Price-currencySymbol',
    ],
    "stock": [
        ".stock", ".availability", '[itemprop="availability"]',
        '.in-stock', '.out-of-stock', '.add-to-cart', '.product-inventory',
        '.shipping-message', '.delivery-message', '.lead-time',
    ],
    "title": [
        "h1", '[itemprop="name"]', '.product-title', '.product_name',
        '.entry-title', '.product-name', '.item-title',
    ],
}

# ─── JavaScript extraction snippets ───
# These are passed to browser_console(expression=...) to extract data from
# the page without needing to parse the accessibility tree.

EXTRACTION_SCRIPTS = {
    "price": """
(function() {
    var selectors = [{selectors}];
    for (var i = 0; i < selectors.length; i++) {
        var el = document.querySelector(selectors[i]);
        if (el) {
            var text = (el.textContent || el.getAttribute('content') || el.value || '').trim();
            if (text && text.match(/[$£€]|\\d+\\.?\\d*/)) return text;
        }
    }
    return '';
})()
""",
    "stock": """
(function() {
    var selectors = [{selectors}];
    for (var i = 0; i < selectors.length; i++) {
        var el = document.querySelector(selectors[i]);
        if (el) {
            var text = (el.textContent || el.value || '').trim().toLowerCase();
            if (text) return text;
        }
    }
    // Check for Add to Cart button as proxy for in-stock
    var atc = document.querySelector('button:contains("Add to Cart"), button:contains("Buy"), [type="submit"]:contains("Add")');
    if (atc) return 'in stock (add to cart available)';
    return '';
})()
""",
    "title": """
(function() {
    var selectors = [{selectors}];
    for (var i = 0; i < selectors.length; i++) {
        var el = document.querySelector(selectors[i]);
        if (el) {
            var text = el.textContent.trim();
            if (text && text.length > 3) return text.substring(0, 200);
        }
    }
    return document.title || '';
})()
""",
    # All-in-one extraction — single browser_console call gets everything
    "all": """
(function() {
    var result = {price: '', stock: '', title: ''};
    
    // Title
    var titleSelectors = [{title_selectors}];
    for (var i = 0; i < titleSelectors.length; i++) {
        var tel = document.querySelector(titleSelectors[i]);
        if (tel) { result.title = tel.textContent.trim().substring(0, 200); break; }
    }
    if (!result.title) result.title = document.title || '';
    
    // Price
    var priceSelectors = [{price_selectors}];
    for (var i = 0; i < priceSelectors.length; i++) {
        var pel = document.querySelector(priceSelectors[i]);
        if (pel) {
            var txt = (pel.textContent || pel.getAttribute('content') || '').trim();
            txt = txt.replace(/[\\n\\r\\t]+/g, ' ').replace(/\\s+/g, ' ');
            if (txt && /[$£€]|\\d/.test(txt)) { result.price = txt; break; }
        }
    }
    
    // Stock
    var stockSelectors = [{stock_selectors}];
    for (var i = 0; i < stockSelectors.length; i++) {
        var sel = document.querySelector(stockSelectors[i]);
        if (sel) { result.stock = sel.textContent.trim(); break; }
    }
    if (!result.stock) {
        var atc = document.querySelector('button, [type="submit"]');
        if (atc && /add|buy|cart/i.test(atc.textContent)) result.stock = 'likely in stock';
    }
    
    return JSON.stringify(result);
})()
""",
}


def build_extraction_script(vendor_name=None):
    """Build the JavaScript extraction snippet for a specific vendor or generic."""
    if vendor_name and vendor_name in VENDOR_EXTRACTORS:
        ve = VENDOR_EXTRACTORS[vendor_name]
        title_sels = json.dumps(ve["title_selectors"])
        price_sels = json.dumps(ve["price_selectors"])
        stock_sels = json.dumps(ve["stock_selectors"])
    else:
        title_sels = json.dumps(GENERIC_SELECTORS["title"])
        price_sels = json.dumps(GENERIC_SELECTORS["price"])
        stock_sels = json.dumps(GENERIC_SELECTORS["stock"])
    
    return EXTRACTION_SCRIPTS["all"].replace(
        "{title_selectors}", title_sels
    ).replace(
        "{price_selectors}", price_sels
    ).replace(
        "{stock_selectors}", stock_sels
    )


def parse_price(raw_price, currency_hint="CAD"):
    """Parse a raw price string into normalized form."""
    if not raw_price:
        return None
    
    raw_price = raw_price.strip().replace(",", "")
    
    # Detect currency
    currency = currency_hint
    if "$" in raw_price:
        currency = "USD" if "US" in raw_price.upper() else currency_hint
    elif "€" in raw_price:
        currency = "EUR"
    elif "£" in raw_price:
        currency = "GBP"
    
    # Extract numeric value
    match = re.search(r'[\d.]+', raw_price.replace("$", "").replace("€", "").replace("£", ""))
    if match:
        try:
            value = float(match.group())
            return {"amount": value, "currency": currency, "raw": raw_price, "display": f"{currency} ${value:,.2f}" if currency in ("CAD", "USD") else raw_price}
        except ValueError:
            pass
    
    return {"amount": None, "currency": currency, "raw": raw_price, "display": raw_price}


def parse_stock(raw_stock):
    """Parse raw stock text into standardized status."""
    if not raw_stock:
        return {"status": "unknown", "label": "—", "class": "stock-out"}
    
    raw = raw_stock.lower().strip()
    
    if any(w in raw for w in ["in stock", "in-stock", "available", "add to cart", "inventory", "qty", "quantity"]):
        return {"status": "in_stock", "label": "In Stock", "class": "stock-in"}
    elif any(w in raw for w in ["out of stock", "out-of-stock", "sold out", "unavailable", "discontinued"]):
        return {"status": "out_of_stock", "label": "Out of Stock", "class": "stock-out"}
    elif any(w in raw for w in ["backorder", "back order", "special order", "lead time", "pre-order"]):
        return {"status": "special_order", "label": "Special Order", "class": "stock-limited"}
    elif any(w in raw for w in ["limited", "low stock", "few left", "only", "remaining"]):
        return {"status": "limited", "label": "Low Stock", "class": "stock-limited"}
    elif "likely in stock" in raw:
        return {"status": "likely_in_stock", "label": "Likely In Stock", "class": "stock-in"}
    else:
        return {"status": "unknown", "label": raw_stock[:30], "class": "stock-out"}


# ─── Agent workflow instructions ───
# The agent follows this pattern for each vendor product page:

AGENT_WORKFLOW = """
For each vendor with a likely product URL:

1. browser_navigate(url="<product_or_search_url>")
   → Returns page snapshot with interactive elements

2. browser_console(expression=<extraction_script>)
   → Returns JSON: {"price": "...", "stock": "...", "title": "..."}
   
   Build the script with:
   from vendor_page_extractor import build_extraction_script
   script = build_extraction_script("<vendor_name>")
   
3. Parse results:
   from vendor_page_extractor import parse_price, parse_stock
   price_data = parse_price(result["price"])
   stock_data = parse_stock(result["stock"])

4. If price not found in console output, check the snapshot:
   - Scroll browser_scroll(down) to reveal price section
   - browser_snapshot(full=true) to read page structure
   - Look for price in the text snapshot

5. If page is JS-heavy and snapshot shows no content:
   - Wait 2-3 seconds (browser_navigate handles dynamic content)
   - Try browser_console again
   - Fall back to: web_search("site:<domain> <part_number> price") to find Google-cached pricing
"""


if __name__ == "__main__":
    # Test: print extraction scripts for known vendors
    print("=== Holland Marine Products extraction script ===\n")
    print(build_extraction_script("Holland Marine Products")[:500] + "...\n")
    
    print("=== Generic extraction script ===\n")
    print(build_extraction_script()[:500] + "...\n")
    
    print("=== Price parsing tests ===")
    tests = ["$45.99", "CAD $129.95", "US $89.99", "€34.50", "45.99", "", None]
    for t in tests:
        print(f"  '{t}' → {parse_price(t)}")
    
    print("\n=== Stock parsing tests ===")
    tests = ["In Stock", "Out of Stock", "Only 3 left", "Special Order - 2 weeks", "", None]
    for t in tests:
        print(f"  '{t}' → {parse_stock(t)}")
