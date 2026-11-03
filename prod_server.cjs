const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");

const ROOT_DIR = __dirname;
const ACTIVE_DEALS_PATH = path.join(ROOT_DIR, "data", "active_deals.json");
const DEAL_EXCLUSIONS_PATH = path.join(ROOT_DIR, "data", "deal_exclusions.json");
const BLACKLIST_PATH = path.join(ROOT_DIR, "config", "blacklist.json");
const SEARCH_CONFIG_PATH = path.join(ROOT_DIR, "config", "search_config.yaml");
const SITE_INDEX_PATH = path.join(ROOT_DIR, "site", "index.html");

const IATA_CITY_MAP = {
  MUC: ["München", "Deutschland"],
  FMM: ["Memmingen", "Deutschland"],
  PMI: ["Palma de Mallorca", "Spanien"],
  BCN: ["Barcelona", "Spanien"],
  MAD: ["Madrid", "Spanien"],
  AGP: ["Málaga", "Spanien"],
  ALC: ["Alicante", "Spanien"],
  VLC: ["Valencia", "Spanien"],
  TFS: ["Teneriffa Süd", "Spanien"],
  LPA: ["Gran Canaria", "Spanien"],
  ACE: ["Lanzarote", "Spanien"],
  FUE: ["Fuerteventura", "Spanien"],
  IBZ: ["Ibiza", "Spanien"],
  SVQ: ["Sevilla", "Spanien"],
  LIS: ["Lissabon", "Portugal"],
  OPO: ["Porto", "Portugal"],
  FAO: ["Faro", "Portugal"],
  FNC: ["Madeira (Funchal)", "Portugal"],
  FCO: ["Rom-Fiumicino", "Italien"],
  CIA: ["Rom-Ciampino", "Italien"],
  ROM: ["Rom (FCO/CIA)", "Italien"],
  MXP: ["Mailand-Malpensa", "Italien"],
  BGY: ["Mailand-Bergamo", "Italien"],
  NAP: ["Neapel", "Italien"],
  CTA: ["Catania (Sizilien)", "Italien"],
  PMO: ["Palermo (Sizilien)", "Italien"],
  BRI: ["Bari", "Italien"],
  BDS: ["Brindisi", "Italien"],
  PSA: ["Pisa", "Italien"],
  BLQ: ["Bologna", "Italien"],
  VCE: ["Venedig", "Italien"],
  CAG: ["Cagliari (Sardinien)", "Italien"],
  AHO: ["Alghero (Sardinien)", "Italien"],
  ATH: ["Athen", "Griechenland"],
  SKG: ["Thessaloniki", "Griechenland"],
  HER: ["Heraklion (Kreta)", "Griechenland"],
  CHQ: ["Chania (Kreta)", "Griechenland"],
  RHO: ["Rhodos", "Griechenland"],
  CFU: ["Korfu", "Griechenland"],
  KGS: ["Kos", "Griechenland"],
  ZTH: ["Zakynthos", "Griechenland"],
  JTR: ["Santorini", "Griechenland"],
  ZAD: ["Zadar", "Kroatien"],
  SPU: ["Split", "Kroatien"],
  DBV: ["Dubrovnik", "Kroatien"],
  PUY: ["Pula", "Kroatien"],
  ZAG: ["Zagreb", "Kroatien"],
  RJK: ["Rijeka", "Kroatien"],
  TIA: ["Tirana", "Albanien"],
  SOF: ["Sofia", "Bulgarien"],
  VAR: ["Varna", "Bulgarien"],
  BOJ: ["Burgas", "Bulgarien"],
  OTP: ["Bukarest", "Rumänien"],
  CLJ: ["Cluj-Napoca", "Rumänien"],
  SBZ: ["Sibiu", "Rumänien"],
  TSR: ["Timișoara", "Rumänien"],
  BEG: ["Belgrad", "Serbien"],
  INI: ["Niš", "Serbien"],
  SJJ: ["Sarajevo", "Bosnien und Herzegowina"],
  BNX: ["Banja Luka", "Bosnien und Herzegowina"],
  TGD: ["Podgorica", "Montenegro"],
  TIV: ["Tivat", "Montenegro"],
  SKP: ["Skopje", "Nordmazedonien"],
  OHD: ["Ohrid", "Nordmazedonien"],
  PRN: ["Pristina", "Kosovo"],
  LCA: ["Larnaka", "Zypern"],
  PFO: ["Paphos", "Zypern"],
  MLA: ["Malta", "Malta"],
  DUB: ["Dublin", "Irland"],
  STN: ["London-Stansted", "Vereinigtes Königreich"],
  LGW: ["London-Gatwick", "Vereinigtes Königreich"],
  LHR: ["London-Heathrow", "Vereinigtes Königreich"],
  MAN: ["Manchester", "Vereinigtes Königreich"],
  EDI: ["Edinburgh", "Vereinigtes Königreich"],
  CDG: ["Paris-CDG", "Frankreich"],
  ORY: ["Paris-Orly", "Frankreich"],
  NCE: ["Nizza", "Frankreich"],
  MRS: ["Marseille", "Frankreich"],
  AMS: ["Amsterdam", "Niederlande"],
  EIN: ["Eindhoven", "Niederlande"],
  BRU: ["Brüssel", "Belgien"],
  CPH: ["Kopenhagen", "Dänemark"],
  ARN: ["Stockholm", "Schweden"],
  OSL: ["Oslo", "Norwegen"],
  HEL: ["Helsinki", "Finnland"],
  RIX: ["Riga", "Lettland"],
  VNO: ["Vilnius", "Litauen"],
  TLL: ["Tallinn", "Estland"],
  KRK: ["Krakau", "Polen"],
  GDN: ["Danzig", "Polen"],
  WAW: ["Warschau", "Polen"],
  BUD: ["Budapest", "Ungarn"],
  PRG: ["Prag", "Tschechien"],
  VIE: ["Wien", "Österreich"],
  ZRH: ["Zürich", "Schweiz"],
  IST: ["Istanbul", "Türkei"],
  SAW: ["Istanbul-Sabiha Gökçen", "Türkei"],
  AYT: ["Antalya", "Türkei"],
  ADB: ["Izmir", "Türkei"],
  RAK: ["Marrakesch", "Marokko"],
  AGA: ["Agadir", "Marokko"],
  TNG: ["Tanger", "Marokko"],
  FEZ: ["Fès", "Marokko"],
  AMM: ["Amman", "Jordanien"],
  TLV: ["Tel Aviv", "Israel"],
  DXB: ["Dubai", "Vereinigte Arabische Emirate"],
  AUH: ["Abu Dhabi", "Vereinigte Arabische Emirate"],
  JFK: ["New York (JFK)", "USA"],
  EWR: ["New York (Newark)", "USA"],
  BOS: ["Boston", "USA"],
  MIA: ["Miami", "USA"],
  LAX: ["Los Angeles", "USA"],
  SFO: ["San Francisco", "USA"],
  BKK: ["Bangkok", "Thailand"],
  SIN: ["Singapur", "Singapur"],
  NRT: ["Tokio-Narita", "Japan"],
  HND: ["Tokio-Haneda", "Japan"],
};

