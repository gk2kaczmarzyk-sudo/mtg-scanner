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

# Oddzielne progi cenowe (w PLN) oparte o wartości rynkowe TCGplayer
# z rozbiciem na konkretne talie Commander Deck dla każdego dodatku
SET_PRICE_RULES = [
    {
        "set_name": "Foundations",
        "keywords": ["foundations"],
        "prices": {
            "play_booster": 16,
            "play_box": 430,
            "collector_booster": 115,
            "collector_box": 1250,
            "jumpstart_booster": 16,
            "jumpstart_box": 340,
            "bundle": 165,
            "prerelease": 100,
            "beginner_box": 105,
            "starter_collection": 195,
            "cmd_calling_all_angels": 105,
            "cmd_keen_engineering": 105,
            "cmd_wretched_ranks": 105,
            "cmd_reign_of_dragons": 105,
            "cmd_tramplesaurus_rex": 105,
            "commander_generic": 105,
        },
    },
    {
        "set_name": "Edge of Eternities",
        "keywords": ["edge of eternities"],
        "prices": {
            "play_booster": 18,
            "play_box": 520,
            "collector_booster": 180,
            "collector_box": 1850,
            "bundle": 240,
            "prerelease": 115,
            "cmd_world_shaper": 175,          # TCGplayer: ~$54.08
            "cmd_counter_intelligence": 140,  # TCGplayer: ~$43.29
            "commander_generic": 140,
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
            "play_booster": 18,
            "play_box": 440,
            "collector_booster": 135,
            "collector_box": 1350,
            "bundle": 210,
            "prerelease": 125,
            "beginner_box": 110,
            "scene_box": 135,
        },
    },
    {
        "set_name": "Lorwyn Eclipsed",
        "keywords": ["lorwyn"],
        "prices": {
            "play_booster": 18,
            "play_box": 450,
            "collector_booster": 115,
            "collector_box": 1250,
            "bundle": 195,
            "prerelease": 115,
            "draft_night": 310,
            "cmd_dance_of_the_elements": 145,  # TCGplayer: ~$40.67
            "cmd_blight_curse": 130,           # TCGplayer: ~$35.99
            "commander_generic": 130,
        },
    },
    {
        "set_name": "Teenage Mutant Ninja Turtles",
        "keywords": ["ninja turtles", "tmnt"],
        "prices": {
            "play_booster": 15,
            "play_box": 360,
            "collector_booster": 110,
            "collector_box": 1200,
            "bundle": 145,
            "prerelease": 85,
            "draft_night": 250,
            "cmd_turtle_power": 130,           # TCGplayer: ~$32.95
            "commander_generic": 130,
        },
    },
    {
        "set_name": "Secrets of Strixhaven",
        "keywords": ["strixhaven"],
        "prices": {
            "play_booster": 16,
            "play_box": 450,
            "collector_booster": 135,
            "collector_box": 1450,
            "bundle": 150,
            "prerelease": 105,
            "draft_night": 280,
            "cmd_silverquill_influence": 195,  # TCGplayer: ~$59.99
            "cmd_witherbloom_pestilence": 165, # TCGplayer: ~$48.61
            "cmd_prismari_artistry": 135,      # TCGplayer: ~$37.77
            "cmd_lorehold_spirit": 135,        # TCGplayer: ~$37.36
            "cmd_quandrix_unlimited": 130,     # TCGplayer: ~$36.82
            "commander_generic": 130,
        },
    },
    {
        "set_name": "Marvel Super Heroes",
        "keywords": ["marvel"],
        "prices": {
            "play_booster": 16,
            "play_box": 390,
            "collector_booster": 135,
            "collector_box": 1400,
            "bundle": 145,
            "prerelease": 95,
            "draft_night": 260,
            "scene_box": 80,
            "cmd_doom_prevails": 205,          # TCGplayer: ~$62.76
            "cmd_avengers_assemble": 155,      # TCGplayer: ~$44.88
            "cmd_wakanda_forever": 145,        # TCGplayer: ~$41.90
            "cmd_fantastic_four": 125,         # TCGplayer: ~$34.92
            "commander_generic": 125,
        },
    },
    {
        "set_name": "The Hobbit",
        "keywords": ["hobbit"],
        "prices": {
            "play_booster": 16,
            "play_box": 440,
            "collector_booster": 150,
            "collector_box": 1450,
            "bundle": 185,
            "prerelease": 115,
            "draft_night": 300,
            "scene_box": 110,
        },
    },
    {
        "set_name": "Reality Fracture",
        "keywords": ["reality fracture"],
        "prices": {
            "play_booster": 16,
            "play_box": 410,
            "collector_booster": 115,
            "collector_box": 1200,
            "bundle": 150,
            "prerelease": 100,
            "draft_night": 270,
            "cmd_multiverse_reforged": 175,    # TCGplayer: ~$52.82
            "commander_generic": 175,
        },
    },
    {
        "set_name": "Star Trek",
        "keywords": ["star trek"],
        "prices": {
            "play_booster": 16,
            "play_box": 395,
            "collector_booster": 135,
            "collector_box": 1350,
            "bundle": 160,
            "prerelease": 105,
            "draft_night": 275,
            "scene_box": 115,
            "cmd_we_are_the_borg": 235,        # TCGplayer: ~$73.57
            "cmd_landing_party": 180,          # TCGplayer: ~$54.93
            "cmd_federation_fleet": 140,       # TCGplayer: ~$39.99
            "cmd_klingon_fury": 140,           # TCGplayer: ~$39.47
            "commander_generic": 140,
        },
    },
]

