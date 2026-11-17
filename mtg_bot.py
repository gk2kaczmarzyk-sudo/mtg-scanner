import os
import json
import time
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# ================= KONFIGURACJA =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen_offers.json")

# Oddzielne progi cenowe (w PLN) dla 10 dodatków: od Edge of Eternities do Star Trek
SET_PRICE_RULES = [
    {
        "set_name": "Edge of Eternities",
        "keywords": ["edge of eternities"],
        "prices": {
            "play_booster": 18,
            "play_box": 480,
            "collector_booster": 95,
            "collector_box": 1000,
            "commander": 145,
            "bundle": 165,
            "prerelease": 100,
        },
    },
    {
        "set_name": "Marvel's Spider-Man",
        "keywords": ["spider-man", "spiderman"],
        "prices": {
            "play_booster": 18,
            "play_box": 480,
            "collector_booster": 115,
            "collector_box": 1250,
            "bundle": 190,
            "prerelease": 120,
            "scene_box": 110,
        },
    },
    {
        "set_name": "Avatar: The Last Airbender",
        "keywords": ["avatar"],
        "prices": {
            "play_booster": 21,
            "play_box": 630,
            "collector_booster": 145,
            "collector_box": 1350,
            "bundle": 210,
            "prerelease": 135,
            "beginner_box": 110,
            "scene_box": 135,
        },
    },
    {
        "set_name": "Lorwyn Eclipsed",
        "keywords": ["lorwyn"],
        "prices": {
            "play_booster": 20,
            "play_box": 450,
            "collector_booster": 115,
            "collector_box": 1250,
            "commander": 195,
            "bundle": 205,
            "prerelease": 115,
            "draft_night": 320,
        },
    },
    {
        "set_name": "Teenage Mutant Ninja Turtles",
        "keywords": ["ninja turtles", "tmnt"],
        "prices": {
            "play_booster": 18,
            "play_box": 490,
            "collector_booster": 110,
            "collector_box": 1200,
            "commander": 190,
            "bundle": 165,
            "prerelease": 115,
            "draft_night": 320,
        },
    },
    {
        "set_name": "Secrets of Strixhaven",
        "keywords": ["strixhaven"],
        "prices": {
            "play_booster": 17,
            "play_box": 440,
            "collector_booster": 95,
            "collector_box": 1000,
            "commander": 150,
            "bundle": 165,
            "prerelease": 100,
            "draft_night": 300,
        },
    },
    {
        "set_name": "Marvel Super Heroes",
        "keywords": ["marvel"],
        "prices": {
            "play_booster": 20,
            "play_box": 540,
            "collector_booster": 135,
            "collector_box": 1550,
            "commander": 175,
            "bundle": 200,
            "prerelease": 125,
            "draft_night": 350,
            "scene_box": 140,
        },
    },
    {
        "set_name": "The Hobbit",
        "keywords": ["hobbit"],
        "prices": {
            "play_booster": 22,
            "play_box": 600,
            "collector_booster": 250,
            "collector_box": 2900,
            "commander": 190,
            "bundle": 225,
            "prerelease": 140,
            "draft_night": 390,
            "scene_box": 155,
        },
    },
    {
        "set_name": "Reality Fracture",
        "keywords": ["reality fracture"],
        "prices": {
            "play_booster": 17,
            "play_box": 440,
            "collector_booster": 95,
            "collector_box": 1000,
            "commander": 150,
            "bundle": 165,
            "prerelease": 100,
            "draft_night": 300,
        },
    },
    {
        "set_name": "Star Trek",
        "keywords": ["star trek"],
        "prices": {
            "play_booster": 20,
            "play_box": 550,
            "collector_booster": 145,
            "collector_box": 1650,
            "commander": 180,
            "bundle": 205,
            "prerelease": 130,
            "draft_night": 360,
            "scene_box": 145,
        },
    },
]

PRODUCT_LABELS = {
    "play_booster": "Play Booster",
    "play_box": "Play Booster Box",
    "collector_booster": "Collector Booster",
    "collector_box": "Collector Booster Box",
    "commander": "Commander Deck",
    "bundle": "Bundle",
    "prerelease": "Prerelease Pack",
    "draft_night": "Draft Night",
    "scene_box": "Scene Box",
    "beginner_box": "Beginner Box",
}