const DEFAULT_DEPARTURES = [
  { code: "FMM", name: "Memmingen", max_explore_price_eur: 55.0 },
  { code: "MUC", name: "München", max_explore_price_eur: 120.0 },
];

const DEFAULT_WISHLIST = [
  { code: "PMI", name: "Palma de Mallorca", country: "Spanien", max_price_eur: 65.0 },
  { code: "LIS", name: "Lissabon", country: "Portugal", max_price_eur: 115.0 },
  { code: "BCN", name: "Barcelona", country: "Spanien", max_price_eur: 85.0 },
  { code: "ROM", name: "Rom (FCO/CIA)", country: "Italien", airports: ["FCO", "CIA"], max_price_eur: 70.0 },
  { code: "ATH", name: "Athen", country: "Griechenland", max_price_eur: 95.0 },
  { code: "TFS", name: "Teneriffa Süd", country: "Spanien", max_price_eur: 110.0 },
];

function resolveCityAndCountry(iata, fallbackCity = "", fallbackCountry = "") {
  const code = String(iata || "").trim().toUpperCase();
  if (IATA_CITY_MAP[code]) {
    const [city, country] = IATA_CITY_MAP[code];
    return [fallbackCity || city, fallbackCountry || country];
  }
  return [fallbackCity || code, fallbackCountry || "Unbekannt"];
}

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

function saveJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf8");
}

function parseYamlListSection(text, sectionName, fallbackList) {
  try {
    const trimmed = String(text || "").trim();
    if (trimmed.startsWith("{")) {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed[sectionName])) return parsed[sectionName];
    }
  } catch {
    // Not JSON, continue with YAML parsing
  }

  const regex = new RegExp(`^${sectionName}\\s*:\\s*\\n((?:^[ \\t]+.*\\n?)*)`, "m");
  const match = String(text || "").match(regex);
  if (!match) return fallbackList;

  const block = match[1];
  const items = [];
  let current = null;

  for (const line of block.split(/\r?\n/)) {
    const stripped = line.trim();
    if (!stripped || stripped.startsWith("#")) continue;
    let content = stripped;
    if (content.startsWith("- ")) {
      if (current) items.push(current);
      current = {};
      content = content.slice(2).trim();
    }
    if (current && content.includes(":")) {
      const idx = content.indexOf(":");
      const key = content.slice(0, idx).trim();
      const rawVal = content.slice(idx + 1).replace(/\s+#.*$/, "").trim();
      if (rawVal.startsWith("[") && rawVal.endsWith("]")) {
        try {
          current[key] = JSON.parse(rawVal);
        } catch {
          current[key] = rawVal
            .slice(1, -1)
            .split(",")
            .map((s) => s.trim().replace(/^["']|["']$/g, ""))
            .filter(Boolean);
        }
      } else {
        const cleanVal = rawVal.replace(/^["']|["']$/g, "");
        if (key === "max_price_eur" || key === "max_explore_price_eur") {
          const num = Number(cleanVal);
          current[key] = Number.isFinite(num) ? num : cleanVal;
        } else {
          current[key] = cleanVal;
        }
      }
    }
  }
  if (current) items.push(current);
  return items.length > 0 ? items : fallbackList;
}

function serializeWishlistYaml(wishlist) {
  if (!Array.isArray(wishlist) || wishlist.length === 0) {
    return "wishlist_destinations: []\n";
  }
  const lines = ["wishlist_destinations:"];
  for (const item of wishlist) {
    lines.push(`  - code: "${String(item.code || "").toUpperCase()}"`);
    if (item.name) lines.push(`    name: "${String(item.name)}"`);
    if (item.country) lines.push(`    country: "${String(item.country)}"`);
    if (Array.isArray(item.airports) && item.airports.length > 0) {
      lines.push(`    airports: [${item.airports.map((a) => `"${a}"`).join(", ")}]`);
    }
    const price = Number(item.max_price_eur || 100);
    lines.push(`    max_price_eur: ${price.toFixed(1)}`);
  }
  return lines.join("\n") + "\n";
}

function updateWishlistInConfigFile(newWishlist) {
  let text = fs.existsSync(SEARCH_CONFIG_PATH) ? fs.readFileSync(SEARCH_CONFIG_PATH, "utf8") : "";
  const trimmed = text.trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed);
      parsed.wishlist_destinations = newWishlist;
      fs.writeFileSync(SEARCH_CONFIG_PATH, JSON.stringify(parsed, null, 2), "utf8");
      return;
    } catch {
      // fall through
    }
  }

  const newSection = serializeWishlistYaml(newWishlist);
  const regex = /^wishlist_destinations\s*:\s*(?:\[\])?\n(?:^[ \t]+.*\n?)*/m;
  if (regex.test(text)) {
    text = text.replace(regex, newSection);
  } else {
    text = text.trimEnd() + "\n\n" + newSection;
  }
  fs.writeFileSync(SEARCH_CONFIG_PATH, text, "utf8");
}

function loadConfigLists() {
  if (!fs.existsSync(SEARCH_CONFIG_PATH)) {
    return { wishlist: DEFAULT_WISHLIST, departures: DEFAULT_DEPARTURES };
  }
  const text = fs.readFileSync(SEARCH_CONFIG_PATH, "utf8");
  const wishlist = parseYamlListSection(text, "wishlist_destinations", DEFAULT_WISHLIST);
  const departures = parseYamlListSection(text, "departure_airports", DEFAULT_DEPARTURES);
  return { wishlist, departures };
}

function getPauseUntil() {
  try {
    if (!fs.existsSync(SEARCH_CONFIG_PATH)) return null;
    const text = fs.readFileSync(SEARCH_CONFIG_PATH, "utf8");
    const trimmed = text.trim();
    let val = "";
    if (trimmed.startsWith("{")) {
      const parsed = JSON.parse(trimmed);
      val = String(parsed.pause_until || "").trim().slice(0, 10);
    } else {
      const m = text.match(/^\s*pause_until\s*:\s*["']?([^"'\n#]*)["']?/m);
      if (!m) return null;
      val = String(m[1] || "").trim().slice(0, 10);
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(val)) return null;
    const todayIso = new Date().toISOString().slice(0, 10);
    return val >= todayIso ? val : null;
  } catch {
    return null;
  }
}

function setRadarPause(target) {
  const raw = String(target || "").trim();
  if (!raw) return { changed: false, message: "Keine Pausendauer angegeben." };
  const lower = raw.toLowerCase();
  let newVal = "";
  if (!["off", "0", "0d", "resume", "weiter", "unpause", "start", "false", "none", "stop", "active", "aktiv"].includes(lower)) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      newVal = raw;
    } else {
      const mDur = lower.match(/^(\d+)\s*(d|day|days|t|tag|tage|w|week|weeks|woche|wochen|m|month|months|monat|monate)?$/);
      if (!mDur) return { changed: false, message: "Ungültige Pausen-Angabe." };
      const amount = Number(mDur[1]);
      const unit = mDur[2] || "d";
      let days = amount;
      if (unit.startsWith("w")) days = amount * 7;
      else if (unit.startsWith("m")) days = amount * 30;
      days = Math.min(Math.max(days, 1), 365);
      const dt = new Date();
      dt.setUTCDate(dt.getUTCDate() + days);
      newVal = dt.toISOString().slice(0, 10);
    }
  }
  try {
    let text = fs.existsSync(SEARCH_CONFIG_PATH) ? fs.readFileSync(SEARCH_CONFIG_PATH, "utf8") : "";
    if (text.trim().startsWith("{")) {
      const parsed = JSON.parse(text);
      parsed.pause_until = newVal;
      fs.writeFileSync(SEARCH_CONFIG_PATH, JSON.stringify(parsed, null, 2), "utf8");
    } else {
      if (/^\s*pause_until\s*:/m.test(text)) {
        text = text.replace(/^\s*pause_until\s*:.*$/m, `pause_until: "${newVal}"`);
      } else {
        text = `pause_until: "${newVal}"\n` + text;
      }
      fs.writeFileSync(SEARCH_CONFIG_PATH, text, "utf8");
    }
    return {
      changed: true,
      message: newVal ? `Radar pausiert bis einschließlich ${newVal}.` : "Radar ist wieder aktiv.",
    };
  } catch {
    return { changed: false, message: "Konfiguration konnte nicht gespeichert werden." };
  }
}