# Słowa kluczowe dla konkretnych talii Commander Deck (kolejność ma znaczenie)
COMMANDER_DECK_KEYWORDS = [
    # Foundations
    (["calling all angels"], "cmd_calling_all_angels"),
    (["keen engineering"], "cmd_keen_engineering"),
    (["wretched ranks"], "cmd_wretched_ranks"),
    (["reign of dragons"], "cmd_reign_of_dragons"),
    (["tramplesaurus rex"], "cmd_tramplesaurus_rex"),
    # Edge of Eternities
    (["world shaper"], "cmd_world_shaper"),
    (["counter intelligence"], "cmd_counter_intelligence"),
    # Lorwyn Eclipsed
    (["dance of the elements"], "cmd_dance_of_the_elements"),
    (["blight curse"], "cmd_blight_curse"),
    # Teenage Mutant Ninja Turtles
    (["turtle power"], "cmd_turtle_power"),
    # Secrets of Strixhaven
    (["silverquill"], "cmd_silverquill_influence"),
    (["witherbloom"], "cmd_witherbloom_pestilence"),
    (["prismari"], "cmd_prismari_artistry"),
    (["lorehold"], "cmd_lorehold_spirit"),
    (["quandrix"], "cmd_quandrix_unlimited"),
    # Marvel Super Heroes
    (["doom prevails"], "cmd_doom_prevails"),
    (["avengers assemble"], "cmd_avengers_assemble"),
    (["wakanda forever"], "cmd_wakanda_forever"),
    (["fantastic four"], "cmd_fantastic_four"),
    # Reality Fracture
    (["multiverse reforged"], "cmd_multiverse_reforged"),
    # Star Trek
    (["we are the borg", "the borg"], "cmd_we_are_the_borg"),
    (["landing party"], "cmd_landing_party"),
    (["federation fleet"], "cmd_federation_fleet"),
    (["klingon fury"], "cmd_klingon_fury"),
]

