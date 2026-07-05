# Build Pipeline Notes — Marine Procurement Agent

Data shape normalization, key mapping, and pitfalls discovered during build.

## Key Mapping: vendor_searches vs vendor rows

`vendor_search.py` outputs a flat structure in `instructions.vendor_searches[]`:
```json
{
  "vendor": "Holland Marine Products",
  "tier": 1,
  "location": "Toronto, ON, Canada",
  "currency": "CAD",
  "website": "https://www.hollandmarine.com",
  "search_query": "site:hollandmarine.com Jabsco 18670-0001",
  "search_url": "https://www.hollandmarine.com/search?q=...",
  "near_source_score": 10
}
```

But `render_vendor_row()` and `render_near_sourcing_gauge()` expect:
```json
{
  "name": "Holland Marine Products",
  "tier": 1,
  "city": "Toronto",
  "province": "ON",
  "country": "Canada",
  "currency": "CAD",
  "website": "https://www.hollandmarine.com",
  "near_source_score": 10,
  "price": "CAD $45.99",
  "stock": "In Stock",
  "lead_time": {"label": "1-3 days", "class": "lead-fast"},
  "source_url": "https://hollandmarine.com/product/..."
}
```

### Normalization snippet (add to any new consumer)

```python
for v in vendors:
    if "vendor" in v and "name" not in v:
        v["name"] = v["vendor"]
    if "location" in v:
        parts = [p.strip() for p in v["location"].split(",")]
        v["city"] = v.get("city") or (parts[0] if len(parts) > 0 else "")
        v["province"] = v.get("province") or (parts[1] if len(parts) > 1 else "")
        v["country"] = v.get("country") or (parts[2] if len(parts) > 2 else "")
```

This normalizer exists in:
- `vendor_search.py` — in the `--format html` branch (line ~204)
- `build_report.py` — after JSON load, before calling render functions (line ~108)

## Price Field

The `price` field is intentionally absent from initial `vendor_search.py` output.
It gets populated by the agent after web_search / browser extraction:

```python
v["price"] = "CAD $45.99"
v["source_url"] = "https://hollandmarine.com/product/jabsco-18670-0001"
```

Before prices exist, the table shows `—` in price columns. The email formatter
and HTML template both handle this gracefully.

## Verification

The verification script is at `/tmp/hermes-verify-marine-procurement.py` 
(run once, since deleted). To re-verify after changes:

```bash
cd ~/.hermes/skills/maritime/marine-procurement-agent/scripts
python3 vendor_search.py --part "Jabsco 18670-0001" --brand "Jabsco" --description "impeller"
python3 vendor_page_extractor.py  # tests extraction scripts and parsing
python3 email_formatter.py --results <json> --part-number "Jabsco 18670-0001" --description "Impeller" --brand "Jabsco"
```

## Telegram Loading Pitfall

Local skills (source: local) do NOT appear in the Telegram slash-command menu
due to Telegram's 100-command Bot API limit. Built-in skills fill all slots.
The skill IS registered in `get_skill_commands()` and the runtime dispatcher
handles `/skill marine-procurement-agent` correctly — the user just has to
type the full command manually without autocomplete. This is not a bug, it's
a slot-cap behavior.

To verify the skill is registered:
```bash
cd /usr/local/lib/hermes-agent
python3 -c "from agent.skill_commands import get_skill_commands; print([k for k in get_skill_commands() if 'marine' in k])"
# Should show: ['/marine-procurement-agent']
```