# Oczyszczona lista 41 aktywnych sklepów z poprawnymi adresami
POLISH_STORES = [
    {"name": "Strefa MTG", "base_url": "https://strefamtg.pl", "require_magic_word": False,
     "urls": ["https://strefamtg.pl/szukaj?controller=search&s=booster", "https://strefamtg.pl/szukaj?controller=search&s=commander", "https://strefamtg.pl/szukaj?controller=search&s=draft+night"]},
    {"name": "Centrum MTG", "base_url": "https://www.centrum-mtg.com.pl", "require_magic_word": False,
     "urls": ["https://www.centrum-mtg.com.pl/?s=booster&post_type=product", "https://www.centrum-mtg.com.pl/?s=commander&post_type=product"]},
    {"name": "Time4Magic", "base_url": "https://time4magic.pl", "require_magic_word": False,
     "urls": ["https://time4magic.pl/commander-decki-magic-the-gathering", "https://time4magic.pl/pl/searchquery/booster/1/phot/5"]},
    {"name": "Card Dojo", "base_url": "https://carddojo.pl", "require_magic_word": False,
     "urls": ["https://carddojo.pl/pl/c/Magic-the-Gathering/43"]},
    {"name": "Sklep Merfolk", "base_url": "https://sklep.merfolk.pl", "require_magic_word": False,
     "urls": ["https://sklep.merfolk.pl/category/BOOSTERY-I-BOXY-MTG-343892"]},
    {"name": "Dragonus", "base_url": "https://dragonus.pl", "require_magic_word": True,
     "urls": ["https://dragonus.pl/pl/searchquery/booster/1/phot/5", "https://dragonus.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "MagicTown", "base_url": "https://magictown.pl", "require_magic_word": False,
     "urls": ["https://magictown.pl/?s=booster&post_type=product", "https://magictown.pl/?s=commander&post_type=product"]},
    {"name": "Zgrani.pl", "base_url": "https://zgrani.pl", "require_magic_word": False,
     "urls": ["https://zgrani.pl/pl/menu/magic-the-gathering/boostery-157", "https://zgrani.pl/pl/producers/magic-the-gathering-1618991396"]},
    {"name": "Sklep Graal", "base_url": "https://sklep-graal.pl", "require_magic_word": False,
     "urls": ["https://sklep-graal.pl/pl/c/Boostery/760", "https://sklep-graal.pl/pl/c/Commander/767"]},
    {"name": "Pan Mysza", "base_url": "https://panmysza.pl", "require_magic_word": False,
     "urls": ["https://panmysza.pl/pl/c/Magic-The-Gathering/53"]},
    {"name": "Jaskinia Trolla", "base_url": "https://jaskiniatrolla.pl", "require_magic_word": False,
     "urls": ["https://jaskiniatrolla.pl/Magic-the-Gathering-c560"]},
    {"name": "Xjoy.pl", "base_url": "https://www.xjoy.pl", "require_magic_word": False,
     "urls": ["https://www.xjoy.pl/371-mtg-commander", "https://www.xjoy.pl/441-mtg-booster-box-y"]},
    {"name": "Centrum Gier Pegaz", "base_url": "https://pegaz-gry.pl", "require_magic_word": False,
     "urls": ["https://pegaz-gry.pl/brand/6-wizards-of-the-coast", "https://pegaz-gry.pl/96-magic-the-gathering-commander"]},
    {"name": "Przyczółek", "base_url": "https://przyczolek.pl", "require_magic_word": False,
     "urls": ["https://przyczolek.pl/wizards-of-the-coast"]},
    {"name": "Stajnia Gier", "base_url": "https://stajnia-gier.pl", "require_magic_word": False,
     "urls": ["https://stajnia-gier.pl/brand/4-wizards-of-the-coast"]},
    {"name": "Redraft", "base_url": "https://redraft.pl", "require_magic_word": False,
     "urls": ["https://redraft.pl/pl/menu/magic-the-gathering-165.html"]},
    {"name": "Flamberg", "base_url": "https://flamberg.com.pl", "require_magic_word": False,
     "urls": ["https://flamberg.com.pl/pl/menu/boostery-i-boxy-163"]},
    {"name": "Gralnia", "base_url": "https://gralnia.pl", "require_magic_word": True,
     "urls": ["https://gralnia.pl/pl/searchquery/booster/1/phot/5", "https://gralnia.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Rebel.pl", "base_url": "https://www.rebel.pl", "require_magic_word": True,
     "urls": ["https://www.rebel.pl/szukaj.html?q=magic+booster", "https://www.rebel.pl/szukaj.html?q=magic+commander"]},
    {"name": "Mepel.pl", "base_url": "https://mepel.pl", "require_magic_word": True,
     "urls": ["https://mepel.pl/pl/searchquery/booster/1/phot/5", "https://mepel.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Planszostrefa", "base_url": "https://planszostrefa.pl", "require_magic_word": True,
     "urls": ["https://planszostrefa.pl/pl/searchquery/booster/1/phot/5", "https://planszostrefa.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Aleplanszówki", "base_url": "https://aleplanszowki.pl", "require_magic_word": True,
     "urls": ["https://aleplanszowki.pl/szukaj?controller=search&s=magic+booster", "https://aleplanszowki.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "3Trolle", "base_url": "https://3trolle.pl", "require_magic_word": True,
     "urls": ["https://3trolle.pl/szukaj?controller=search&s=magic+booster", "https://3trolle.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "Bolter.pl", "base_url": "https://bolter.pl", "require_magic_word": True,
     "urls": ["https://bolter.pl/pl/searchquery/booster/1/phot/5", "https://bolter.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Vanaheim", "base_url": "https://vanaheim.pl", "require_magic_word": True,
     "urls": ["https://vanaheim.pl/pl/szukaj?controller=search&s=magic+booster", "https://vanaheim.pl/pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "XGames", "base_url": "https://xgames.pl", "require_magic_word": True,
     "urls": ["https://xgames.pl/pl/searchquery/booster/1/phot/5", "https://xgames.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Zagramy.pl", "base_url": "https://zagramy.pl", "require_magic_word": True,
     "urls": ["https://zagramy.pl/pl/searchquery/booster/1/phot/5", "https://zagramy.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Wargamer", "base_url": "https://sklep.wargamer.pl", "require_magic_word": True,
     "urls": ["https://sklep.wargamer.pl/szukaj?controller=search&s=magic+booster", "https://sklep.wargamer.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "RGFK.pl", "base_url": "https://rgfk.pl", "require_magic_word": True,
     "urls": ["https://rgfk.pl/szukaj?controller=search&s=magic+booster", "https://rgfk.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "Planszomania", "base_url": "https://www.planszomania.pl", "require_magic_word": True,
     "urls": ["https://www.planszomania.pl/szukaj?q=magic+booster", "https://www.planszomania.pl/szukaj?q=magic+commander"]},
    {"name": "Zagrajnik", "base_url": "https://zagrajnik.pl", "require_magic_word": True,
     "urls": ["https://zagrajnik.pl/pl/searchquery/booster/1/phot/5", "https://zagrajnik.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Geek Up", "base_url": "https://geekup.pl", "require_magic_word": True,
     "urls": ["https://geekup.pl/pl/searchquery/booster/1/phot/5", "https://geekup.pl/pl/searchquery/commander/1/phot/5"]},
    {"name": "Gry Bez Prądu", "base_url": "https://grybezpradu.eu", "require_magic_word": True,
     "urls": ["https://grybezpradu.eu/pl/searchquery/booster/1/phot/5", "https://grybezpradu.eu/pl/searchquery/commander/1/phot/5"]},
    {"name": "Bat-Cave", "base_url": "https://bat-cave.pl", "require_magic_word": True,
     "urls": ["https://bat-cave.pl/?s=magic+booster&post_type=product", "https://bat-cave.pl/?s=magic+commander&post_type=product"]},
    {"name": "Przystań Gier", "base_url": "https://przystangier.pl", "require_magic_word": True,
     "urls": ["https://przystangier.pl/pl/searchquery/booster/1/phot/5", "https://przystangier.pl/pl/searchquery/commander/1/phot/5"]},
]

BLACKLIST_WORDS = [
    "set booster", "draft booster", "school of mages",
    "koszulki", "sleeves", "album", "segregator", "mata", "playmat",
    "deck box", "deckbox", "pudełko na karty", "kości", "dice",
    "token", "singiel", "single", "puste", "pusty", "ultra pro", "dragon shield",
    "pokemon", "lorcana", "one piece", "star wars", "flesh and blood", "yu-gi-oh",
    "digimon", "altered", "sorcery", "riftbound", "gundam", "cyberpunk"
]

OUT_OF_STOCK_WORDS = [
    "brak towaru", "produkt niedostępny", "niedostępny", "obecnie brak na stanie",
    "wyprzedane", "powiadom o dostępności", "powiadom mnie o dostępności",
    "brak w magazynie", "oczekujemy"
]
# ================================================


def load_seen_offers():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_offers(seen_set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f, ensure_ascii=False, indent=2)


def send_telegram_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chat_ids = [cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(",") if cid.strip()]
    any_sent = False

    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        try:
            res = requests.post(url, data=payload, timeout=15)
            if res.status_code == 200:
                any_sent = True
            else:
                print(f"[BŁĄD TELEGRAM dla {chat_id}] {res.status_code}: {res.text}")
        except Exception as e:
            print(f"[BŁĄD POŁĄCZENIA TELEGRAM] {e}")

    return any_sent


def extract_price(card_soup):
    text = card_soup.get_text(" ", strip=True)
    matches = re.findall(r"(\d[\d\s\xa0]*[.,]\d{2})\s*(?:zł|pln)", text, flags=re.IGNORECASE)
    values = []
    for m in matches:
        cleaned = m.replace(" ", "").replace("\xa0", "").replace(",", ".")
        try:
            val = float(cleaned)
            if 5.0 <= val <= 10000.0:
                values.append(val)
        except ValueError:
            continue
    return min(values) if values else None


def classify_product(title):
    t = title.lower()
    is_box = ("box" in t or "display" in t)

    if "draft night" in t:
        return "draft_night"
    if "scene box" in t:
        return "scene_box"
    if "beginner box" in t:
        return "beginner_box"
    if "collector" in t and is_box:
        return "collector_box"
    if "collector" in t:
        return "collector_booster"
    if "bundle" in t:
        return "bundle"
    if "commander" in t:
        return "commander"
    if "prerelease" in t:
        return "prerelease"
    if is_box and "booster" in t:
        return "play_box"
    if "play booster" in t or ("booster" in t and not is_box):
        return "play_booster"

    return None


def match_set_and_price(title, current_price):
    t = title.lower()
    product_type = classify_product(title)
    if not product_type:
        return False, None

    for set_rule in SET_PRICE_RULES:
        if any(kw in t for kw in set_rule["keywords"]):
            max_price = set_rule["prices"].get(product_type)
            if max_price is not None and current_price <= max_price:
                label = PRODUCT_LABELS.get(product_type, product_type)
                reason = f"{set_rule['set_name']} — {label} (próg: {max_price} zł)"
                return True, reason
            return False, None

    return False, None


def parse_store_page(store_name, base_url, html, require_magic_word):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    cards = soup.select(
        ".product-inner-wrap, .product, .product-miniature, .product-box, "
        "li.product, article.product-miniature, .product_wrapper, .product-item, "
        ".product-container, .product__item, .product-card, .grid-product"
    )

    for card in cards:
        full_text = card.get_text(" ", strip=True).lower()
        if any(oos in full_text for oos in OUT_OF_STOCK_WORDS):
            continue

        link_el = card.select_one(
            "a.prodname, a.product-name, .product__name, .product-title a, "
            ".woocommerce-loop-product__title a, .product-name a, "
            ".product-item-link, h2 a, h3 a, h4 a, a[href]"
        )
        if not link_el:
            continue

        href = link_el.get("href", "").strip()
        if not href or href.startswith("#") or "javascript:" in href:
            continue

        title = link_el.get("title") or link_el.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 6:
            continue

        t_lower = title.lower()

        if require_magic_word and not any(w in t_lower for w in ["magic", "mtg"]):
            continue

        if any(bad in t_lower for bad in BLACKLIST_WORDS):
            continue

        current_price = extract_price(card)
        if not current_price:
            continue

        ok, reason = match_set_and_price(title, current_price)
        if not ok:
            continue

        full_url = urljoin(base_url, href)
        results.append({
            "id": full_url,
            "store": store_name,
            "title": title,
            "price": current_price,
            "reason": reason,
            "url": full_url,
        })

    return results


def create_http_session():
    if HAS_CLOUDSCRAPER:
        return cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    })
    return session


def fetch_direct_or_scraperapi(session, url, timeout=10):
    """Najpierw łączy się bezpośrednio za darmo; przy blokadzie IP USA używa ScraperAPI (PL)."""
    try:
        if HAS_CLOUDSCRAPER:
            res = session.get(url, timeout=timeout)
        else:
            res = session.get(url, timeout=timeout, verify=False)
        if res.status_code == 200:
            return res, "direct"
    except Exception:
        pass

    if not SCRAPER_API_KEY:
        return None, None

    try:
        api_params = {
            "api_key": SCRAPER_API_KEY,
            "url": url,
            "country_code": "pl",
        }
        res = requests.get("https://api.scraperapi.com/", params=api_params, timeout=20)
        if res.status_code == 200:
            return res, "scraperapi"
        print(f"[ScraperAPI] Status {res.status_code} dla {url}")
    except Exception as e:
        print(f"[ScraperAPI BŁĄD] {url}: {e}")

    return None, None


def scan_single_store(store):
    store_name = store["name"]
    base_url = store["base_url"]
    require_magic = store.get("require_magic_word", False)
    session = create_http_session()
    store_responded = False
    used_scraperapi = False
    store_deals = []

    for url in store["urls"]:
        res, mode = fetch_direct_or_scraperapi(session, url, timeout=10)
        if not res or res.status_code != 200:
            continue

        store_responded = True
        if mode == "scraperapi":
            used_scraperapi = True
        deals = parse_store_page(store_name, base_url, res.text, require_magic)
        store_deals.extend(deals)
        time.sleep(0.3)

    return store_name, store_responded, used_scraperapi, store_deals


def scan_polish_stores(seen_offers):
    new_found = 0
    working_direct = []
    working_api = []
    failed_stores = []
    all_deals = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scan_single_store, store) for store in POLISH_STORES]
        for future in as_completed(futures):
            store_name, responded, used_api, deals = future.result()
            if responded:
                if used_api:
                    working_api.append(store_name)
                else:
                    working_direct.append(store_name)
                all_deals.extend(deals)
            else:
                failed_stores.append(store_name)

    for deal in all_deals:
        offer_key = f"{deal['id']}_{deal['price']}"
        if offer_key in seen_offers:
            continue

        msg = (
            f"🔥 <b>Okazja MTG Sealed — {deal['store']}!</b>\n\n"
            f"📦 <b>{deal['title']}</b>\n"
            f"💰 Cena: <b>{deal['price']:.2f} zł</b>\n"
            f"🏷 {deal['reason']}\n\n"
            f"🔗 <a href='{deal['url']}'>Przejdź do sklepu</a>"
        )
        print(f"[OKAZJA] {deal['store']} | {deal['title']} | {deal['price']} zł")
        if send_telegram_text(msg):
            seen_offers.add(offer_key)
            new_found += 1
            time.sleep(0.5)

    return new_found, sorted(working_direct), sorted(working_api), sorted(failed_stores)


def run_once():
    mode_info = "z ScraperAPI PL" if SCRAPER_API_KEY else "bez klucza ScraperAPI"
    print(f"Skanuję {len(POLISH_STORES)} polskich sklepów ({mode_info})...")
    seen = load_seen_offers()
    found, direct_ok, api_ok, failed = scan_polish_stores(seen)
    save_seen_offers(seen)

    total_ok = len(direct_ok) + len(api_ok)

    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        direct_list = ", ".join(direct_ok) if direct_ok else "brak"
        api_list = ", ".join(api_ok) if api_ok else "brak"
        fail_list = ", ".join(failed) if failed else "brak"
        send_telegram_text(
            f"✅ <b>Skanowanie zakończone!</b>\n"
            f"🏪 Wynik: <b>{total_ok}/{len(POLISH_STORES)}</b>\n\n"
            f"🟢 <b>Bezpośrednio ({len(direct_ok)}):</b> {direct_list}\n\n"
            f"🇵🇱 <b>Odblokowane przez ScraperAPI PL ({len(api_ok)}):</b> {api_list}\n\n"
            f"🔴 <b>Niedostępne ({len(failed)}):</b> {fail_list}\n\n"
            f"🔥 <b>Nowych okazji:</b> {found}"
        )

    print(f"Zakończono. Działają: {total_ok}/{len(POLISH_STORES)} (w tym {len(api_ok)} przez ScraperAPI) | Nowe okazje: {found}")


if __name__ == "__main__":
    try:
        run_once()
    except Exception as err:
        send_telegram_text(f"❌ <b>Błąd krytyczny bota:</b> {err}")
        raise
