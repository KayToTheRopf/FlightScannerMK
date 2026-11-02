# Trust-Verified Multi-Market Deal Radar (API & Official RSS Only)

Transform the existing flight bargain tracker into a **zero-scraping, block-proof Multi-Market Deal Radar** for **Tech & Electronics**, **Video Games & Software**, and **Collectibles (LEGO & Watches)**—powered strictly by **official RSS feeds and public JSON APIs** so it never gets IP-blocked on GitHub Actions, filters out marketplace scams through built-in trust signals, and requires zero scraper maintenance.

## User Review & Critical Decisions

> [!IMPORTANT]
> **Why We Dropped HTML Scraping (Kleinanzeigen / Geizhals HTML) in Favor of Official Feeds & APIs**:
> 1. **No IP Blocking on GitHub Actions**: GitHub Actions runs on Microsoft Azure datacenter IPs. Sites like Kleinanzeigen.de and Geizhals.de block or CAPTCHA datacenter IPs via Cloudflare/Akamai. Official RSS feeds (`mydealz.de/rss/...`) and official JSON APIs (`CheapShark`, `Steam Store API`, `eBay Browse API`) are explicitly built for automated requests and **never block GitHub Actions**.
> 2. **High Trust (No Classified Scams)**: Unvetted classified listings (Kleinanzeigen) for cheap GPUs or LEGO sets are heavily polluted by scams (*Dreiecksbetrug*), broken items, and empty-box traps—and real deals sell within 2 minutes, making a 2x/day cron job ineffective. By contrast, **MyDealz** has human moderation + community temperature voting (`°`), **Steam/CheapShark** only list official authorized stores, and the **official eBay API** lets us filter strictly for `>= 98%` seller feedback and working condition codes.
> 3. **Zero Maintenance Overhead**: HTML scrapers break whenever CSS classes change. Standard XML/RSS and REST JSON APIs run untouched for years.

- **Confirmed Architecture — 3 Block-Proof Providers (Mirroring Your Original 3 Flight Providers)**:
  1. **MyDealz Official RSS Provider (No API Key Needed)**: Fetches `/rss/hot` and category/keyword RSS feeds for **Electronics**, **Gaming**, **LEGO**, and **Watches**. Uses community temperature (`>= 100°`) as a built-in trust filter and extracts the community comparison price (*PVG / nextBestPrice*).
  2. **Steam DE & CheapShark Official JSON API Provider (No API Key Needed)**: Fetches live `EUR` digital game deals across Steam, GOG, Epic, and Humble, filtering by Steam review score (`>= 80%`) and comparing against historical all-time lows.
  3. **eBay Official Browse API Provider (Optional Free Token, Like `TRAVELPAYOUTS_TOKEN`)**: Queries `api.ebay.com` for your specific Wishlist items with strict API-level trust filters (`Buy-It-Now` only, seller positive feedback `>= 98%`, feedback count `>= 50`, and excluding condition code `7000` "For parts/defective").

---

## 1. Overview & Core Concept

- **What It Does**: Runs 2x/day in GitHub Actions (and on-demand via the interactive web dashboard) to query **MyDealz RSS**, **Steam / CheapShark APIs**, and the **official eBay Browse API**. It evaluates every offer against your custom wishlist targets, PVG reference prices, and rolling historical price baselines (`price_history.json`), then updates the interactive Deal Radar dashboard and dispatches Discord / GitHub Issue / Email alerts.
- **Target Audience / Persona**: Deal hunters, PC builders, gamers, and LEGO/watch collectors who want a "set-and-forget" radar that only alerts on verified, trustworthy bargains.
- **Key Value**: 100% reliable execution on GitHub Actions with zero proxy/CAPTCHA headaches, zero scraper maintenance, and multi-layered scam/junk protection.

---

## 2. User Experience & Visual Design

- **Key User Flows**:
  1. **Deal Radar Feed & Filtering**: Open the dashboard to view verified bargains ranked by Deal Score. Filter instantaneously by vertical (`All`, `Tech & Hardware`, `Games`, `Collectibles`, `Verified Refurb / eBay`), source platform (`MyDealz`, `Steam / CheapShark`, `eBay Official`), discovery mode (`Wishlist` vs. `Category Explore`), or search query.
  2. **Trust & Price Spread Inspection**: Each deal card/row displays the current total price (including shipping), target threshold, PVG / rolling historical average, percentage savings, and explicit **Trust Signals** (MyDealz temperature in `°`, Steam review score `%`, or eBay seller rating `%`) in aligned tabular numerals.
  3. **1-Click Exclusion & Blacklist Tuning**: Exclude an individual deal (`Ignore Deal`), block a noisy keyword (e.g., `"defekt"`, `"OVP"`, `"Schutzfolie"`), or mute an unwanted merchant/brand directly from the dashboard or via 1-click GitHub Issue links.
  4. **Wishlist & Trust Rule Management**: Add or edit watched items (e.g., `"RTX 4070 Super"` max `520 €`, `"LEGO 10316 Bruchtal"` max `360 €`, `"Baldur's Gate 3"` max `39 €`, `"Seiko 5 Sports"` max `190 €`) and configure minimum MyDealz temperature (`°`) or minimum discount thresholds directly from the UI.
  5. **On-Demand Scan & Static Export**: Trigger a live provider scan from the dashboard header to fetch fresh offers from the official RSS/JSON APIs, update `price_history.json`, and regenerate the static GitHub Pages snapshot.

