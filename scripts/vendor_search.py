#!/usr/bin/env python3
"""
Marine Procurement — Vendor Search Pipeline
============================================
Searches known marine vendors for a given part and returns structured results.
Uses web_search, web_extract, and browser_navigate where needed.
Run from Hermes execute_code or terminal with part details as args.

Usage: python3 vendor_search.py --part "Jabsco 18670-0001" [--brand "Jabsco"] [--category "impeller"]

Outputs JSON to stdout with vendor_results array.
"""

import json
import sys
import os
import argparse
from datetime import datetime, timezone

# ─── Vendor Registry (loaded from JSON, fallback inline) ───
REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "references", "vendor-registry.json"
)

def load_registry():
    try:
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback: embedded minimal registry for cron/remote execution
        return {
            "vendors": [
                {"name": "Holland Marine Products", "tier": 1, "city": "Toronto", "province": "ON", "country": "Canada", "currency": "CAD", "website": "https://www.hollandmarine.com", "search_url": "https://www.hollandmarine.com/search?q={query}", "near_source_score": 10},
                {"name": "Brewers' Marine Supply", "tier": 1, "city": "Hamilton", "province": "ON", "country": "Canada", "currency": "CAD", "website": "https://www.brewersmarine.com", "search_url": "https://www.brewersmarine.com/search?q={query}", "near_source_score": 10},
                {"name": "C.C. Marine Distributors", "tier": 1, "city": "Canada-wide", "province": "ON", "country": "Canada", "currency": "CAD", "website": "https://ccmarine.ca", "search_url": "https://ccmarine.ca/search?q={query}", "near_source_score": 9},
                {"name": "Marine Outfitters", "tier": 1, "city": "Ontario", "province": "ON", "country": "Canada", "currency": "CAD", "website": "https://www.marineoutfitters.ca", "search_url": "https://www.marineoutfitters.ca/index.cfm?search={query}", "near_source_score": 9},
                {"name": "OBR Oil & Marine", "tier": 1, "city": "Canada", "province": "ON", "country": "Canada", "currency": "CAD", "website": "https://www.obroilandmarine.com", "search_url": "https://www.obroilandmarine.com/search?q={query}", "near_source_score": 8},
                {"name": "Steveston Marine", "tier": 2, "city": "Vancouver", "province": "BC", "country": "Canada", "currency": "CAD", "website": "https://www.stevestonmarine.com", "search_url": "https://www.stevestonmarine.com/search?q={query}", "near_source_score": 7},
                {"name": "Trotac Marine", "tier": 2, "city": "Victoria", "province": "BC", "country": "Canada", "currency": "CAD", "website": "https://trotac.ca", "search_url": "https://trotac.ca/search?q={query}", "near_source_score": 5},
                {"name": "Defender Marine", "tier": 3, "city": "Waterford", "province": "CT", "country": "USA", "currency": "USD", "website": "https://defender.com", "search_url": "https://defender.com/en_us/search?q={query}", "near_source_score": 3},
                {"name": "Hamilton Marine", "tier": 3, "city": "Searsport", "province": "ME", "country": "USA", "currency": "USD", "website": "https://hamiltonmarine.com", "search_url": "https://shop.hamiltonmarine.com/inet/storefront/store.php?mode=searchstore&search[searchfor]={query}", "near_source_score": 2},
                {"name": "Fisheries Supply", "tier": 3, "city": "Seattle", "province": "WA", "country": "USA", "currency": "USD", "website": "https://www.fisheriessupply.com", "search_url": "https://www.fisheriessupply.com/search?q={query}", "near_source_score": 2},
            ],
            "tiers": {
                "1": {"label": "GTA / Southern Ontario", "color": "#22C55E", "score_range": [8, 10]},
                "2": {"label": "Canada", "color": "#EAB308", "score_range": [4, 7]},
                "3": {"label": "US / International", "color": "#EF4444", "score_range": [1, 3]},
            },
            "duty_estimate": {"most_favored_nation": "5-7%", "usmca_exempt": "0%"}
        }

def build_search_queries(part_number, part_description, brand):
    """Build all search query variants for a part."""
    queries = []
    
    # Primary: exact part number
    if part_number:
        queries.append(part_number)
        if brand:
            queries.append(f"{brand} {part_number}")
    
    # Description-based
    if part_description:
        if brand:
            queries.append(f"{brand} {part_description}")
        queries.append(f"{part_description} marine")
    
    # Aftermarket variants
    if part_number and "marine" not in (part_description or "").lower():
        queries.append(f"{part_number} marine")
    
    # Canadian-market focused
    if part_number:
        queries.append(f"{part_number} Canada price")
        queries.append(f"{part_number} Ontario supplier")
    
    return queries[:8]  # Cap at 8 queries

def estimate_shipping(vendor, item_category="general"):
    """Rough shipping estimates per vendor tier."""
    tier = vendor.get("tier", 3)
    country = vendor.get("country", "USA")
    
    if tier == 1:
        # GTA/Ontario — could be pickup, courier, or free over threshold
        return {"estimate": "CAD $10-25", "method": "Courier / Pickup", "days": "1-3"}
    elif tier == 2:
        # Canada — domestic shipping
        return {"estimate": "CAD $15-35", "method": "Canada Post / Courier", "days": "3-7"}
    else:
        # US/International
        return {"estimate": "USD $15-50", "method": "USPS/UPS to Canada", "days": "5-14"}

def estimate_lead_time(vendor):
    """Estimate lead time based on tier and location."""
    tier = vendor.get("tier", 3)
    if tier == 1:
        return {"label": "1-3 days", "class": "lead-fast"}
    elif tier == 2:
        return {"label": "3-7 days", "class": "lead-medium"}
    else:
        return {"label": "1-3 weeks", "class": "lead-slow"}

