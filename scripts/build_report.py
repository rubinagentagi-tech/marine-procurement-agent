#!/usr/bin/env python3
"""
Marine Procurement HTML Report Builder
=======================================
Takes vendor search results (JSON) and the HTML template, fills in values,
and outputs the final HTML report ready for publishing to here.now.

Usage: python3 build_report.py --results results.json --part-number "Jabsco 18670-0001" --output report.html
"""

import json
import sys
import os
import argparse
from datetime import datetime, timezone

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marine_report_template.html")

def load_template():
    with open(TEMPLATE_PATH) as f:
        return f.read()

def fill_template(template, data):
    """Simple {{VAR}} template substitution."""
    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"
        if placeholder in template:
            template = template.replace(placeholder, str(value) if value else "—")
    # Conditional blocks: {{#KEY}}...{{/KEY}} — show if key is truthy, hide if falsy
    import re
    for match in re.finditer(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', template, re.DOTALL):
        key = match.group(1)
        inner = match.group(2)
        if data.get(key):
            # Unwrap: show the inner content
            template = template.replace(match.group(0), inner.replace(f"{{{{{key}}}}}", str(data[key])))
        else:
            # Hide the entire block
            template = template.replace(match.group(0), "")
    return template

def extract_best(results):
    """Extract quick summary stats from vendor results."""
    best_price = None
    best_price_vendor = "N/A"
    fastest_lead = "N/A"
    fastest_lead_vendor = "N/A"
    best_near_source_score = 0
    best_near_source_vendor = "N/A"
    best_near_source_city = "N/A"
    
    for v in results:
        # Near source
        score = v.get("near_source_score", 0)
        if score > best_near_source_score:
            best_near_source_score = score
            best_near_source_vendor = v.get("name", v.get("vendor", "N/A"))
            best_near_source_city = v.get("city", "N/A")
        
        # Price (rough comparison — different currencies not normalized here)
        price = v.get("price", "")
        if price and price != "—":
            if best_price is None:
                best_price = price
                best_price_vendor = v.get("name", v.get("vendor", "N/A"))
        
        # Lead time
        lead = v.get("lead_time", "")
        if lead and "fast" in str(lead).lower():
            if fastest_lead == "N/A":
                fastest_lead = lead.get("label", str(lead)) if isinstance(lead, dict) else str(lead)
                fastest_lead_vendor = v.get("name", v.get("vendor", "N/A"))
    
    return {
        "BEST_PRICE": best_price or "—",
        "BEST_PRICE_VENDOR": best_price_vendor,
        "FASTEST_LEAD": fastest_lead,
        "FASTEST_LEAD_VENDOR": fastest_lead_vendor,
        "BEST_NEAR_SOURCE_SCORE": best_near_source_score,
        "BEST_NEAR_SOURCE_VENDOR": best_near_source_vendor,
        "BEST_NEAR_SOURCE_CITY": best_near_source_city,
    }

def main():
    parser = argparse.ArgumentParser(description="Build Marine Procurement HTML Report")
    parser.add_argument("--results", required=True, help="JSON file with vendor search results")
    parser.add_argument("--part-number", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--brand", default="")
    parser.add_argument("--category", default="general")
    parser.add_argument("--output", default="/tmp/marine-report.html")
    args = parser.parse_args()
    
    with open(args.results) as f:
        results = json.load(f)
    
    # If results is the full instructions format, extract vendor_searches
    if "instructions" in results:
        vendors = results["instructions"].get("vendor_searches", [])
    elif isinstance(results, list):
        vendors = results
    else:
        vendors = results.get("vendor_searches", results.get("vendors", []))
    
    template = load_template()
    
    # Build vendor rows and gauges
    # Normalize vendor keys: vendor_searches uses 'vendor', render fn expects 'name'/'city'/'province'/'country'
    for v in vendors:
        if "vendor" in v and "name" not in v:
            v["name"] = v["vendor"]
        if "location" in v:
            parts = [p.strip() for p in v["location"].split(",")]
            v["city"] = v.get("city") or (parts[0] if len(parts) > 0 else "")
            v["province"] = v.get("province") or (parts[1] if len(parts) > 1 else "")
            v["country"] = v.get("country") or (parts[2] if len(parts) > 2 else "")
    
    from vendor_search import render_vendor_row, render_near_sourcing_gauge
    
    vendor_rows_html = "\n        ".join(render_vendor_row(v) for v in vendors)
    gauges_html = "\n  ".join(render_near_sourcing_gauge(v) for v in vendors)
    
    # Quick summary
    best = extract_best(vendors)
    
    # Cost estimate (use best near-source vendor)
    best_vendor = None
    max_score = 0
    for v in vendors:
        if v.get("near_source_score", 0) > max_score:
            max_score = v.get("near_source_score", 0)
            best_vendor = v
    
    currency = "CAD"
    if best_vendor:
        currency = best_vendor.get("currency", "CAD")
        cost_vendor_name = best_vendor.get("name", best_vendor.get("vendor", "N/A"))
        price = best_vendor.get("price", "—")
        shipping = best_vendor.get("shipping_estimate", {}).get("estimate", "CAD $10-25")
    else:
        cost_vendor_name = "N/A"
        price = "—"
        shipping = "—"
    
    data = {
        "REPORT_TIMESTAMP": datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC"),
        "PART_NUMBER": args.part_number,
        "PART_DESCRIPTION": args.description or "See part number",
        "PART_BRAND": args.brand or "Unknown",
        "PART_CATEGORY": args.category,
        "PART_OEM_EQUIVALENT": "",
        "PART_IMAGE_SRC": "",
        "VENDOR_ROWS": vendor_rows_html,
        "NEAR_SOURCING_GAUGES": gauges_html,
        "COST_VENDOR": cost_vendor_name,
        "COST_ITEM_PRICE": price,
        "COST_SHIPPING": shipping,
        "COST_DUTY": "",
        "COST_DUTY_RATE": "",
        "COST_HST": "",
        "COST_TOTAL": price if price != "—" else "—",
        "CURRENCY": currency,
        "FX_RATE": "N/A",
        "REPORT_URL": "https://marine-procurement.here.now (publish after generation)",
        **best,
    }
    
    html = fill_template(template, data)
    
    with open(args.output, "w") as f:
        f.write(html)
    
    print(json.dumps({"output_path": args.output, "size_bytes": len(html)}))

if __name__ == "__main__":
    main()
