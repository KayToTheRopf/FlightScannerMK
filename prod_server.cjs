const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT_DIR = __dirname;
const ACTIVE_DEALS_PATH = path.join(ROOT_DIR, "data", "active_deals.json");
const DEAL_EXCLUSIONS_PATH = path.join(ROOT_DIR, "data", "deal_exclusions.json");
const BLACKLIST_PATH = path.join(ROOT_DIR, "config", "blacklist.json");
const SITE_INDEX_PATH = path.join(ROOT_DIR, "site", "index.html");

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function safeLink(url) {
  try {
    const parsed = new URL(String(url || ""));
    return parsed.protocol === "https:" && parsed.host ? String(url) : "";
  } catch {
    return "";
  }
}

function renderButton(label, url, styleClass) {
  const safe = safeLink(url);
  if (!safe) {
    return `<span class="button button-disabled">${escapeHtml(label)}</span>`;
  }
  return `<a class="button ${styleClass}" href="${escapeHtml(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function loadJson(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function getFilteredDeals() {
  const raw = loadJson(ACTIVE_DEALS_PATH, { deals: [] });
  const deals = Array.isArray(raw.deals) ? raw.deals : [];
  const exRaw = loadJson(DEAL_EXCLUSIONS_PATH, { excluded_deals: [] });
  const excludedSet = new Set(Array.isArray(exRaw.excluded_deals) ? exRaw.excluded_deals : []);
  const bl = loadJson(BLACKLIST_PATH, {
    excluded_airports: [],
    excluded_cities: [],
    excluded_countries: [],
  });
  const airports = new Set((bl.excluded_airports || []).map((a) => String(a).trim().toUpperCase()));
  const cities = new Set((bl.excluded_cities || []).map((c) => String(c).trim().toLowerCase()));
  const countries = new Set((bl.excluded_countries || []).map((c) => String(c).trim().toLowerCase()));

  const filtered = deals.filter((d) => {
    const offer = d && d.offer ? d.offer : {};
    const sig = `${String(offer.origin || "").toUpperCase()}-${String(offer.destination || "").toUpperCase()}:${offer.outbound_date}:${offer.inbound_date}`;
    if (excludedSet.has(sig)) return false;
    if (airports.has(String(offer.destination || "").trim().toUpperCase())) return false;
    if (cities.has(String(offer.destination_name || "").trim().toLowerCase())) return false;
    if (countries.has(String(offer.destination_country || "").trim().toLowerCase())) return false;
    return true;
  });

  filtered.sort((a, b) => {
    const scoreDiff = Number(b.deal_score || 0) - Number(a.deal_score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return Number(a.offer?.price_eur || 0) - Number(b.offer?.price_eur || 0);
  });

  return filtered;
}

function renderDealsPage(deals) {
  let timestamp = new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC";
  try {
    if (fs.existsSync(ACTIVE_DEALS_PATH)) {
      const mtime = fs.statSync(ACTIVE_DEALS_PATH).mtime;
      const pad = (n) => String(n).padStart(2, "0");
      timestamp = `${pad(mtime.getUTCDate())}.${pad(mtime.getUTCMonth() + 1)}.${mtime.getUTCFullYear()} ${pad(mtime.getUTCHours())}:${pad(mtime.getUTCMinutes())} UTC`;
    }
  } catch {
    // ignore stat error
  }

  const cards = deals.map((deal) => {
    const offer = deal.offer || {};
    const badge = offer.is_wishlist ? "Wunschziel" : "Explore-Deal";
    const stops = Number(offer.stops || 0) === 0 ? "Direktflug" : `${offer.stops} Stopp(s)`;
    const outDate = String(offer.outbound_date || "");
    const inDate = String(offer.inbound_date || "");
    let stayDays = 0;
    try {
      stayDays = Math.max(0, Math.round((new Date(inDate) - new Date(outDate)) / 86400000));
    } catch {
      stayDays = 0;
    }
    const price = Number(offer.price_eur || 0).toFixed(2);
    return `
            <article class="deal-card">
              <div class="deal-heading">
                <span class="badge">${escapeHtml(badge)}</span>
                <span class="price">${price} €</span>
              </div>
              <h2>${escapeHtml(offer.origin_name)} (${escapeHtml(offer.origin)}) → ${escapeHtml(offer.destination_name)} (${escapeHtml(offer.destination)})</h2>
              <p class="country">${escapeHtml(offer.destination_country)}</p>
              <dl>
                <div><dt>Reisezeitraum</dt><dd>${escapeHtml(outDate)} bis ${escapeHtml(inDate)} (${stayDays} Tage)</dd></div>
                <div><dt>Airline</dt><dd>${escapeHtml(offer.airline)} · ${escapeHtml(stops)} · ${escapeHtml(offer.provider)}</dd></div>
                <div><dt>Ersparnis</dt><dd>${escapeHtml(deal.reason)}</dd></div>
              </dl>
              <div class="actions">
                ${renderButton("✈ Flug ansehen & buchen", offer.booking_url, "button-book")}
                ${renderButton("🚫 Diesen Deal ausschließen", deal.exclude_url, "button-exclude")}
              </div>
            </article>`;
  });

  const content =
    cards.length > 0
      ? cards.join("\n")
      : '<p class="empty">Aktuell sind keine aktiven Schnäppchen gespeichert.</p>';

  let summary = `${deals.length} Schnäppchen gefunden`;
  if (deals.length > 0) {
    const bestPrice = Math.min(...deals.map((d) => Number(d.offer?.price_eur || 0)));
    summary += ` · günstigster Flug ab ${bestPrice.toFixed(2)} €`;
  }

  return `<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Aktuelle Flug-Schnäppchen ab München und Memmingen.">
  <title>Flug-Schnäppchen-Radar</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; color: #172033; background: #f3f6fb; }
    body { margin: 0; }
    header { padding: 2rem max(1rem, calc((100% - 960px) / 2)); color: white; background: #172b4d; }
    header h1 { margin: 0 0 .5rem; }
    header p { margin: .25rem 0; }
    main { max-width: 960px; margin: 1.5rem auto; padding: 0 1rem; }
    .deal-list { display: grid; gap: 1rem; }
    .deal-card { padding: 1.25rem; background: white; border: 1px solid #dce3ee; border-radius: 12px; box-shadow: 0 3px 12px #172b4d0b; }
    .deal-heading { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
    .badge { padding: .25rem .6rem; border-radius: 999px; background: #e8f1ff; color: #174ea6; font-size: .85rem; }
    .price { color: #16803c; font-size: 1.4rem; font-weight: 700; white-space: nowrap; }
    h2 { margin: 1rem 0 0; font-size: 1.25rem; }
    .country { margin: .2rem 0 1rem; color: #586579; }
    dl { display: grid; gap: .6rem; margin: 0 0 1rem; }
    dl div { display: grid; grid-template-columns: 130px 1fr; gap: .5rem; }
    dt { color: #586579; } dd { margin: 0; }
    .actions { display: flex; flex-wrap: wrap; gap: .6rem; }
    .button { display: inline-block; padding: .65rem .9rem; border-radius: 7px; color: white; text-decoration: none; font-weight: 650; }
    .button-book { background: #1769aa; } .button-exclude { background: #b42318; }
    .button-disabled { background: #697586; }
    .empty { padding: 2rem; background: white; border-radius: 12px; text-align: center; }
    footer { max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #586579; font-size: .85rem; }
    @media (max-width: 560px) { dl div { grid-template-columns: 1fr; gap: .15rem; } }
  </style>
</head>
<body>
  <header>
    <h1>✈ Flug-Schnäppchen-Radar</h1>
    <p>${escapeHtml(summary)}</p>
    <p>Letzte Aktualisierung: ${escapeHtml(timestamp)}</p>
  </header>
  <main><section class="deal-list" aria-label="Gefundene Flugangebote">${content}</section></main>
  <footer>Preise und Verfügbarkeiten können sich jederzeit ändern. Bitte beim Anbieter prüfen.</footer>
</body>
</html>`;
}

const server = http.createServer((req, res) => {
  const parsedUrl = new URL(req.url || "/", "http://localhost");
  const pathname = parsedUrl.pathname;
  const headOnly = req.method === "HEAD";

  if (pathname === "/api/health") {
    const body = Buffer.from(JSON.stringify({ status: "ok" }), "utf8");
    res.writeHead(200, {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": body.length,
      "Cache-Control": "no-store",
    });
    return res.end(headOnly ? undefined : body);
  }

  if (pathname === "/api/deals") {
    const deals = getFilteredDeals();
    const blacklist = loadJson(BLACKLIST_PATH, {
      excluded_airports: [],
      excluded_cities: [],
      excluded_countries: [],
    });
    const body = Buffer.from(
      JSON.stringify({ count: deals.length, deals, blacklist }, null, 2),
      "utf8"
    );
    res.writeHead(200, {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": body.length,
      "Cache-Control": "no-store",
    });
    return res.end(headOnly ? undefined : body);
  }

  if (pathname === "/" || pathname === "/index.html") {
    let htmlText = "";
    try {
      const deals = getFilteredDeals();
      htmlText = renderDealsPage(deals);
    } catch {
      if (fs.existsSync(SITE_INDEX_PATH)) {
        htmlText = fs.readFileSync(SITE_INDEX_PATH, "utf8");
      } else {
        htmlText = "<!doctype html><html><body><h1>Flug-Schnäppchen-Radar</h1></body></html>";
      }
    }
    const body = Buffer.from(htmlText, "utf8");
    res.writeHead(200, {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Length": body.length,
      "Cache-Control": "no-store",
    });
    return res.end(headOnly ? undefined : body);
  }

  const notFound = Buffer.from(JSON.stringify({ error: "Not found" }), "utf8");
  res.writeHead(404, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": notFound.length,
  });
  res.end(headOnly ? undefined : notFound);
});

const port = Number(process.env.PORT || 3000);
const host = process.env.HOST || "0.0.0.0";
server.listen(port, host, () => {
  console.log(`Flug-Schnäppchen-Radar Server listening on http://${host}:${port}`);
});