PRODUCT_LABELS = {
    "jumpstart_booster": "Jumpstart Booster",
    "jumpstart_box": "Jumpstart Booster Box",
    "starter_collection": "Starter Collection",
    "play_booster": "Play Booster",
    "play_box": "Play Booster Box",
    "collector_booster": "Collector Booster",
    "collector_box": "Collector Booster Box",
    "bundle": "Bundle",
    "prerelease": "Prerelease Pack",
    "draft_night": "Draft Night",
    "scene_box": "Scene Box",
    "beginner_box": "Beginner Box",
    "commander_generic": "Commander Deck (ogólny)",
    # Konkretne talie Commander
    "cmd_calling_all_angels": "Commander Deck — Calling All Angels",
    "cmd_keen_engineering": "Commander Deck — Keen Engineering",
    "cmd_wretched_ranks": "Commander Deck — Wretched Ranks",
    "cmd_reign_of_dragons": "Commander Deck — Reign of Dragons",
    "cmd_tramplesaurus_rex": "Commander Deck — Tramplesaurus Rex",
    "cmd_world_shaper": "Commander Deck — World Shaper",
    "cmd_counter_intelligence": "Commander Deck — Counter Intelligence",
    "cmd_dance_of_the_elements": "Commander Deck — Dance of the Elements",
    "cmd_blight_curse": "Commander Deck — Blight Curse",
    "cmd_turtle_power": "Commander Deck — Turtle Power!",
    "cmd_silverquill_influence": "Commander Deck — Silverquill Influence",
    "cmd_witherbloom_pestilence": "Commander Deck — Witherbloom Pestilence",
    "cmd_prismari_artistry": "Commander Deck — Prismari Artistry",
    "cmd_lorehold_spirit": "Commander Deck — Lorehold Spirit",
    "cmd_quandrix_unlimited": "Commander Deck — Quandrix Unlimited",
    "cmd_doom_prevails": "Commander Deck — Doom Prevails",
    "cmd_avengers_assemble": "Commander Deck — Avengers Assemble",
    "cmd_wakanda_forever": "Commander Deck — Wakanda Forever",
    "cmd_fantastic_four": "Commander Deck — The Fantastic Four",
    "cmd_multiverse_reforged": "Commander Deck — Multiverse Reforged",
    "cmd_we_are_the_borg": "Commander Deck — We Are the Borg",
    "cmd_landing_party": "Commander Deck — Landing Party",
    "cmd_federation_fleet": "Commander Deck — Federation Fleet",
    "cmd_klingon_fury": "Commander Deck — Klingon Fury",
}