function addExclusion(target) {
  const raw = String(target || "").trim();
  if (!raw) return { changed: false, message: "Kein Ziel zum Ausschließen angegeben." };

  const bl = loadJson(BLACKLIST_PATH, {
    excluded_airports: [],
    excluded_cities: [],
    excluded_countries: [],
  });
  bl.excluded_airports = Array.isArray(bl.excluded_airports) ? bl.excluded_airports : [];
  bl.excluded_cities = Array.isArray(bl.excluded_cities) ? bl.excluded_cities : [];
  bl.excluded_countries = Array.isArray(bl.excluded_countries) ? bl.excluded_countries : [];

  const lower = raw.toLowerCase();
  if (lower.startsWith("country:") || lower.startsWith("land:")) {
    const val = raw.split(":", 2)[1].trim();
    if (val && !bl.excluded_countries.includes(val)) {
      bl.excluded_countries.push(val);
      saveJson(BLACKLIST_PATH, bl);
      return { changed: true, message: `Land ${val} wurde auf die Blacklist gesetzt.` };
    }
    return { changed: false, message: `Land ${val} war bereits auf der Blacklist.` };
  }

  if (lower.startsWith("city:") || lower.startsWith("stadt:")) {
    const val = raw.split(":", 2)[1].trim();
    if (val && !bl.excluded_cities.includes(val)) {
      bl.excluded_cities.push(val);
      saveJson(BLACKLIST_PATH, bl);
      return { changed: true, message: `Stadt ${val} wurde auf die Blacklist gesetzt.` };
    }
    return { changed: false, message: `Stadt ${val} war bereits auf der Blacklist.` };
  }

  const cleaned = lower.startsWith("airport:") ? raw.split(":", 2)[1].trim() : raw;
  if (/^[A-Za-z]{3}$/.test(cleaned)) {
    const code = cleaned.toUpperCase();
    const [cityName] = resolveCityAndCountry(code);
    if (!bl.excluded_airports.includes(code)) {
      bl.excluded_airports.push(code);
      saveJson(BLACKLIST_PATH, bl);
      return { changed: true, message: `Flughafen ${code} (${cityName}) wurde auf die Blacklist gesetzt.` };
    }
    return { changed: false, message: `Flughafen ${code} (${cityName}) stand bereits auf der Blacklist.` };
  }

  if (!bl.excluded_cities.includes(cleaned)) {
    bl.excluded_cities.push(cleaned);
    saveJson(BLACKLIST_PATH, bl);
    return { changed: true, message: `Ort ${cleaned} wurde auf die Blacklist gesetzt.` };
  }
  return { changed: false, message: `Ort ${cleaned} stand bereits auf der Blacklist.` };
}

function removeExclusion(target) {
  const raw = String(target || "").trim();
  if (!raw) return { changed: false, message: "Kein Ziel zum Entfernen angegeben." };
  const cleaned = raw.replace(/^(?:country|land|city|stadt|airport)\s*:\s*/i, "").trim();

  const bl = loadJson(BLACKLIST_PATH, {
    excluded_airports: [],
    excluded_cities: [],
    excluded_countries: [],
  });
  const beforeAirports = (bl.excluded_airports || []).length;
  const beforeCities = (bl.excluded_cities || []).length;
  const beforeCountries = (bl.excluded_countries || []).length;

  bl.excluded_airports = (bl.excluded_airports || []).filter((a) => String(a).toUpperCase() !== cleaned.toUpperCase());
  bl.excluded_cities = (bl.excluded_cities || []).filter((c) => String(c).toLowerCase() !== cleaned.toLowerCase());
  bl.excluded_countries = (bl.excluded_countries || []).filter((co) => String(co).toLowerCase() !== cleaned.toLowerCase());

  if (
    bl.excluded_airports.length !== beforeAirports ||
    bl.excluded_cities.length !== beforeCities ||
    bl.excluded_countries.length !== beforeCountries
  ) {
    saveJson(BLACKLIST_PATH, bl);
    return { changed: true, message: `${cleaned} wurde wieder von der Blacklist entfernt.` };
  }
  return { changed: false, message: `${cleaned} wurde nicht auf der Blacklist gefunden.` };
}

function loadExcludedDealSignatures() {
  const exRaw = loadJson(DEAL_EXCLUSIONS_PATH, { excluded_signatures: [] });
  const rawList = Array.isArray(exRaw.excluded_signatures)
    ? exRaw.excluded_signatures
    : Array.isArray(exRaw.excluded_deals)
      ? exRaw.excluded_deals
      : [];
  return [...new Set(rawList.map((s) => String(s || "").trim()).filter(Boolean))].sort();
}

function addDealExclusion(signature) {
  const sig = String(signature || "").trim();
  if (!/^[A-Z]{3}-[A-Z]{3}:\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$/.test(sig)) {
    return { changed: false, message: "Ungültige Deal-ID." };
  }
  const list = loadExcludedDealSignatures();
  if (list.includes(sig)) {
    return { changed: false, message: `Deal ${sig} war bereits ausgeschlossen.` };
  }
  list.push(sig);
  list.sort();
  saveJson(DEAL_EXCLUSIONS_PATH, { excluded_signatures: list });
  return { changed: true, message: `Deal ${sig} wurde dauerhaft ausgeschlossen.` };
}

function removeDealExclusion(signature) {
  const sig = String(signature || "").trim();
  const list = loadExcludedDealSignatures();
  const filtered = list.filter((item) => item !== sig);
  if (filtered.length === list.length) {
    return { changed: false, message: `Deal ${sig} war nicht ausgeschlossen.` };
  }
  saveJson(DEAL_EXCLUSIONS_PATH, { excluded_signatures: filtered });
  return { changed: true, message: `Deal-Ausschluss ${sig} wurde aufgehoben.` };
}

