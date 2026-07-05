#!/usr/bin/env python3
"""
Email-Ready Output Formatter
=============================
Takes vendor search results and formats them as a clean plain-text table
designed to be copy-pasted into Microsoft Outlook (desktop app).

Design constraints:
- Plain text only (no HTML, no markdown — Outlook desktop renders these inconsistently)
- Fixed-width columns aligned with spaces (Outlook preserves spaces in plain-text mode)
- Compact enough to fit in an email body without horizontal scrolling (~80 chars)
- Tier indicators, currency flags, stock status symbols
- Section headers with clear hierarchy

Usage: python3 email_formatter.py --results results.json [--output clipboard]
"""

import json
import sys
import os
import argparse
from datetime import datetime, timezone

def load_results(path):
    with open(path) as f:
        data = json.load(f)
    if "instructions" in data:
        return data["instructions"].get("vendor_searches", [])
    if isinstance(data, list):
        return data
    return data.get("vendor_searches", data.get("vendors", []))

def format_email_body(part_info, vendors):
    """
    Build the full email-ready body as a single string.
    Designed for Ctrl+A → Ctrl+C → Ctrl+V into Outlook.
    """
    lines = []
    now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    
    # ─── HEADER ───
    lines.append("=" * 72)
    lines.append("  MARINE PROCUREMENT REPORT")
    lines.append("  Generated: " + now)
    lines.append("=" * 72)
    lines.append("")
    
    # ─── PART IDENTIFICATION ───
    lines.append("PART:")
    lines.append(f"  Number:      {part_info.get('part_number', 'N/A')}")
    lines.append(f"  Description: {part_info.get('description', 'N/A')}")
    lines.append(f"  Brand:       {part_info.get('brand', 'N/A')}")
    lines.append("")
    
    # ─── QUICK SUMMARY ───
    t1_vendors = [v for v in vendors if v.get("tier") == 1]
    best_price = None
    best_price_vendor = "N/A"
    best_near = None
    best_near_score = 0
    
    for v in vendors:
        score = v.get("near_source_score", 0)
        if score > best_near_score:
            best_near_score = score
            best_near = v
        price = v.get("price", "")
        if price and price != "—":
            if best_price is None or (isinstance(price, str) and "CAD" in price):
                best_price = price
                best_price_vendor = v.get("name", v.get("vendor", "N/A"))
    
    lines.append("QUICK SUMMARY:")
    if best_price and best_price != "—":
        lines.append(f"  Best Price:   {best_price} at {best_price_vendor}")
    if best_near:
        loc = best_near.get("location", best_near.get("city", ""))
        lines.append(f"  Best Source:  {best_near.get('name', best_near.get('vendor', 'N/A'))} ({loc}) — Near-Source Score: {best_near_score}/10")
    lines.append("")
    
    # ─── VENDOR TABLE ───
    # Column layout: Tier | Vendor (24) | Price (14) | Stock (14) | Lead (10) | Location (18)
    # Total: ~80 chars
    SEP = "-" * 90
    HEADER = f" {'Tier':4s}  {'Vendor':26s}  {'Price':14s}  {'Stock':12s}  {'Lead':12s}  {'Location'}"
    
    lines.append("VENDOR COMPARISON:")
    lines.append(SEP)
    lines.append(HEADER)
    lines.append(SEP)
    
    for v in vendors:
        tier = v.get("tier", 3)
        tier_label = f"T{tier}"
        if tier == 1:
            tier_label += " *"  # star for GTA
        
        name = v.get("name", v.get("vendor", "N/A"))
        # Truncate long names
        if len(name) > 26:
            name = name[:23] + "..."
        
        price = v.get("price", "—")
        if isinstance(price, dict):
            price = price.get("display", price.get("raw", "—"))
        price = str(price) if price else "—"
        if len(price) > 14:
            price = price[:11] + "..."
        
        stock = v.get("stock", "—")
        if isinstance(stock, dict):
            stock = stock.get("label", "—")
        stock = str(stock) if stock else "—"
        if len(stock) > 12:
            stock = stock[:9] + "..."
        
        lead = v.get("lead_time", "")
        if isinstance(lead, dict):
            lead = lead.get("label", "—")
        lead = str(lead) if lead else "—"
        if len(lead) > 12:
            lead = lead[:9] + "..."
        
        location = v.get("location", "")
        if not location:
            city = v.get("city", "")
            province = v.get("province", "")
            if city or province:
                location = f"{city}, {province}"
        location = str(location) if location else "—"
        if len(location) > 23:
            location = location[:20] + "..."
        
        lines.append(f" {tier_label:4s}  {name:26s}  {price:14s}  {stock:12s}  {lead:12s}  {location}")
    
    lines.append(SEP)
    lines.append("")
    lines.append("Tier Legend:  T1* = GTA / Southern Ontario   T2 = Canada   T3 = US / International")
    lines.append("")
    
    # ─── NEAR-SOURCING SCORES ───
    lines.append("NEAR-SOURCING SCORES (1-10, higher = closer to Hamilton/Toronto):")
    lines.append("-" * 50)
    for v in vendors:
        name = v.get("name", v.get("vendor", "N/A"))
        score = v.get("near_source_score", 0)
        location = v.get("location", "")
        if not location:
            location = f"{v.get('city', '')}, {v.get('province', '')}"
        bar = "█" * score + "░" * (10 - score)
        color = "GREEN" if score >= 8 else "YELLOW" if score >= 4 else "RED"
        lines.append(f"  {name:30s} [{bar}] {score}/10 {color}  ({location})")
    
    lines.append("")
    
    # ─── ESTIMATED COST (best option) ───
    if best_near:
        name = best_near.get("name", best_near.get("vendor", "N/A"))
        price_str = best_near.get("price", "—")
        if isinstance(price_str, dict):
            price_str = price_str.get("display", "—")
        currency = best_near.get("currency", "CAD")
        
        lines.append("ESTIMATED TOTAL COST (Best Near-Source Option):")
        lines.append("-" * 50)
        lines.append(f"  Vendor:        {name}")
        lines.append(f"  Part Price:    {price_str}")
        lines.append(f"  Est. Shipping: {'CAD $10-25' if best_near.get('tier') == 1 else 'CAD $15-35'}")
        lines.append(f"  Est. HST:      {'~' + str(round(float(str(price_str).replace('CAD $','').replace('USD $','').replace('$','').strip() or 0) * 0.13, 2)) + ' ' + currency if price_str != '—' else '—'}")
        lines.append(f"  Total Est:     {'Varies — confirm with vendor'}")
        lines.append(f"  Currency:      {currency}")
        lines.append("")
    
    # ─── SOURCE LINKS ───
    lines.append("SOURCE LINKS:")
    lines.append("-" * 50)
    for v in vendors:
        name = v.get("name", v.get("vendor", "N/A"))
        url = v.get("source_url", v.get("website", ""))
        if url:
            lines.append(f"  {name}: {url}")
    
    lines.append("")
    
    # ─── FOOTER ───
    lines.append("=" * 72)
    lines.append("  Generated by Marine Procurement Agent")
    lines.append("  Full HTML report available on request")
    lines.append("  Prices/stock per vendor websites — confirm before ordering.")
    lines.append("=" * 72)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Format marine procurement results for email")
    parser.add_argument("--results", required=True, help="JSON results file from vendor_search.py")
    parser.add_argument("--part-number", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--brand", default="")
    parser.add_argument("--output", default=None, help="Output file (default: stdout)")
    args = parser.parse_args()
    
    vendors = load_results(args.results)
    
    part_info = {
        "part_number": args.part_number,
        "description": args.description,
        "brand": args.brand,
    }
    
    body = format_email_body(part_info, vendors)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(body)
        print(f"Written to {args.output}")
    else:
        print(body)


if __name__ == "__main__":
    main()