POLISH_STORES = [
    {"name": "Strefa MTG", "base_url": "https://strefamtg.pl", "require_magic_word": False,
     "urls": [
         "https://strefamtg.pl/szukaj?controller=search&s=booster",
         "https://strefamtg.pl/szukaj?controller=search&s=commander",
         "https://strefamtg.pl/szukaj?controller=search&s=bundle",
         "https://strefamtg.pl/szukaj?controller=search&s=foundations",
         "https://strefamtg.pl/szukaj?controller=search&s=draft+night",
     ]},
    {"name": "Centrum MTG", "base_url": "https://www.centrum-mtg.com.pl", "require_magic_word": False,
     "urls": [
         "https://www.centrum-mtg.com.pl/?s=booster&post_type=product",
         "https://www.centrum-mtg.com.pl/?s=commander&post_type=product",
         "https://www.centrum-mtg.com.pl/?s=bundle&post_type=product",
         "https://www.centrum-mtg.com.pl/?s=foundations&post_type=product",
     ]},
    {"name": "Time4Magic", "base_url": "https://time4magic.pl", "require_magic_word": True,
     "urls": [
         "https://time4magic.pl/commander-decki-magic-the-gathering",
         "https://time4magic.pl/pl/searchquery/magic+booster/1/phot/5",
         "https://time4magic.pl/pl/searchquery/magic+bundle/1/phot/5",
         "https://time4magic.pl/pl/searchquery/magic+foundations/1/phot/5",
     ]},
    {"name": "Card Dojo", "base_url": "https://carddojo.pl", "require_magic_word": False,
     "urls": ["https://carddojo.pl/pl/c/Magic-the-Gathering/43"]},
    {"name": "Sklep Merfolk", "base_url": "https://sklep.merfolk.pl", "require_magic_word": False,
     "urls": ["https://sklep.merfolk.pl/category/BOOSTERY-I-BOXY-MTG-343892"]},
    {"name": "Dragonus", "base_url": "https://dragonus.pl", "require_magic_word": True,
     "urls": [
         "https://dragonus.pl/pl/searchquery/magic+booster/1/phot/5",
         "https://dragonus.pl/pl/searchquery/magic+commander/1/phot/5",
         "https://dragonus.pl/pl/searchquery/magic+bundle/1/phot/5",
         "https://dragonus.pl/pl/searchquery/magic+foundations/1/phot/5",
     ]},
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
    {"name": "Rebel.pl", "base_url": "https://www.rebel.pl", "require_magic_word": True,
     "urls": [
         "https://www.rebel.pl/szukaj.html?q=magic+booster",
         "https://www.rebel.pl/szukaj.html?q=magic+commander",
         "https://www.rebel.pl/szukaj.html?q=magic+bundle",
         "https://www.rebel.pl/szukaj.html?q=magic+foundations",
     ]},
    {"name": "Mepel.pl", "base_url": "https://mepel.pl", "require_magic_word": True,
     "urls": ["https://mepel.pl/pl/searchquery/magic+booster/1/phot/5", "https://mepel.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Planszostrefa", "base_url": "https://planszostrefa.pl", "require_magic_word": True,
     "urls": ["https://planszostrefa.pl/pl/searchquery/magic+booster/1/phot/5", "https://planszostrefa.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Aleplanszówki", "base_url": "https://aleplanszowki.pl", "require_magic_word": True,
     "urls": ["https://aleplanszowki.pl/szukaj?controller=search&s=magic+booster", "https://aleplanszowki.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "3Trolle", "base_url": "https://3trolle.pl", "require_magic_word": True,
     "urls": ["https://3trolle.pl/szukaj?controller=search&s=magic+booster", "https://3trolle.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "Bolter.pl", "base_url": "https://bolter.pl", "require_magic_word": True,
     "urls": ["https://bolter.pl/pl/searchquery/magic+booster/1/phot/5", "https://bolter.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Vanaheim", "base_url": "https://vanaheim.pl", "require_magic_word": True,
     "urls": [
         "https://vanaheim.pl/pl/szukaj?controller=search&s=magic+booster",
         "https://vanaheim.pl/pl/szukaj?controller=search&s=magic+commander",
         "https://vanaheim.pl/pl/szukaj?controller=search&s=magic+bundle",
         "https://vanaheim.pl/pl/szukaj?controller=search&s=magic+foundations",
     ]},
    {"name": "Wargamer", "base_url": "https://sklep.wargamer.pl", "require_magic_word": True,
     "urls": [
         "https://sklep.wargamer.pl/szukaj?controller=search&s=magic+booster",
         "https://sklep.wargamer.pl/szukaj?controller=search&s=magic+commander",
         "https://sklep.wargamer.pl/szukaj?controller=search&s=magic+bundle",
         "https://sklep.wargamer.pl/szukaj?controller=search&s=magic+foundations",
     ]},
    {"name": "RGFK.pl", "base_url": "https://rgfk.pl", "require_magic_word": True,
     "urls": ["https://rgfk.pl/szukaj?controller=search&s=magic+booster", "https://rgfk.pl/szukaj?controller=search&s=magic+commander"]},
    {"name": "Planszomania", "base_url": "https://www.planszomania.pl", "require_magic_word": True,
     "urls": [
         "https://www.planszomania.pl/szukaj?q=magic+booster",
         "https://www.planszomania.pl/szukaj?q=magic+commander",
         "https://www.planszomania.pl/szukaj?q=magic+bundle",
         "https://www.planszomania.pl/szukaj?q=magic+foundations",
     ]},
    {"name": "Geek Up", "base_url": "https://geekup.pl", "require_magic_word": True,
     "urls": ["https://geekup.pl/pl/searchquery/magic+booster/1/phot/5", "https://geekup.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Gry Bez Prądu", "base_url": "https://grybezpradu.eu", "require_magic_word": True,
     "urls": ["https://grybezpradu.eu/pl/searchquery/magic+booster/1/phot/5", "https://grybezpradu.eu/pl/searchquery/magic+commander/1/phot/5"]},
    # --- Poprawione silniki Shoper dla nowych sklepów ---
    {"name": "Gralnia.org", "base_url": "https://gralnia.org", "require_magic_word": True,
     "urls": ["https://gralnia.org/pl/searchquery/magic+booster/1/phot/5", "https://gralnia.org/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Skład Gier", "base_url": "https://skladgier.pl", "require_magic_word": True,
     "urls": ["https://skladgier.pl/pl/searchquery/magic+booster/1/phot/5", "https://skladgier.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Planszolek", "base_url": "https://planszolek.pl", "require_magic_word": True,
     "urls": ["https://planszolek.pl/pl/searchquery/magic+booster/1/phot/5", "https://planszolek.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "Bluegames", "base_url": "https://bluegames.pl", "require_magic_word": True,
     "urls": ["https://bluegames.pl/pl/searchquery/magic+booster/1/phot/5", "https://bluegames.pl/pl/searchquery/magic+commander/1/phot/5"]},
    {"name": "TCGlove", "base_url": "https://www.tcglove.pl", "require_magic_word": True,
     "urls": ["https://www.tcglove.pl/pl/searchquery/magic+booster/1/phot/5", "https://www.tcglove.pl/pl/searchquery/magic+commander/1/phot/5"]},
]

BLACKLIST_WORDS = [
    "set booster", "draft booster", "school of mages",
    "sample pack", "sample", "promo pack", "welcome deck", "art series",
    "koszulki", "sleeves", "album", "segregator", "mata do gry", "playmat",
    "deck box", "deckbox", "pudełko na karty", "kości", "dice",
    "token", "singiel", "singli", "karta pojedyncza", "puste", "pusty", "ultra pro", "dragon shield",
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
    """Wyciąga aktualną cenę brutto produktu z pominięciem starych cen, netto, Omnibus i dostawy."""
    card_copy = BeautifulSoup(str(card_soup), "html.parser")
    for tag in card_copy.select("del, s, .old-price, .regular-price, .price-old, .omnibus, .lowest-price"):
        tag.decompose()

    # 1. Priorytet: dedykowane znaczniki aktualnej ceny
    price_els = card_copy.select(
        ".current-price, .price-new, .special-price, ins .woocommerce-Price-amount, "
        ".woocommerce-Price-amount, .price, .product-price"
    )
    for el in price_els:
        el_text = el.get_text(" ", strip=True)
        if any(skip in el_text.lower() for skip in ["30 dni", "najniższa", "/ szt", "/szt", "dostaw", "netto"]):
            continue
        el_matches = re.findall(r"(\d[\d\s\xa0]*[.,]\d{2})\s*(?:zł|pln)", el_text, flags=re.IGNORECASE)
        el_values = []
        for m in el_matches:
            cleaned = m.replace(" ", "").replace("\xa0", "").replace(",", ".")
            try:
                val = float(cleaned)
                if 5.0 <= val <= 10000.0:
                    el_values.append(val)
            except ValueError:
                pass
        if el_values:
            return min(el_values)

    # 2. Fallback: tekst kafelka po wycięciu fraz Omnibus, dostawy, rat, netto i ceny za sztukę
    text = card_copy.get_text(" ", strip=True)
    text = re.sub(r"(?:najniższa cena|z 30 dni|dostawa|rata).*?\d+[.,]\d{2}\s*(?:zł|pln)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d[\d\s\xa0]*[.,]\d{2}\s*(?:zł|pln)\s*netto", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\([^)]*\d+[.,]\d{2}\s*(?:zł|pln)\s*/\s*szt[^)]*\)", "", text, flags=re.IGNORECASE)

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
    """Rozpoznaje dokładny typ produktu sealed oraz konkretną talię Commander Deck."""
    t = title.lower()
    is_box = ("box" in t or "display" in t)

    if "starter collection" in t:
        return "starter_collection"
    if "draft night" in t:
        return "draft_night"
    if "scene box" in t:
        return "scene_box"
    if "beginner box" in t:
        return "beginner_box"
    if "jumpstart" in t and is_box:
        return "jumpstart_box"
    if "jumpstart" in t:
        return "jumpstart_booster"
    if "collector" in t and is_box:
        return "collector_box"
    if "collector" in t and ("booster" in t or "pack" in t):
        return "collector_booster"
    if "bundle" in t:
        return "bundle"
    if "prerelease" in t:
        return "prerelease"

    # Najpierw sprawdzamy konkretne nazwy talii Commander Deck
    for kw_list, cmd_key in COMMANDER_DECK_KEYWORDS:
        if any(kw in t for kw in kw_list):
            return cmd_key

    # Ogólny Commander Deck (gdy sklep nie podał w nazwie konkretnej talii)
    if "commander" in t:
        return "commander_generic"

    if (is_box and "booster" in t) or "play box" in t or "play display" in t:
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
    """Zwraca listę okazji oraz łączną liczbę znalezionych kafelków produktów na stronie."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_in_page = set()

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

        full_url = urljoin(base_url, href).split("#")[0]
        if full_url in seen_in_page:
            continue
        seen_in_page.add(full_url)

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

        results.append({
            "id": full_url,
            "store": store_name,
            "title": title,
            "price": current_price,
            "reason": reason,
            "url": full_url,
        })

    return results, len(cards)


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
            res.encoding = res.apparent_encoding or "utf-8"
            return res, "direct"
        if res.status_code == 404:
            return None, None
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
            res.encoding = res.apparent_encoding or "utf-8"
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
    total_cards_found = 0
    store_deals = []

    for url in store["urls"]:
        res, mode = fetch_direct_or_scraperapi(session, url, timeout=10)
        if not res or res.status_code != 200:
            continue

        store_responded = True
        if mode == "scraperapi":
            used_scraperapi = True
        deals, cards_count = parse_store_page(store_name, base_url, res.text, require_magic)
        total_cards_found += cards_count
        store_deals.extend(deals)
        time.sleep(0.3)

    return store_name, store_responded, used_scraperapi, total_cards_found, store_deals


def scan_polish_stores(seen_offers):
    new_found = 0
    working_direct = []
    working_api = []
    empty_stores = []
    failed_stores = []
    all_deals = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scan_single_store, store) for store in POLISH_STORES]
        for future in as_completed(futures):
            store_name, responded, used_api, cards_count, deals = future.result()
            if not responded:
                failed_stores.append(store_name)
            elif cards_count == 0:
                empty_stores.append(store_name)
                print(f"[PUSTE WYNIKI] {store_name}: strona 200 OK, ale 0 kafelków produktów")
            else:
                label = f"{store_name} ({cards_count})"
                if used_api:
                    working_api.append(label)
                else:
                    working_direct.append(label)
                all_deals.extend(deals)

    for deal in all_deals:
        offer_key = f"{deal['id']}_{deal['price']}"
        if offer_key in seen_offers:
            continue

        msg = (
            f"🔥 <b>Okazja MTG Sealed — {deal['store']}!</b>\n\n"
            f"📦 <b>{deal['title']}</b>\n"
            f"💰 Cena: <b>{deal['price']:.2f} zł</b>\n"
            f"🔗 <a href='{deal['url']}'>Przejdź do sklepu</a>"
        )
        print(f"[OKAZJA] {deal['store']} | {deal['title']} | {deal['price']} zł")
        if send_telegram_text(msg):
            seen_offers.add(offer_key)
            new_found += 1
            time.sleep(0.5)

    return new_found, sorted(working_direct), sorted(working_api), sorted(empty_stores), sorted(failed_stores)


def run_once():
    mode_info = "z ScraperAPI PL" if SCRAPER_API_KEY else "bez klucza ScraperAPI"
    print(f"Skanuję {len(POLISH_STORES)} polskich sklepów ({mode_info})...")
    seen = load_seen_offers()
    found, direct_ok, api_ok, empty_ok, failed = scan_polish_stores(seen)
    save_seen_offers(seen)

    total_with_products = len(direct_ok) + len(api_ok)

    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        direct_list = ", ".join(direct_ok) if direct_ok else "brak"
        api_list = ", ".join(api_ok) if api_ok else "brak"
        empty_list = ", ".join(empty_ok) if empty_ok else "brak"
        fail_list = ", ".join(failed) if failed else "brak"
        send_telegram_text(
            f"✅ <b>Skanowanie zakończone!</b>\n"
            f"🏪 Sklepy z produktami: <b>{total_with_products}/{len(POLISH_STORES)}</b>\n\n"
            f"🟢 <b>Bezpośrednio ({len(direct_ok)}):</b> {direct_list}\n\n"
            f"🇵🇱 <b>Przez ScraperAPI PL ({len(api_ok)}):</b> {api_list}\n\n"
            f"⚠️ <b>Otwarte, ale 0 produktów ({len(empty_ok)}):</b> {empty_list}\n\n"
            f"🔴 <b>Niedostępne ({len(failed)}):</b> {fail_list}\n\n"
            f"🔥 <b>Nowych okazji:</b> {found}"
        )

    print(
        f"Zakończono. Z produktami: {total_with_products}/{len(POLISH_STORES)} "
        f"| Puste (0 prod.): {len(empty_ok)} | Niedostępne: {len(failed)} | Nowe okazje: {found}"
    )


if __name__ == "__main__":
    try:
        run_once()
    except Exception as err:
        send_telegram_text(f"❌ <b>Błąd krytyczny bota:</b> {err}")
        raise