- **Visual Identity & Theme**:
  - *Aesthetic Direction*: High-precision analytical market terminal meets clean editorial deal curation—structured, scannable, and free of promotional clutter.
  - *Color Palette & Mood* (60-30-10 distribution):
    - **60% Dominant Neutral Canvas**: Crisp cool alabaster (`#F8FAFC`) in light mode / deep slate (`#0F172A`) for header and structural framing.
    - **30% Structural Surfaces**: Pure white (`#FFFFFF`) single-elevation surfaces with `1px solid #E2E8F0` hairline borders and muted slate metadata (`#64748B`).
    - **10% Accent Budget**: Emerald (`#16A34A`) for verified price drops, warm amber (`#D97706`) for high community heat (`°`), royal blue (`#1D4ED8`) for primary actions, and crimson (`#DC2626`) reserved strictly for exclusion actions.
  - *Typography & Hierarchy*:
    - **Display / Headings**: `Plus Jakarta Sans` (600/700 weight, `text-wrap: balance`) for crisp structural hierarchy.
    - **Body & Controls**: `DM Sans` (400/500 weight) for dense scannability across deal titles and filter controls.
    - **Prices, Discounts & Trust Metrics**: `JetBrains Mono` with `font-variant-numeric: tabular-nums` so prices, PVG reference prices, historical averages, and percentage savings align vertically.
  - *Component Styling & Layout*:
    - Full-width `1440px` desktop workspace with a strict 3-zone top bar (`Brand Wordmark` — `View Navigation Links` — `Run Live Scan CTA`), a full-width 4-metric KPI summary strip below the header, segmented interactive filter controls, and a single-elevation deal grid/table.
    - Static metadata (platform source, category name, merchant, community temperature / review score) rendered as clean unboxed text separated by `·` bullets (zero pill badges).
- **Interactive Feedback & Motion**:
  - Instant `<150ms` client-side filtering and sorting, inline toast confirmation when excluding a deal or adding a wishlist target, and clean skeleton states while an on-demand provider scan runs.

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: Zero HTML Scraping — Official RSS & REST JSON APIs Only**
  - *Chosen Approach*: Use **MyDealz RSS/Pepper XML feeds**, **CheapShark + Steam Store DE JSON APIs**, and the **official eBay Browse REST API** (optional free key).
  - *Why*: Eliminates IP blocking on GitHub Actions Azure runners, removes fragile DOM/HTML parsing maintenance, and runs in `< 5 seconds` per scheduled run using only standard HTTP requests and XML/JSON parsing.
  - *Alternatives Considered*: Scraping Kleinanzeigen.de or Geizhals.de HTML, which triggers Cloudflare/Akamai blocks on datacenter IPs and requires high ongoing selector maintenance.

- **Decision 2: Three-Layer Trust & Anti-Junk Verification**
  - *Chosen Approach*:
    1. **Community Heat Gate (MyDealz)**: Ignore cold or downvoted posts; require configurable minimum temperature (e.g., `>= 100°` for explore deals, `>= 20°` for wishlist matches).
    2. **Store & Review Gate (Games)**: Only query official authorized digital storefronts via CheapShark/Steam and require a minimum Steam review score for explore deals.
    3. **Seller & Condition Gate (eBay Official + Keyword Trap Filter)**: Require seller positive feedback `>= 98%`, exclude "For parts / defective" condition codes, and filter out accessory/box-trap keywords (`"nur OVP"`, `"Leerbox"`, `"Defekt"`, `"Hülle"`).
  - *Why*: Ensures every notification sent to Discord or GitHub Issues is a legitimate, buyable product rather than a scam or accessory listing.

- **Decision 3: Dual Reference Baseline (PVG / Store Retail + Rolling EMA Price History)**
  - *Chosen Approach*: Combine external reference prices (MyDealz `nextBestPrice` PVG or Steam `normalPrice`) with our own rolling exponential moving average in `data/price_history.json`.
  - *Why*: Protects against inflated MSRP strikethroughs while building a long-term price memory for every product key (`item_key`) your radar observes.

---

## 4. Technical Architecture & Data Strategy *(Technical Reference)*

### Architecture & Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              TRUST-VERIFIED MULTI-MARKET DEAL RADAR (NO SCRAPING)            │
└──────────────────────────────────────────────────────────────────────────────┘
       │                                                       │
       ▼ (Scheduled 2x/day or Manual)                          ▼ (Port 3000 HTTP)
