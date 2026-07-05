---
name: marine-procurement-agent
description: "Marine spare parts and consumables procurement agent — multimodal Telegram input (image/voice/screenshot), vision-based part identification, automated vendor search with GTA/Ontario near-sourcing priority, generates comparison table and dark-theme HTML report."
version: 1.1.0
platforms: [linux]
category: maritime
---

# Marine Procurement Agent

Triggered by Telegram messages (image, voice, screenshot, or text part description).
Identifies the part, searches known marine vendors, returns a tiered comparison table
and a detailed HTML report.

## When This Skill Loads

This skill is designed to be loaded explicitly by a cron job or a dedicated gateway
session that handles marine procurement requests. It should NOT load in every session.

### Trigger phrases (any of these in Telegram message should load this skill):
- "find part", "source", "procurement", "buy", "price check", "where to buy"
- Any image/photo sent to the Telegram bot (assumed to be a part photo)
- Any screenshot or voice note mentioning marine parts

## Vendor Registry (Tiered by Near-Sourcing Priority)

### Tier 1 — GTA / Southern Ontario (highest priority)
| Vendor | City | Website | Notes |
|--------|------|---------|-------|
| Holland Marine Products | Toronto, ON | hollandmarine.com | Largest Ontario inventory, chandlery |
| Brewers' Marine Supply | Hamilton, ON | brewersmarine.com | Hamilton port, commercial + recreational |
| C.C. Marine Distributors | Canada-wide | ccmarine.ca | Wholesale distributor, marine + industrial |
| Eastmar Marine | Toronto, ON | eastmar.ca | Toronto's marine parts centre |
| Marine Outfitters | Ontario, Canada | marineoutfitters.ca | Established 1999, broad inventory |
| Fogh Boat Supplies | Ontario, Canada | foghboatsupplies.com | Ontario marine store |
| OBR Oil & Marine | Canada | obroilandmarine.com | Engine parts, impellers, lubes |

### Tier 2 — Canada (broader)
| Vendor | City | Website | Notes |
|--------|------|---------|-------|
| Steveston Marine | Vancouver, BC | stevestonmarine.com | Since 1941, 10,000+ items |
| Western Marine / Transat Marine | Vancouver, BC | westernmarine.com | Wholesale distributor |
| Marine Parts Supply | Canada | marinepartssupply.com | Evinrude distributor |
| The Chandlery | Ottawa, ON | thechandleryonline.com | Since 1982 |
| Trotac Marine | Victoria, BC | trotac.ca | Pumps, impellers, hose |
| Kimpex Canada | Drummondville, QC | kimpex.com | Marine impellers, engine parts |

### Tier 3 — US / International (fallback)
| Vendor | City | Website | Notes |
|--------|------|---------|-------|
| Defender Marine | Waterford, CT | defender.com | Largest US online marine retailer |
| Hamilton Marine | Searsport, ME | hamiltonmarine.com | Traditional marine hardware |
| Fisheries Supply | Seattle, WA | fisheriessupply.com | Major West Coast supplier |
| Marine Engine Depot | US | marineenginedepot.com | Engine parts specialist |
| MDI (Marine Diesel Inc.) | US | marinedieselinc.com | Diesel engine parts |
| ShipServ | Global | shipserv.com | Maritime e-procurement marketplace |

## Workflow

### Phase 1: Receive Input

The user sends a message via Telegram:
- **Image/Screenshot**: Photo of a part, manual page, computer screen showing part number
- **Voice note**: "Find me a Jabsco impeller for a 4.3L Mercruiser"
- **Text**: Part number, description, or request like "need Racor S3227 fuel filter"

### Phase 2: Identify the Part

1. If image: Use `vision_analyze` to read the part — extract:
   - Part number / SKU (if visible)
   - Part name / description
   - Brand / manufacturer
   - Any specs visible (size, model, etc.)
   - Context clues (what equipment it belongs to)

2. If voice: Hermes STT auto-transcribes. Extract the same info from the text.

3. If text: Parse the request for part number, name, brand, specs.

4. If ambiguous: Search the web for the part to confirm identity before scraping.

### Phase 3: Search Vendors

Run parallel searches for each vendor tier:

```
web_search("site:<vendor-domain> <part-number> <part-name>")
web_search("<part-number> marine supply Canada price")
web_search("<part-name> <brand> marine distributor Ontario")
```

For each vendor, attempt to extract:
- Price (CAD preferred, USD noted)
- Availability (in stock / special order / backorder)
- Lead time (same day / 1-3 days / 1-2 weeks)
- Shipping info (free over $X, flat rate, etc.)

### Phase 4: Build Comparison Table

Format as a table with columns:
| Tier | Vendor | Part # | Price | Stock | Lead Time | Location | Notes |

Tiered rows sorted: Tier 1 (GTA) → Tier 2 (Canada) → Tier 3 (US/Intl)

### Phase 5: Generate HTML Report

Use the dark theme template (see below) and publish to here.now.
Include:
- Part identification (with image if provided)
- Comparison table sorted by tier
- Near-sourcing score (1-10, based on distance to Hamilton/Toronto)
- Total cost estimate (price + estimated shipping + duty if applicable)
- Source links for each vendor
- Timestamp and disclaimer

### Phase 6: Deliver

1. Telegram inline summary: Quick table with top 3-5 results, tier badges
2. here.now URL for the full detailed report

## HTML Report Template

Dark theme: #0D1117 background, #161B22 cards, #8B5CFC purple accent.
640px max width, inline CSS (Gmail-safe).

Sections:
1. Header: "Marine Procurement Report" + timestamp + part identification
2. Quick Summary card: best price, fastest lead time, best near-source
3. Comparison Table: all vendors with tier color coding
4. Near-Sourcing Score visualization (gauges for each vendor)
5. Source links
6. Footer: "Generated by Marine Procurement Agent · Rubin Varghese"

## Near-Sourcing Score

Score 1-10 based on:
- Location proximity to Hamilton/Toronto (Tier 1 = 8-10, Tier 2 = 4-7, Tier 3 = 1-3)
- CAD pricing (bonus points)
- Fast lead time (bonus points)
- In-stock availability (bonus points)

Color code: Green (8-10), Yellow (4-7), Red (1-3)

## Implementation Notes

### Web Search Strategy

Marine vendor sites don't typically have public APIs. The agent uses:
1. **web_search** — Google-indexed product pages from vendor sites
2. **web_extract** — Try extracting pricing from product pages (Firecrawl is broken, falls back)
3. **browser_navigate** — For JS-heavy catalog sites that web_extract can't handle
4. **Google Shopping** — `web_search("<part> price site:google.com/shopping")` as fallback

### Part Number Normalization

Marine parts often have multiple numbering systems:
- OEM part number (e.g., Mercruiser 47-862232A2)
- Aftermarket equivalent (e.g., Sierra 18-3347)
- Generic description (e.g., "Jabsco impeller 18670-0001")

Search all variants. Cross-reference with aftermarket catalogs (Sierra, GLM, Mallory).

### Currency Handling

- Tier 1 & 2 vendors: prices in CAD
- Tier 3 vendors: prices in USD → note conversion
- Use current CAD/USD rate (fetch from yfinance or web_search)
- Estimate duties for US imports (typically 5-13% for marine parts)

### Image Handling

Telegram sends images to Hermes which triggers vision_analyze.
If the image is a screenshot of a computer/tablet showing a part page:
- Extract the visible part number
- Note the source website if visible
- Use that as a direct vendor source

### Voice Notes

Telegram voice messages are auto-transcribed by Hermes STT.
The transcription becomes the search query.
If transcription is unclear, ask clarifying questions.

## Pitfalls