function addOrUpdateWishlist(code, maxPriceEur, name) {
  const iata = String(code || "").trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(iata)) {
    return { changed: false, message: "Ungültiger IATA-Code (3 Buchstaben erwartet)." };
  }
  const price = Number(maxPriceEur);
  if (!Number.isFinite(price) || price <= 0) {
    return { changed: false, message: "Ungültiger Maximalpreis." };
  }
  const { wishlist } = loadConfigLists();
  const [cityName, countryName] = resolveCityAndCountry(iata, name || "");
  let updated = false;
  const nextList = wishlist.map((item) => {
    if (String(item.code || "").toUpperCase() === iata) {
      updated = true;
      return {
        ...item,
        code: iata,
        name: name || item.name || cityName,
        country: item.country || countryName,
        max_price_eur: price,
      };
    }
    return item;
  });

  if (!updated) {
    nextList.push({
      code: iata,
      name: name || cityName,
      country: countryName,
      max_price_eur: price,
    });
  }

  updateWishlistInConfigFile(nextList);
  return {
    changed: true,
    message: updated
      ? `Wunschziel ${name || cityName} (${iata}) aktualisiert auf max. ${Math.round(price)} €.`
      : `Neues Wunschziel ${name || cityName} (${iata}) mit Limit ${Math.round(price)} € hinzugefügt.`,
  };
}

function removeWishlist(code) {
  const cleaned = String(code || "").trim();
  if (!cleaned) return { changed: false, message: "Kein Wunschziel angegeben." };
  const { wishlist } = loadConfigLists();
  const kept = wishlist.filter(
    (item) =>
      String(item.code || "").toUpperCase() !== cleaned.toUpperCase() &&
      String(item.name || "").toLowerCase() !== cleaned.toLowerCase()
  );
  if (kept.length === wishlist.length) {
    return { changed: false, message: `Wunschziel ${cleaned} war nicht in der Wunschliste.` };
  }
  updateWishlistInConfigFile(kept);
  return { changed: true, message: `Wunschziel ${cleaned} wurde entfernt.` };
}

function triggerTestDiscord(callback) {
  try {
    let text = fs.existsSync(SEARCH_CONFIG_PATH) ? fs.readFileSync(SEARCH_CONFIG_PATH, "utf8") : "";
    if (text.trim().startsWith("{")) {
      const parsed = JSON.parse(text);
      parsed.force_next_discord = true;
      fs.writeFileSync(SEARCH_CONFIG_PATH, JSON.stringify(parsed, null, 2), "utf8");
    } else {
      if (/^\s*force_next_discord\s*:/m.test(text)) {
        text = text.replace(/^\s*force_next_discord\s*:.*$/m, "force_next_discord: true");
      } else {
        text = "force_next_discord: true\n" + text;
      }
      fs.writeFileSync(SEARCH_CONFIG_PATH, text, "utf8");
    }
  } catch {
    return callback({
      changed: false,
      has_webhook: false,
      message: "Konfiguration konnte nicht gespeichert werden.",
    });
  }

  const webhook = String(process.env.DISCORD_WEBHOOK_URL || "").trim();
  if (!webhook) {
    return callback({
      changed: true,
      has_webhook: false,
      message:
        "🔔 Nächster Discord-Versand zum Testen aktiviert (force_next_discord: true)! Beim nächsten Suchlauf wird garantiert eine Discord-Benachrichtigung gesendet.",
    });
  }

  try {
    const deals = getFilteredDeals().slice(0, 10);
    const slug = process.env.GITHUB_REPOSITORY || "KayToTheRopf/FlightScannerMK";
    const [owner, repo] = slug.split("/");
    const pageUrl = process.env.FLIGHT_DEALS_PAGE_URL || `https://${owner}.github.io/${repo}/`;
    const bestPrice = deals.length > 0 ? Math.min(...deals.map((d) => Number(d.offer?.price_eur || 0))) : 0;
    const content = `✈️ **${deals.length} neue Flug-Schnäppchen ab München / Memmingen!**\nGünstigster Preis ab **${bestPrice.toFixed(0)} €** Hin & Zurück.\n👉 **[Alle Angebote auf der Deal-Seite ansehen](${pageUrl})**`;

    const payload = Buffer.from(JSON.stringify({ username: "✈️ Flug-Schnäppchen-Radar", content }), "utf8");
    const parsedWebhook = new URL(webhook);
    const req = https.request(
      {
        hostname: parsedWebhook.hostname,
        path: parsedWebhook.pathname + parsedWebhook.search,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": payload.length,
        },
      },
      (resp) => {
        resp.on("data", () => {});
        resp.on("end", () => {
          callback({
            changed: true,
            has_webhook: true,
            message: `🔔 Test-Discord mit ${deals.length} Top-Schnäppchen wurde sofort gesendet! (Zusätzlich ist force_next_discord: true aktiv.)`,
          });
        });
      }
    );
    req.on("error", () => {
      callback({
        changed: true,
        has_webhook: false,
        message: "🔔 Nächster Discord-Versand zum Testen aktiviert (force_next_discord: true)!",
      });
    });
    req.write(payload);
    req.end();
  } catch {
    callback({
      changed: true,
      has_webhook: false,
      message: "🔔 Nächster Discord-Versand zum Testen aktiviert (force_next_discord: true)!",
    });
  }
}