def format_search_instructions(registry, part_number, part_description, brand):
    """
    Generate search instructions for the LLM to execute via web_search calls.
    This is returned as part of the output so the agent knows what to search.
    """
    vendors = registry["vendors"]
    instructions = {
        "part": {
            "number": part_number,
            "description": part_description,
            "brand": brand,
        },
        "search_queries": build_search_queries(part_number, part_description, brand),
        "vendor_searches": [],
    }
    
    for v in vendors:
        search_url = v.get("search_url", "").replace("{query}", (part_number or part_description or ""))
        instructions["vendor_searches"].append({
            "vendor": v["name"],
            "tier": v["tier"],
            "location": f"{v['city']}, {v['province']}, {v['country']}",
            "currency": v["currency"],
            "website": v["website"],
            "search_query": f"site:{v['website'].replace('https://', '').replace('www.', '')} {part_number} {part_description or ''}",
            "search_url": search_url,
            "near_source_score": v.get("near_source_score", 1),
        })
    
    return instructions

def render_vendor_row(v):
    """Render a single vendor row for the HTML template."""
    tier = v.get("tier", 3)
    score = v.get("near_source_score", 1)
    score_class = "gauge-g" if score >= 8 else "gauge-y" if score >= 4 else "gauge-r"
    score_num_class = "gauge-g-num" if score >= 8 else "gauge-y-num" if score >= 4 else "gauge-r-num"
    
    price = v.get("price") or "—"
    currency = v.get("currency", "USD")
    stock = v.get("stock") or "—"
    stock_class = "stock-in" if "stock" in str(stock).lower() else "stock-out"
    lead = v.get("lead_time") or estimate_lead_time(v)
    lead_html = f'<span class="{lead["class"]}">{lead["label"]}</span>'
    
    return f"""<tr>
      <td><span class="tier-badge tier-{tier}">T{tier}</span></td>
      <td>
        <div class="vendor-name">{v['name']}</div>
        <div class="vendor-location">{v.get('city', '')}, {v.get('province', '')}, {v.get('country', '')}</div>
      </td>
      <td><span class="price">{price}</span> <span class="price-currency">{currency}</span></td>
      <td><span class="stock {stock_class}"><span class="stock-dot"></span>{stock}</span></td>
      <td>{lead_html}</td>
      <td>
        <div class="gauge-row">
          <div class="gauge-bar"><div class="gauge-fill {score_class}" style="width:{score*10}%"></div></div>
          <span class="gauge-num {score_num_class}">{score}</span>
        </div>
      </td>
      <td><a class="source-link" href="{v.get('source_url', v.get('website', '#'))}">view →</a></td>
    </tr>"""

def render_near_sourcing_gauge(v):
    """Render a gauge row for the near-sourcing section."""
    score = v.get("near_source_score", 1)
    pct = score * 10
    cls = "gauge-g" if score >= 8 else "gauge-y" if score >= 4 else "gauge-r"
    num_cls = "gauge-g-num" if score >= 8 else "gauge-y-num" if score >= 4 else "gauge-r-num"
    return f"""<div style="margin-bottom:8px;">
    <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px;">
      <span style="color:#E6EDF3;">{v['name']}</span>
      <span style="color:#8B949E;font-size:10px;">{v.get('city', '')}, {v.get('province', '')}</span>
    </div>
    <div class="gauge-row">
      <div class="gauge-bar"><div class="gauge-fill {cls}" style="width:{pct}%"></div></div>
      <span class="gauge-num {num_cls}">{score}/10</span>
    </div>
  </div>"""

def main():
    parser = argparse.ArgumentParser(description="Marine Vendor Search Pipeline")
    parser.add_argument("--part", required=True, help="Part number or name")
    parser.add_argument("--brand", default="", help="Brand/manufacturer")
    parser.add_argument("--description", default="", help="Part description")
    parser.add_argument("--category", default="general", help="Part category")
    parser.add_argument("--format", choices=["json", "html"], default="json", help="Output format")
    args = parser.parse_args()
    
    registry = load_registry()
    instructions = format_search_instructions(
        registry, args.part, args.description, args.brand
    )
    
    if args.format == "html":
        # Build HTML snippet (vendor rows + gauges)
        vendor_rows = []
        gauges = []
        for v in instructions["vendor_searches"]:
            # Align keys: the vendor_searches use 'vendor' for name and 'location' string
            v["name"] = v["vendor"]
            loc = v.get("location", "")
            parts = [p.strip() for p in loc.split(",")]
            v["city"] = parts[0] if len(parts) > 0 else ""
            v["province"] = parts[1] if len(parts) > 1 else ""
            v["country"] = parts[2] if len(parts) > 2 else ""
            vendor_rows.append(render_vendor_row(v))
            gauges.append(render_near_sourcing_gauge(v))
        
        html_snippets = {
            "vendor_rows": "\n        ".join(vendor_rows),
            "near_sourcing_gauges": "\n  ".join(gauges),
        }
        print(json.dumps(html_snippets, indent=2))
    else:
        # Full JSON instructions for the agent
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "instructions": instructions,
            "registry_summary": {
                "total_vendors": len(registry["vendors"]),
                "tier_counts": {
                    "1": sum(1 for v in registry["vendors"] if v["tier"] == 1),
                    "2": sum(1 for v in registry["vendors"] if v["tier"] == 2),
                    "3": sum(1 for v in registry["vendors"] if v["tier"] == 3),
                },
                "duty_estimate": registry.get("duty_estimate", {}),
            }
        }
        print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