1. **Firecrawl is broken** — Don't rely on web_extract for vendor sites. Use browser_navigate + browser_snapshot for detailed catalog pages.
2. **Many marine vendors use old-school websites** — HTML tables, no APIs, sometimes no search. Use Google site search as primary.
3. **Prices fluctuate** — Always note "price as of [date]" in reports.
4. **Stock is unreliable** — Many sites show "in stock" but don't update in real time. Note "per website" as caveat.
5. **Cross-border shipping** — US vendors may not ship to Canada, or shipping may exceed part cost. Always flag.
6. **Part compatibility** — Marine engines have specific model years and serial number ranges. Flag if uncertain.
7. **Redactor issues** — When reading here.now credentials or API keys, use the runtime read pattern (file read, not inline env vars).
8. **Skill must be explicitly loaded on Telegram** — The gateway does NOT auto-load skills based on message content. The user MUST type `/skill marine-procurement-agent` in Telegram before sending a procurement request. **Important:** This command will NOT appear in the Telegram slash-command autocomplete menu because the 100-slot Bot API cap is filled by built-in skills. The user has to type the full command name manually. The runtime dispatcher handles it correctly — it's just invisible in the menu. Verify the skill is registered: `python3 -c "from agent.skill_commands import get_skill_commands; print([k for k in get_skill_commands() if 'marine' in k])"` should show `['/marine-procurement-agent']`. Without loading, the bot responds with "I searched my knowledge vault, skills, cron jobs and don't have a marine purchasing agent." This is the #1 onboarding failure point.
9. **Data shape mismatch: vendor vs name keys** — `vendor_search.py` outputs `{"vendor": "...", "location": "City, PROV, Country"}` but `render_vendor_row()` expects `{"name": "...", "city": "...", "province": "..."}`. Key normalization code exists in both `vendor_search.py` (HTML output branch) and `build_report.py` (after JSON load). If adding a new consumer of the vendor search output, you must normalize keys first. See `references/build-pipeline-notes.md` for the exact normalization snippet.
10. **Web extraction APIs are overkill at this volume** — At 5-10 searches/day (~35-70 page extractions), paid APIs like ScrapingBee ($0.025/req) or Firecrawl ($19/mo) cost more than they're worth. The VPS already runs a Chrome headless instance 24/7. Browser-based extraction with `browser_navigate` + `browser_console` costs $0 and handles JS-rendered pages that block API-based extractors. See `references/web-crawler-analysis.md` for the first-principles breakdown.

## Required Tools

This skill requires these Hermes toolsets to be enabled:
- `web` — web_search + web_extract
- `browser` — browser_navigate, browser_snapshot, browser_click
- `vision` — vision_analyze for part identification from images
- `terminal` — for yfinance currency rates, file operations
- `file` — write_file for HTML report generation

## Execution Workflow (Step by Step)

When a marine procurement request arrives via Telegram:

### Step 0: Load this skill

Run `/skill marine-procurement-agent` or auto-load based on trigger phrases.

### Step 1: Identify the Part

```
If IMAGE received:
  vision_analyze(image_url=<image>, question="Identify the marine part in this image. Extract: part number, brand/manufacturer, part name/description, any visible specs. If it's a screenshot from a website, note the source URL.")

If VOICE received:
  Transcription is auto-provided by STT. Extract part details from text.

If TEXT received:
  Parse for: part number (alphanumeric patterns like '47-862232A2'), brand name, description.
```

### Step 2: Run Vendor Search

```python
# In execute_code or terminal:
cd ~/.hermes/skills/maritime/marine-procurement-agent/scripts
python3 vendor_search.py --part "<part_number>" --brand "<brand>" --description "<description>"
```

This outputs JSON with search instructions for all 19 vendors across 3 tiers.
Save to `/tmp/marine-results-<timestamp>.json`

### Step 3: Search Vendors (Parallel)

For each tier, run web_search calls for vendors where you need pricing:

```
# Tier 1 examples:
web_search("site:hollandmarine.com <part_number>")
web_search("site:brewersmarine.com <part_number>")
web_search("site:marineoutfitters.ca <part_number> <description>")

# Broader search:
web_search("<part_number> <brand> Canada price marine")
web_search("<part_number> <brand> Ontario distributor purchase")
```

For each vendor with a result, extract:
- Price (CAD/USD)
- Stock status (in stock / special order / backorder)
- Lead time estimate
- Source URL

### Step 4: Update Results JSON

Add the found data to each vendor entry in the JSON:
```python
v["price"] = "CAD $45.99"
v["stock"] = "In Stock"
v["lead_time"] = {"label": "1-3 days", "class": "lead-fast"}
v["source_url"] = "https://hollandmarine.com/product/..."
```

### Step 5: Build HTML Report