┌─────────────────────────────────────┐         ┌──────────────────────────────┐
│   GitHub Actions / CLI Runner       │         │  Interactive Web Dashboard   │
│  ┌───────────────────────────────┐  │         │ ┌──────────────────────────┐ │
│  │ 1. MyDealz Official RSS/XML   │  │         │ │ 3-Zone Top Bar & Scan CTA│ │
│  │    (Hot + Category + Keyword) │  │         │ ├──────────────────────────┤ │
│  │ 2. Steam DE & CheapShark JSON │  │         │ │ 4-Metric KPI Strip       │ │
│  │ 3. eBay Official Browse API   │  │         │ ├──────────────────────────┤ │
│  └──────────────┬────────────────┘  │         │ │ Category / Platform /    │ │
│                 ▼                   │         │ │ Mode / Search Filter Bar │ │
│  ┌───────────────────────────────┐  │         │ ├──────────────────────────┤ │
│  │ DealAnalyzer & Trust Engine   │  │         │ │ Deal Feed & Trust/Spread │ │
│  │ • Community Heat / Rating Gate│  │         │ │ Cards (1-Click Exclude)  │ │
│  │ • PVG + Rolling EMA History   │  │         │ ├──────────────────────────┤ │
│  │ • Keyword/Accessory Trap Block│  │         │ │ Wishlist & Blacklist     │ │
│  │ • 7-Day Cooldown / 15% Drop   │  │         │ │ Management Panel         │ │
│  └──────────────┬────────────────┘  │         │ └────────────┬─────────────┘ │
└─────────────────┼───────────────────┘         └──────────────┼───────────────┘
                  │                                            │
                  ▼                                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     SHARED JSON & YAML STATE LAYER                           │
│  • Market Config & Wishlist Targets   • Rolling Item Price History           │
│  • Active Evaluated Deals Store       • Keyword, Merchant & Deal Exclusions  │
│  • Static HTML Snapshot Generator     • Discord / GitHub Issue / Mail Alerts │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data Model & State

1. **`MarketOffer` & `EvaluatedDeal`**:
   - Tracks `category` (`tech`, `games`, `collectibles`), `item_key` (normalized product slug/ID used as the historical key), `title`, `condition` (`new`, `refurbished`, `used`), `price_eur`, `shipping_eur`, `reference_price_eur` (PVG comparison price or normal store price), `merchant`, `provider` (`mydealz`, `cheapshark`, `steam`, `ebay_api`), `trust_signal` (e.g., `"342° MyDealz"`, `"94% Steam"`, `"99.6% Seller"`), `booking_url`, `is_wishlist`, `verified_live`, and `deal_signature`.
   - `EvaluatedDeal` computes `threshold_eur`, `historical_avg_eur`, `discount_vs_avg_percent`, `discount_vs_threshold_percent`, `deal_score`, `reason`, and `exclude_url`.
2. **Configuration & Persistence Stores**:
   - **Search & Category Config**: Defines per-category explore ceilings, minimum MyDealz temperature (`min_temperature_deg`), minimum discount percentages, and watched items (`wishlist_items` with code/slug, name, category, target max price in EUR, and search keywords).
   - **Blacklist & Trap Filter Store**: Stores `excluded_keywords` (e.g., `"defekt"`, `"leer"`, `"nur ovp"`), `excluded_merchants`, `excluded_categories`, and individual `excluded_signatures`.
   - **Rolling Price History Store**: Maps each normalized `item_key` to its exponentially weighted moving average (`avg_price_eur`), `min_price_eur`, `max_price_eur`, `observations`, and `notified_deals` cooldown timestamps.

### Interactive Component & State Mapping

- **Category, Platform & Mode Filter Bar**: Clicking a category (`All`, `Tech & Hardware`, `Video Games`, `Collectibles & LEGO`), source platform (`All`, `MyDealz`, `Steam / CheapShark`, `eBay Official`), discovery mode (`All`, `Wishlist`, `Explore`), or typing in the search box filters the displayed deals in real time and updates the 4-column KPI summary metrics.
- **1-Click Deal & Keyword Exclusion**: Clicking `Ignore Deal` on any card sends `POST /api/exclude-deal` to persist the signature in the exclusions store and immediately removes the card from the feed; submitting a keyword or merchant in the Blacklist panel sends `POST /api/exclude` to update `blacklist.json`.
- **Wishlist Manager**: Submitting the Wishlist form (`POST /api/wishlist`) adds or updates a watched item (item key, display name, category, target max price in EUR, and keywords) in `search_config.yaml` and immediately re-evaluates active offers.
- **Live Scan Trigger**: Clicking `Run Scan` in the top bar invokes `POST /api/scan`, executes the enabled official RSS/API providers (`mydealz`, `game_deals`, `ebay_official`) and `DealAnalyzer`, updates `active_deals.json` and `site/index.html`, and refreshes the dashboard feed.