function getFilteredDeals() {
  const raw = loadJson(ACTIVE_DEALS_PATH, { deals: [] });
  const deals = Array.isArray(raw.deals) ? raw.deals : [];
  const excludedSet = new Set(loadExcludedDealSignatures());
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

function getRepoSlug() {
  const slug = String(process.env.GITHUB_REPOSITORY || "KayToTheRopf/FlightScannerMK").trim();
  return slug.includes("/") ? slug : "KayToTheRopf/FlightScannerMK";
}

function buildPauseIssueUrl(target) {
  const slug = getRepoSlug();
  if (target === "off") {
    const title = encodeURIComponent("resume:now");
    const body = encodeURIComponent(
      "Bitte den Flug-Schnäppchen-Radar sofort wieder aktivieren (`/resume`).\n\n*(Einfach auf 'Submit new issue' klicken.)*"
    );
    return `https://github.com/${slug}/issues/new?title=${title}&labels=feedback-exclude&body=${body}`;
  }
  const title = encodeURIComponent(`pause:${target}`);
  const body = encodeURIComponent(
    `Bitte den Flug-Schnäppchen-Radar für \`${target}\` pausieren.\n\n*(Einfach auf 'Submit new issue' klicken.)*`
  );
  return `https://github.com/${slug}/issues/new?title=${title}&labels=feedback-exclude&body=${body}`;
}

function buildFeedbackIssueUrl(titleRaw, bodyRaw) {
  const slug = getRepoSlug();
  return `https://github.com/${slug}/issues/new?title=${encodeURIComponent(titleRaw)}&labels=feedback-exclude&body=${encodeURIComponent(bodyRaw)}`;
}

function formatDealSignature(sig) {
  const parts = String(sig || "").split(":");
  if (parts.length === 3 && parts[0].includes("-")) {
    const [origin, dest] = parts[0].split("-", 2);
    const [cityName] = resolveCityAndCountry(dest);
    const destLabel = cityName && cityName.toUpperCase() !== dest.toUpperCase() ? `${dest} (${cityName})` : dest;
    return `${origin} → ${destLabel} · ${parts[1]} bis ${parts[2]} (${sig})`;
  }
  return sig;
}

function formatGermanTimestamp(dateObj) {
  try {
    const parts = new Intl.DateTimeFormat("de-DE", {
      timeZone: "Europe/Berlin",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(dateObj);
    const map = {};
    for (const p of parts) map[p.type] = p.value;
    return `${map.day}.${map.month}.${map.year} ${map.hour}:${map.minute} Uhr`;
  } catch {
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(dateObj.getUTCDate())}.${pad(dateObj.getUTCMonth() + 1)}.${dateObj.getUTCFullYear()} ${pad(dateObj.getUTCHours())}:${pad(dateObj.getUTCMinutes())} UTC`;
  }
}

function renderDealsPage(deals, pausedUntil) {
  let latestDate = new Date();
  try {
    const candidatePaths = [ACTIVE_DEALS_PATH, SEARCH_CONFIG_PATH, BLACKLIST_PATH, DEAL_EXCLUSIONS_PATH];
    const mtimes = candidatePaths
      .filter((p) => fs.existsSync(p))
      .map((p) => fs.statSync(p).mtime.getTime());
    if (mtimes.length > 0) {
      latestDate = new Date(Math.max(...mtimes));
    }
  } catch {
    // ignore stat error
  }
  const pad = (n) => String(n).padStart(2, "0");
  const timestampUtc = `${pad(latestDate.getUTCDate())}.${pad(latestDate.getUTCMonth() + 1)}.${latestDate.getUTCFullYear()} ${pad(latestDate.getUTCHours())}:${pad(latestDate.getUTCMinutes())} UTC`;
  const timestampDe = formatGermanTimestamp(latestDate);

  const blacklist = loadJson(BLACKLIST_PATH, {
    excluded_airports: [],
    excluded_cities: [],
    excluded_countries: [],
    excluded_airlines: [],
  });
  const excludedDealsList = loadExcludedDealSignatures();
  const { wishlist, departures } = loadConfigLists();

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

  const url3d = escapeHtml(buildPauseIssueUrl("3d"));
  const url7d = escapeHtml(buildPauseIssueUrl("7d"));
  const url14d = escapeHtml(buildPauseIssueUrl("14d"));
  const url30d = escapeHtml(buildPauseIssueUrl("30d"));
  const urlResume = escapeHtml(buildPauseIssueUrl("off"));
  const urlTestDiscord = escapeHtml(
    buildFeedbackIssueUrl(
      "test-discord",
      "Bitte sofort eine Test-Discord-Nachricht mit den aktuellen Top-Schnäppchen senden (`/test-discord`).\n\n*(Einfach auf 'Submit new issue' klicken.)*"
    )
  );
  const slugEscaped = escapeHtml(getRepoSlug());

  const statusBadge = pausedUntil
    ? `<span class="status-pill status-paused">⏸ Pausiert bis einschl. ${escapeHtml(pausedUntil)}</span>`
    : '<span class="status-pill status-active">🟢 Radar aktiv (2x täglich)</span>';
  const pauseNotice = pausedUntil
    ? `<p class="pause-note">Automatische Suchläufe und Benachrichtigungen sind bis einschließlich <strong>${escapeHtml(pausedUntil)}</strong> ausgesetzt.</p>`
    : '<p class="pause-note">Du kannst die automatische Flugsuche und Benachrichtigungen für einen Zeitraum pausieren:</p>';
  const resumeBtn = pausedUntil
    ? `<a class="button button-resume" href="${urlResume}" onclick="return setRadarPause('off', this.href)">▶ Radar jetzt fortsetzen</a>`
    : "";

  const exAirports = (blacklist.excluded_airports || []).map((a) => String(a).trim()).filter(Boolean);
  const exCities = (blacklist.excluded_cities || []).map((c) => String(c).trim()).filter(Boolean);
  const exCountries = (blacklist.excluded_countries || []).map((co) => String(co).trim()).filter(Boolean);
  const exAirlines = (blacklist.excluded_airlines || []).map((al) => String(al).trim()).filter(Boolean);

  const airportChips = exAirports.map((code) => {
    const upper = code.toUpperCase();
    const [cityName] = resolveCityAndCountry(upper);
    const label = cityName && cityName.toUpperCase() !== upper ? `${upper} (${cityName})` : upper;
    const unUrl = escapeHtml(
      buildFeedbackIssueUrl(`unexclude:${upper}`, `Bitte Flughafen \`${upper}\` wieder von der Blacklist entfernen.`)
    );
    const codeJs = escapeHtml(upper);
    return `<span class="chip chip-exclusion">🛫 ${escapeHtml(label)} <a class="chip-remove" href="${unUrl}" title="Von Blacklist entfernen" onclick="return removeExclusion('${codeJs}', this.href)">×</a></span>`;
  });

  const cityChips = exCities.map((city) => {
    const unUrl = escapeHtml(
      buildFeedbackIssueUrl(`unexclude:${city}`, `Bitte Stadt/Ort \`${city}\` wieder von der Blacklist entfernen.`)
    );
    const cityJs = escapeHtml(city);
    return `<span class="chip chip-exclusion">🏙️ ${escapeHtml(city)} <a class="chip-remove" href="${unUrl}" title="Von Blacklist entfernen" onclick="return removeExclusion('${cityJs}', this.href)">×</a></span>`;
  });

  const countryChips = exCountries.map((country) => {
    const unUrl = escapeHtml(
      buildFeedbackIssueUrl(`unexclude:${country}`, `Bitte Land \`${country}\` wieder von der Blacklist entfernen.`)
    );
    const countryJs = escapeHtml(country);
    return `<span class="chip chip-exclusion">🌍 ${escapeHtml(country)} <a class="chip-remove" href="${unUrl}" title="Von Blacklist entfernen" onclick="return removeExclusion('${countryJs}', this.href)">×</a></span>`;
  });

  const airlineChips = exAirlines.map(
    (airline) => `<span class="chip chip-exclusion">✈️ ${escapeHtml(airline)}</span>`
  );

  const dealExclusionChips = excludedDealsList.map((sig) => {
    const formattedSig = formatDealSignature(sig);
    const unDealUrl = escapeHtml(
      buildFeedbackIssueUrl(`unexclude-deal:${sig}`, `Bitte den Deal-Ausschluss \`${sig}\` wieder aufheben.`)
    );
    const sigJs = escapeHtml(sig);
    return `<span class="chip chip-deal-exclusion">🎫 ${escapeHtml(formattedSig)} <a class="chip-remove" href="${unDealUrl}" title="Deal-Ausschluss aufheben" onclick="return removeDealExclusion('${sigJs}', this.href)">×</a></span>`;
  });

  const totalExclusions =
    exAirports.length + exCities.length + exCountries.length + exAirlines.length + excludedDealsList.length;

  const airportsHtml =
    airportChips.length > 0 ? airportChips.join("") : '<span class="muted-empty">Keine Flughäfen ausgeschlossen</span>';
  const citiesHtml =
    cityChips.length > 0 ? cityChips.join("") : '<span class="muted-empty">Keine Städte ausgeschlossen</span>';
  const countriesHtml =
    countryChips.length > 0 ? countryChips.join("") : '<span class="muted-empty">Keine Länder ausgeschlossen</span>';
  const dealsExHtml =
    dealExclusionChips.length > 0
      ? dealExclusionChips.join("")
      : '<span class="muted-empty">Keine einzelnen Deals ausgeschlossen</span>';
  const airlinesRowHtml =
    airlineChips.length > 0
      ? `<div class="exclusion-group"><span class="group-label">Ausgeschlossene Airlines:</span><div class="chip-list">${airlineChips.join("")}</div></div>`
      : "";

  const depChips = (departures || [])
    .map((dep) => {
      const dCode = String(dep.code || "").trim();
      const dName = String(dep.name || dCode).trim();
      const dMax = dep.max_explore_price_eur;
      const limitStr = dMax != null ? ` · Explore ≤ ${Number(dMax).toFixed(0)} €` : "";
      if (!dCode) return "";
      return `<span class="chip chip-departure">🛫 ${escapeHtml(dName)} (${escapeHtml(dCode)})${escapeHtml(limitStr)}</span>`;
    })
    .filter(Boolean);

  const wishChips = (wishlist || [])
    .map((w) => {
      const wCode = String(w.code || "").trim();
      if (!wCode) return "";
      const wName = String(w.name || wCode).trim();
      const wCountry = String(w.country || "").trim();
      const wMax = w.max_price_eur;
      const limitStr = wMax != null ? ` ≤ ${Number(wMax).toFixed(0)} €` : "";
      const countryStr = wCountry ? `, ${wCountry}` : "";
      const unwatchUrl = escapeHtml(
        buildFeedbackIssueUrl(
          `unwatch:${wCode.toUpperCase()}`,
          `Bitte Wunschziel \`${wCode.toUpperCase()}\` (${wName}) aus der Wunschliste entfernen.`
        )
      );
      const wCodeJs = escapeHtml(wCode.toUpperCase());
      const wNameJs = escapeHtml(wName);
      const wPriceJs = wMax != null ? Number(wMax).toFixed(0) : "100";
      return `<span class="chip chip-wishlist"><span class="chip-edit-trigger" title="Klicken, um Preisgrenze anzupassen" onclick="fillWishlistForm('${wCodeJs}', '${wPriceJs}', '${wNameJs}')">⭐ ${escapeHtml(wName)} (${escapeHtml(wCode)}${escapeHtml(countryStr)})${escapeHtml(limitStr)}</span> <a class="chip-remove chip-remove-wish" href="${unwatchUrl}" title="Wunschziel entfernen" onclick="return removeWishlist('${wCodeJs}', this.href)">×</a></span>`;
    })
    .filter(Boolean);

  const depHtml = depChips.length > 0 ? depChips.join("") : '<span class="muted-empty">Standard (MUC, FMM)</span>';
  const wishHtml =
    wishChips.length > 0 ? wishChips.join("") : '<span class="muted-empty">Keine festen Wunschziele konfiguriert</span>';
  const wishCount = wishChips.length;

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
    .pause-panel, .config-panel { margin-bottom: 1.25rem; padding: 1rem 1.25rem; background: white; border: 1px solid #dce3ee; border-radius: 12px; box-shadow: 0 3px 12px #172b4d0b; }
    .pause-panel.is-paused { background: #fffbeb; border-color: #f59e0b; }
    .pause-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: .75rem; }
    .pause-title { font-weight: 700; font-size: 1rem; margin: 0; }
    .status-pill { display: inline-block; padding: .25rem .65rem; border-radius: 999px; font-size: .85rem; font-weight: 650; }
    .status-active { background: #dcfce7; color: #166534; }
    .status-paused { background: #fef3c7; color: #92400e; }
    .status-count { background: #fee2e2; color: #991b1b; }
    .pause-note { margin: .5rem 0 .75rem; color: #475467; font-size: .92rem; }
    .pause-controls { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
    .pause-date-group { display: inline-flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
    .pause-date-input, .text-input { padding: .45rem .6rem; border: 1px solid #cbd5e1; border-radius: 7px; font-size: .88rem; color: #172033; background: white; }
    .pause-feedback { margin-top: .6rem; font-size: .88rem; font-weight: 600; color: #174ea6; display: none; }
    .exclusion-grid { display: grid; gap: .75rem; margin-top: .75rem; }
    .exclusion-group { display: grid; grid-template-columns: 210px 1fr; align-items: start; gap: .5rem; padding-bottom: .5rem; border-bottom: 1px dashed #e2e8f0; }
    .exclusion-group:last-of-type { border-bottom: none; padding-bottom: 0; }
    .group-label { font-size: .88rem; font-weight: 650; color: #334155; padding-top: .2rem; }
    .chip-list { display: flex; flex-wrap: wrap; gap: .45rem; align-items: center; }
    .chip { display: inline-flex; align-items: center; gap: .35rem; padding: .28rem .65rem; border-radius: 999px; font-size: .84rem; font-weight: 600; }
    .chip-exclusion { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
    .chip-deal-exclusion { background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }
    .chip-wishlist { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
    .chip-departure { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
    .chip-edit-trigger { cursor: pointer; }
    .chip-edit-trigger:hover { text-decoration: underline; }
    .chip-remove { display: inline-flex; align-items: center; justify-content: center; width: 1.15rem; height: 1.15rem; border-radius: 999px; background: #fee2e2; color: #7f1d1d; text-decoration: none; font-weight: 700; font-size: .85rem; line-height: 1; }
    .chip-remove:hover { background: #fca5a5; }
    .chip-remove-wish { background: #dbeafe; color: #1e3a8a; }
    .chip-remove-wish:hover { background: #93c5fd; }
    .status-wish { background: #dbeafe; color: #1e40af; }
    .input-code { width: 9.5rem; text-transform: uppercase; }
    .input-price { width: 9.5rem; }
    .muted-empty { color: #64748b; font-size: .86rem; font-style: italic; padding-top: .15rem; }
    .inline-form { margin-top: .85rem; padding-top: .75rem; border-top: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
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
    .button { display: inline-block; padding: .65rem .9rem; border-radius: 7px; color: white; text-decoration: none; font-weight: 650; border: none; cursor: pointer; font-size: .9rem; }
    .button-sm { padding: .45rem .75rem; font-size: .85rem; }
    .button-book { background: #1769aa; } .button-exclude { background: #b42318; }
    .button-pause { background: #475467; } .button-resume { background: #15803d; }
    .button-discord { background: #5865F2; }
    .button-disabled { background: #697586; cursor: default; }
    .empty { padding: 2rem; background: white; border-radius: 12px; text-align: center; }
    footer { max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #586579; font-size: .85rem; }
    @media (max-width: 640px) {
      dl div { grid-template-columns: 1fr; gap: .15rem; }
      .exclusion-group { grid-template-columns: 1fr; gap: .25rem; }
    }
  </style>
</head>
<body>
  <header>
    <h1>✈ Flug-Schnäppchen-Radar</h1>
    <p>${escapeHtml(summary)}</p>
    <p>Letzte Aktualisierung: <span id="last-updated-time" data-utc="${escapeHtml(timestampUtc)}" title="${escapeHtml(timestampUtc)}">${escapeHtml(timestampDe)}</span></p>
  </header>
  <main>
    <section class="pause-panel${pausedUntil ? " is-paused" : ""}" aria-label="Radar-Steuerung">
      <div class="pause-header">
        <p class="pause-title">⏱ Radar-Status &amp; Pause-Steuerung</p>
        ${statusBadge}
      </div>
      ${pauseNotice}
      <div class="pause-controls">
        ${resumeBtn}
        <a class="button button-sm button-pause" href="${url3d}" onclick="return setRadarPause('3d', this.href)">⏸ 3 Tage</a>
        <a class="button button-sm button-pause" href="${url7d}" onclick="return setRadarPause('7d', this.href)">⏸ 7 Tage</a>
        <a class="button button-sm button-pause" href="${url14d}" onclick="return setRadarPause('14d', this.href)">⏸ 14 Tage</a>
        <a class="button button-sm button-pause" href="${url30d}" onclick="return setRadarPause('30d', this.href)">⏸ 30 Tage</a>
        <span class="pause-date-group">
          <input type="date" id="pause-until-date" class="pause-date-input" value="${escapeHtml(pausedUntil || "")}" aria-label="Pausieren bis Datum">
          <button type="button" class="button button-sm button-pause" onclick="setRadarPauseFromDate()">Bis Datum pausieren</button>
        </span>
        <a class="button button-sm button-discord" href="${urlTestDiscord}" onclick="return sendTestDiscord(this.href)">🔔 Test-Discord senden</a>
      </div>
      <div id="pause-feedback" class="pause-feedback"></div>
    </section>

    <section class="config-panel" aria-label="Ausgeschlossene Ziele und Deals">
      <div class="pause-header">
        <p class="pause-title">🚫 Ausgeschlossene Ziele &amp; Deals (Blacklist)</p>
        <span class="status-pill status-count">${totalExclusions} Ausschlüsse aktiv</span>
      </div>
      <p class="pause-note">Diese Flughäfen, Städte, Länder und einzelnen Verbindungen werden bei der Schnäppchen-Suche ignoriert:</p>
      <div class="exclusion-grid">
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Flughäfen:</span>
          <div class="chip-list">${airportsHtml}</div>
        </div>
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Städte / Orte:</span>
          <div class="chip-list">${citiesHtml}</div>
        </div>
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Länder:</span>
          <div class="chip-list">${countriesHtml}</div>
        </div>
        ${airlinesRowHtml}
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Einzel-Deals:</span>
          <div class="chip-list">${dealsExHtml}</div>
        </div>
      </div>
      <div class="inline-form">
        <input type="text" id="exclude-target-input" class="text-input" placeholder="IATA (z.B. TIA), Stadt oder country:Land" aria-label="Ziel ausschließen">
        <button type="button" class="button button-sm button-exclude" onclick="addExclusionFromInput()">🚫 Ziel ausschließen</button>
      </div>
      <div id="exclude-feedback" class="pause-feedback"></div>
    </section>

    <section class="config-panel" aria-label="Überwachte Abflughäfen und Wunschziele">
      <div class="pause-header">
        <p class="pause-title">🎯 Überwachte Abflughäfen &amp; Wunschziele</p>
        <span class="status-pill status-wish">${wishCount} Wunschziele aktiv</span>
      </div>
      <p class="pause-note">Klicke auf ein Wunschziel, um dessen Maximalpreis anzupassen, oder füge unten ein neues Reiseziel per 3-Buchstaben-IATA-Code hinzu:</p>
      <div class="exclusion-grid">
        <div class="exclusion-group">
          <span class="group-label">Abflughäfen (Explore-Limit):</span>
          <div class="chip-list">${depHtml}</div>
        </div>
        <div class="exclusion-group">
          <span class="group-label">Wunschziele (Maximalpreis):</span>
          <div class="chip-list">${wishHtml}</div>
        </div>
      </div>
      <div class="inline-form">
        <input type="text" id="wishlist-code-input" class="text-input input-code" maxlength="3" placeholder="IATA (z.B. LIS)" aria-label="Wunschziel IATA-Code">
        <input type="number" id="wishlist-price-input" class="text-input input-price" min="1" step="1" placeholder="Max. € (z.B. 110)" aria-label="Maximalpreis in Euro">
        <input type="text" id="wishlist-name-input" class="text-input" placeholder="Städtename (optional, z.B. Lissabon)" aria-label="Optionaler Städtename">
        <button type="button" class="button button-sm button-book" onclick="saveWishlistFromInput()">⭐ Wunschziel speichern</button>
      </div>
      <div id="wishlist-feedback" class="pause-feedback"></div>
    </section>

    <section class="deal-list" aria-label="Gefundene Flugangebote">${content}</section>
  </main>
  <footer>Preise und Verfügbarkeiten können sich jederzeit ändern. Bitte beim Anbieter prüfen.</footer>
  <script>
    const REPO_SLUG = "${slugEscaped}";
    function setRadarPause(target, fallbackUrl) {
      const fb = document.getElementById("pause-feedback");
      if (fb) {
        fb.style.display = "block";
        fb.textContent = "Speichere Einstellung...";
      }
      fetch("/api/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: target })
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function() {
        window.location.reload();
      })
      .catch(function() {
        if (fallbackUrl) {
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }
      });
      return false;
    }
    function setRadarPauseFromDate() {
      const input = document.getElementById("pause-until-date");
      const val = input ? input.value.trim() : "";
      if (!val) return;
      const issueUrl = "https://github.com/" + REPO_SLUG + "/issues/new?title=" + encodeURIComponent("pause:" + val) + "&labels=feedback-exclude";
      setRadarPause(val, issueUrl);
    }
    function addExclusionFromInput() {
      const input = document.getElementById("exclude-target-input");
      const val = input ? input.value.trim() : "";
      if (!val) return;
      const fb = document.getElementById("exclude-feedback");
      if (fb) {
        fb.style.display = "block";
        fb.textContent = "Speichere Ausschluss...";
      }
      const issueUrl = "https://github.com/" + REPO_SLUG + "/issues/new?title=" + encodeURIComponent("exclude:" + val) + "&labels=feedback-exclude";
      fetch("/api/exclude", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: val })
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function() {
        window.location.reload();
      })
      .catch(function() {
        window.open(issueUrl, "_blank", "noopener,noreferrer");
      });
    }
    function removeExclusion(target, fallbackUrl) {
      fetch("/api/unexclude", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: target })
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function() {
        window.location.reload();
      })
      .catch(function() {
        if (fallbackUrl) {
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }
      });
      return false;
    }
    function removeDealExclusion(signature, fallbackUrl) {
      fetch("/api/unexclude-deal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signature: signature })
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function() {
        window.location.reload();
      })
      .catch(function() {
        if (fallbackUrl) {
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }
      });
      return false;
    }
    function fillWishlistForm(code, price, name) {
      const codeInput = document.getElementById("wishlist-code-input");
      const priceInput = document.getElementById("wishlist-price-input");
      const nameInput = document.getElementById("wishlist-name-input");
      if (codeInput) codeInput.value = code || "";
      if (priceInput) priceInput.value = price || "";
      if (nameInput) nameInput.value = name || "";
      if (priceInput) priceInput.focus();
    }
    function saveWishlistFromInput() {
      const codeInput = document.getElementById("wishlist-code-input");
      const priceInput = document.getElementById("wishlist-price-input");
      const nameInput = document.getElementById("wishlist-name-input");
      const code = codeInput ? codeInput.value.trim().toUpperCase() : "";
      const priceRaw = priceInput ? priceInput.value.trim() : "";
      const name = nameInput ? nameInput.value.trim() : "";
      const fb = document.getElementById("wishlist-feedback");
      if (!/^[A-Z]{3}$/.test(code)) {
        if (fb) {
          fb.style.display = "block";
          fb.textContent = "Bitte einen gültigen 3-stelligen IATA-Flughafencode eingeben (z.B. LIS, PMI, ATH).";
        }
        return;
      }
      const price = parseFloat(priceRaw.replace(",", "."));
      if (!price || price <= 0) {
        if (fb) {
          fb.style.display = "block";
          fb.textContent = "Bitte einen gültigen Maximalpreis in Euro eingeben (z.B. 110).";
        }
        return;
      }
      if (fb) {
        fb.style.display = "block";
        fb.textContent = "Speichere Wunschziel...";
      }
      const titleRaw = name ? ("watch:" + code + ":" + Math.round(price) + ":" + name) : ("watch:" + code + ":" + Math.round(price));
      const issueUrl = "https://github.com/" + REPO_SLUG + "/issues/new?title=" + encodeURIComponent(titleRaw) + "&labels=feedback-exclude";
      fetch("/api/wishlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, max_price_eur: price, name: name || null })
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function() {
        window.location.reload();
      })
      .catch(function() {
        window.open(issueUrl, "_blank", "noopener,noreferrer");
      });
    }
    function removeWishlist(code, fallbackUrl) {
      fetch("/api/unwatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code })
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function() {
        window.location.reload();
      })
      .catch(function() {
        if (fallbackUrl) {
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }
      });
      return false;
    }
    function sendTestDiscord(fallbackUrl) {
      const fb = document.getElementById("pause-feedback");
      if (fb) {
        fb.style.display = "block";
        fb.textContent = "Sende / aktiviere Test-Discord...";
      }
      fetch("/api/test-discord", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      })
      .then(function(res) {
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      })
      .then(function(data) {
        if (fb) {
          fb.style.display = "block";
          fb.textContent = data.message || "Test-Discord wurde vorgemerkt!";
        }
        if (!data.has_webhook && fallbackUrl) {
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }
      })
      .catch(function() {
        if (fallbackUrl) {
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }
      });
      return false;
    }
  </script>
</body>
</html>`;
}

function refreshStaticDealsPage() {
  try {
    const deals = getFilteredDeals();
    const pausedUntil = getPauseUntil();
    const htmlText = renderDealsPage(deals, pausedUntil);
    fs.mkdirSync(path.dirname(SITE_INDEX_PATH), { recursive: true });
    fs.writeFileSync(SITE_INDEX_PATH, htmlText, "utf8");
  } catch {
    // ignore write errors in read-only environments
  }
}

function sendJson(res, statusCode, payload, headOnly = false) {
  const body = Buffer.from(JSON.stringify(payload, null, 2), "utf8");
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length,
    "Cache-Control": "no-store, no-cache, must-revalidate",
  });
  res.end(headOnly ? undefined : body);
}

const server = http.createServer((req, res) => {
  const parsedUrl = new URL(req.url || "/", "http://localhost");
  const pathname = parsedUrl.pathname;
  const headOnly = req.method === "HEAD";

  if (req.method === "POST" && pathname.startsWith("/api/")) {
    let bodyStr = "";
    req.on("data", (chunk) => {
      bodyStr += chunk;
    });
    req.on("end", () => {
      let data = {};
      try {
        data = JSON.parse(bodyStr || "{}");
      } catch {
        data = {};
      }

      if (pathname === "/api/pause") {
        const result = setRadarPause(data.target);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, {
          ...result,
          paused_until: getPauseUntil(),
        });
      }

      if (pathname === "/api/exclude") {
        const result = addExclusion(data.target);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, result);
      }

      if (pathname === "/api/unexclude") {
        const result = removeExclusion(data.target);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, result);
      }

      if (pathname === "/api/exclude-deal") {
        const result = addDealExclusion(data.signature);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, result);
      }

      if (pathname === "/api/unexclude-deal") {
        const result = removeDealExclusion(data.signature);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, result);
      }

      if (pathname === "/api/wishlist") {
        const result = addOrUpdateWishlist(data.code, data.max_price_eur, data.name);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, result);
      }

      if (pathname === "/api/unwatch") {
        const result = removeWishlist(data.code);
        if (result.changed) refreshStaticDealsPage();
        return sendJson(res, result.changed ? 200 : 400, result);
      }

      if (pathname === "/api/test-discord") {
        triggerTestDiscord((result) => {
          if (result.changed) refreshStaticDealsPage();
          sendJson(res, result.changed ? 200 : 400, result);
        });
        return;
      }

      return sendJson(res, 404, { error: "Not found" });
    });
    return;
  }

  if (pathname === "/api/health") {
    return sendJson(res, 200, { status: "ok" }, headOnly);
  }

  if (pathname === "/api/deals") {
    const deals = getFilteredDeals();
    const pausedUntil = getPauseUntil();
    const blacklist = loadJson(BLACKLIST_PATH, {
      excluded_airports: [],
      excluded_cities: [],
      excluded_countries: [],
    });
    const excludedDeals = loadExcludedDealSignatures();
    const { wishlist, departures } = loadConfigLists();
    return sendJson(
      res,
      200,
      {
        count: deals.length,
        paused_until: pausedUntil,
        deals,
        wishlist_destinations: wishlist,
        departure_airports: departures,
        blacklist,
        excluded_deals: excludedDeals,
      },
      headOnly
    );
  }

  if (pathname === "/" || pathname === "/index.html") {
    let htmlText = "";
    try {
      const deals = getFilteredDeals();
      const pausedUntil = getPauseUntil();
      htmlText = renderDealsPage(deals, pausedUntil);
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
      "Cache-Control": "no-store, no-cache, must-revalidate",
    });
    return res.end(headOnly ? undefined : body);
  }

  return sendJson(res, 404, { error: "Not found" }, headOnly);
});

const port = Number(process.env.PORT || 3000);
const host = process.env.HOST || "0.0.0.0";
refreshStaticDealsPage();
server.listen(port, host, () => {
  console.log(`Flug-Schnäppchen-Radar Server listening on http://${host}:${port}`);
});