```bash
cd ~/.hermes/skills/maritime/marine-procurement-agent/scripts
python3 build_report.py \
  --results /tmp/marine-results-<timestamp>.json \
  --part-number "<part_number>" \
  --description "<description>" \
  --brand "<brand>" \
  --output /tmp/marine-report-<timestamp>.html
```

### Step 6: Publish to here.now

Use the here.now publish pattern (read key from file, NOT inline):
```python
# Read here.now key and publish
# See web-hosting-and-publishing skill references/herenow-workflow.md
```

### Step 7: Format Email-Ready Output + Respond on Telegram

**Generate email-ready table:**
```bash
cd ~/.hermes/skills/maritime/marine-procurement-agent/scripts
python3 email_formatter.py \
  --results /tmp/marine-results-<timestamp>.json \
  --part-number "<part_number>" \
  --description "<description>" \
  --brand "<brand>"
```

**Send to Telegram:** Post the full email_formatter output as the Telegram reply.
The user copies it and pastes into Outlook on their office laptop.

**Inline summary (in Telegram message, BEFORE the full table):**

```
🛥️ *Marine Procurement Report*
*Part:* <part_number> (<brand> <description>)

🏆 Best Near-Source: <vendor> (<score>/10) — <city>, <province>
💰 Best Price: <price> at <vendor> (if found)
⏱️ Fastest: <lead_time> at <vendor> (if found)

📋 *Email-ready table below — copy and paste into Outlook* ↓
```

Then post the full email_formatter output.

**Also publish HTML report to here.now** (for permanent record and detailed view),
and include the URL at the bottom of the Telegram message.

### Step 8: Commit and Push Changes (if skill was modified)

If the agent made ANY changes to the skill during this session (added a vendor,
fixed a selector, updated the registry, improved the template), commit and push
so the changes survive and sync to the laptop:

```bash
cd ~/.hermes/skills/maritime/marine-procurement-agent
git add -A .
git commit -m "Update from Telegram session: <brief description of what changed>"
git push origin main
```

This is critical. Without this push:
- VPS changes are overwritten by the next cron pull (every 2 hours)
- The laptop never sees the improvements
- GitHub stays stale while the VPS has the real working version

If nothing was modified, skip this step (git will report "nothing to commit").

What NOT to do:
- Do NOT ask the user clarifying questions unless the part is genuinely unidentifiable
- Do NOT fabricate prices — only show what was found via actual web_search results
- Do NOT skip the HTML report — always publish and link
- Do NOT skip Tier 1 (GTA) vendors — they are the priority
- Do NOT forget to `git push` after modifying the skill — changes will be lost

### Quick Response Format (for simple requests)

If the user just says "find me a Jabsco 18670-0001 impeller":
1. Load skill
2. Run vendor_search.py for instructions
3. web_search the top 5 vendors (2 Tier 1, 2 Tier 2, 1 Tier 3)
4. Reply with inline table + note that full HTML report is being generated
5. Then build and publish the HTML report
6. Edit reply or send follow-up with the report URL

## File Layout

```
~/.hermes/skills/maritime/marine-procurement-agent/
├── SKILL.md                          (this file)
├── scripts/
│   ├── marine_report_template.html   (HTML report template)
│   ├── vendor_search.py             (programmatic vendor search)
│   ├── build_report.py             (HTML report builder)
│   ├── vendor_page_extractor.py    (browser-based page extraction — price, stock)
│   └── email_formatter.py          (plain-text email-ready output for Outlook)
└── references/
    └── vendor-registry.json          (full vendor database with URLs)
```

## Email-Ready Output (Outlook Copy-Paste)

The `email_formatter.py` script generates a plain-text table designed for:
1. Telegram delivers the formatted text
2. You Ctrl+A → Ctrl+C on your phone
3. Paste into Outlook on your office laptop
4. Send to your procurement team / requestor

The format uses:
- Fixed-width ASCII columns (no HTML, no markdown)
- Tier badges (T1*, T2, T3)
- Unicode block gauges for near-sourcing scores (█░)
- HELD/AWAITING/QUOTED statuses where pricing not yet scraped

### Email workflow:
```
Personal phone (Telegram) → VPS agent → Telegram reply with email-ready table
                                              ↓
                              You copy from Telegram on phone
                                              ↓
                              Paste into Outlook on office laptop
                                              ↓
                              Forward to procurement team
```

No environment crossover. The VPS never touches your office network/email.

## Browser-Based Extraction (vendor_page_extractor.py)

Instead of relying on Firecrawl (broken) or Jina Reader (blocks marine sites),
the agent uses Hermes browser tools directly:

```
1. browser_navigate(url="<vendor_product_page>")
2. browser_console(expression=<extraction_script>)
   → Returns JSON: {"price": "$45.99", "stock": "In Stock", "title": "Jabsco 18670-0001"}
3. Parse with parse_price() / parse_stock()
```

The extraction script is a self-contained JavaScript IIFE that tries multiple
CSS selectors per vendor. Known vendor selectors are in VENDOR_EXTRACTORS dict.
Unknown vendors fall back to GENERIC_SELECTORS.

This costs $0/month — the Chrome instance is already running on the VPS.

## Git Sync (Laptop ↔ VPS ↔ GitHub)

The skill is version-controlled at:
`https://github.com/rubinagentagi-tech/marine-procurement-agent`

Both laptop (`~/.hermes/skills/maritime/marine-procurement-agent/`) and VPS
(same path) are git clones tracking the same origin. GitHub is the source of
truth.

### Sync flow

```
Laptop changes → git push → GitHub
                                ↓
                    VPS pulls every 2h (cron job e234275c8965)

VPS changes (via Telegram) → git add/commit/push → GitHub
                                                      ↓
                                    Laptop pulls manually next session
```

### If the agent on VPS modifies the skill during a Telegram session

The agent MUST commit and push changes so they survive:

```bash
cd ~/.hermes/skills/maritime/marine-procurement-agent
git add -A .
git commit -m "Update from Telegram session: <brief description>"
git push origin main
```

This is the only way VPS-initiated changes reach GitHub and later the laptop.

### Cron auto-sync on VPS

Job `e234275c8965` runs `sync-skill-marine.sh` every 2 hours:
- Pulls latest from GitHub (silent when already synced)
- If the repo dir is missing (VPS reset), clones fresh from GitHub
- Delivery: `local` (no Telegram spam — only logs errors)

### Manual sync

Run on either machine:
```bash
bash ~/.hermes/skills/maritime/sync.sh
```

### Verifying sync state

Check both sides are at the same commit:
```bash
# Laptop
cd ~/.hermes/skills/maritime/marine-procurement-agent && git log --oneline -1
# VPS
ssh contabo-vps 'cd ~/.hermes/skills/maritime/marine-procurement-agent && git log --oneline -1'
```

They should show identical commit hashes. If not, run the sync script on the
stale side.

### Pitfall: editing on one side without pushing

If you edit the skill on the VPS via Telegram and the agent doesn't `git push`,
those changes are lost on the next `git pull` (the VPS cron job will overwrite
local changes with the GitHub version). Always push after editing.

## Session Management

Procurement sessions run LONG — ~164K tokens in 22 hours is typical because the
agent does web_search, browser navigation, HTML building, and here.now publishing
all in one session.

**After each procurement task completes, end the session:**

1. The skill, vendor registry, and all scripts persist on disk at
   `~/.hermes/skills/maritime/marine-procurement-agent/` — nothing is lost
2. Start a fresh session for the next request with `/new` in Telegram
3. Reload the skill with `/skill marine-procurement-agent`

**Or use compression mid-session:**

```
/compress
```

This trims old messages while keeping recent context intact. Useful if you're
doing back-to-back procurement searches and don't want to reload the skill
between each one.

**Why this matters:**

- Cost: DeepSeek charges per token. 164K tokens per turn × multiple turns =
  real money. A fresh session cuts input tokens by 90%+.
- Quality: LLMs degrade with very long contexts — early instructions get
  truncated, responses get sloppier.
- Speed: More tokens = more processing time = slower Telegram replies.

**Rule of thumb:** If you've done 3+ procurement searches in one session, or
the session is older than 6 hours, `/new` and `/skill marine-procurement-agent`.
The reload takes 2 seconds and saves you minutes of processing time per turn.
