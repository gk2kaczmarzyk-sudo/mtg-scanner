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

# Progi ustawione ok. 10-15% poniżej standardowych cen w polskich sklepach
SET_PRICE_RULES = [
    {
        "set_name": "Marvel Darklord Destiny",
        "keywords": ["darklord destiny", "marvel darklord"],
        "prices": {
            "play_booster": 16,
            "play_box": 430,
            "collector_booster": 130,
            "collector_box": 1380,
            "bundle": 185,
            "prerelease": 105,
            "draft_night": 270,
            "scene_box": 100,
            "commander_generic": 130,
            "collector_commander_generic": 400,
        },
    },
    {
        "set_name": "Nauctic",
        "keywords": ["nauctic", "nautic"],
        "prices": {
            "play_booster": 16,
            "play_box": 420,
            "collector_booster": 115,
            "collector_box": 1220,
            "bundle": 175,
            "prerelease": 100,
            "draft_night": 265,
            "commander_generic": 125,
            "collector_commander_generic": 370,
        },
    },
    {
        "set_name": "Final Fantasy",
        "keywords": ["final fantasy"],
        "prices": {
            "play_booster": 19,
            "play_box": 490,
            "collector_booster": 150,
            "collector_box": 1580,
            "bundle": 210,
            "prerelease": 115,
            "scene_box": 105,
            # Zwykłe Commander Decki
            "cmd_scions_spellcraft": 185,
            "cmd_limit_break": 175,
            "cmd_counter_blitz": 155,
            "cmd_revival_trance": 145,
            "commander_generic": 145,
            # Collector's Commander Decki
            "collector_cmd_scions_spellcraft": 480,
            "collector_cmd_limit_break": 460,
            "collector_cmd_counter_blitz": 430,
            "collector_cmd_revival_trance": 420,
            "collector_commander_generic": 420,
        },
    },
    {
        "set_name": "Bloomburrow",
        "keywords": ["bloomburrow"],
        "prices": {
            "play_booster": 16,
            "play_box": 420,
            "collector_booster": 110,
            "collector_box": 1180,
            "bundle": 175,
            "prerelease": 100,
            # Zwykłe Commander Decki
            "cmd_squirreled_away": 165,
            "cmd_animated_army": 140,
            "cmd_peace_offering": 130,
            "cmd_family_matters": 120,
            "commander_generic": 120,
        },
    },
    {
        "set_name": "Foundations",
        "keywords": ["foundations"],
        "prices": {
            "play_booster": 16,
            "play_box": 420,
            "collector_booster": 110,
            "collector_box": 1200,
            "jumpstart_booster": 16,
            "jumpstart_box": 335,
            "bundle": 160,
            "prerelease": 95,
            "beginner_box": 100,
            "starter_collection": 190,
            # Zwykłe Commander Decki
            "cmd_calling_all_angels": 105,
            "cmd_keen_engineering": 105,
            "cmd_wretched_ranks": 105,
            "cmd_reign_of_dragons": 105,
            "cmd_tramplesaurus_rex": 105,
            "commander_generic": 105,
            # Collector's Commander Decki
            "collector_cmd_calling_all_angels": 340,
            "collector_cmd_keen_engineering": 340,
            "collector_cmd_wretched_ranks": 340,
            "collector_cmd_reign_of_dragons": 340,
            "collector_cmd_tramplesaurus_rex": 340,
            "collector_commander_generic": 340,
        },
    },
    {
        "set_name": "Edge of Eternities",
        "keywords": ["edge of eternities"],
        "prices": {
            "play_booster": 17,
            "play_box": 490,
            "collector_booster": 165,
            "collector_box": 1750,
            "bundle": 220,
            "prerelease": 105,
            # Zwykłe Commander Decki
            "cmd_world_shaper": 165,
            "cmd_counter_intelligence": 130,
            "commander_generic": 130,
            # Collector's Commander Decki
            "collector_cmd_world_shaper": 390,
            "collector_cmd_counter_intelligence": 360,
            "collector_commander_generic": 360,
        },
    },
    {
        "set_name": "Marvel's Spider-Man",
        "keywords": ["spider-man", "spiderman"],
        "prices": {
            "play_booster": 17,
            "play_box": 450,
            "collector_booster": 110,
            "collector_box": 1180,
            "bundle": 175,
            "prerelease": 110,
            "scene_box": 100,
        },
    },
    {
        "set_name": "Avatar: The Last Airbender",
        "keywords": ["avatar"],
        "prices": {
            "play_booster": 17,
            "play_box": 420,
            "collector_booster": 125,
            "collector_box": 1280,
            "bundle": 195,
            "prerelease": 115,
            "beginner_box": 100,
            "scene_box": 125,
        },
    },
    {
        "set_name": "Lorwyn Eclipsed",
        "keywords": ["lorwyn"],
        "prices": {
            "play_booster": 17,
            "play_box": 425,
            "collector_booster": 110,
            "collector_box": 1180,
            "bundle": 180,
            "prerelease": 105,
            "draft_night": 290,
            # Zwykłe Commander Decki
            "cmd_dance_of_the_elements": 135,
            "cmd_blight_curse": 120,
            "commander_generic": 120,
            # Collector's Commander Decki
            "collector_cmd_dance_of_the_elements": 360,
            "collector_cmd_blight_curse": 340,
            "collector_commander_generic": 340,
        },
    },
    {
        "set_name": "Teenage Mutant Ninja Turtles",
        "keywords": ["ninja turtles", "tmnt"],
        "prices": {
            "play_booster": 14,
            "play_box": 340,
            "collector_booster": 100,
            "collector_box": 1130,
            "bundle": 135,
            "prerelease": 80,
            "draft_night": 235,
            # Zwykłe Commander Decki
            "cmd_turtle_power": 120,
            "commander_generic": 120,
            # Collector's Commander Decki
            "collector_cmd_turtle_power": 350,
            "collector_commander_generic": 350,
        },
    },
    {
        "set_name": "Secrets of Strixhaven",
        "keywords": ["strixhaven"],
        "prices": {
            "play_booster": 15,
            "play_box": 425,
            "collector_booster": 125,
            "collector_box": 1360,
            "bundle": 140,
            "prerelease": 95,
            "draft_night": 260,
            # Zwykłe Commander Decki
            "cmd_silverquill_influence": 185,
            "cmd_witherbloom_pestilence": 155,
            "cmd_prismari_artistry": 125,
            "cmd_lorehold_spirit": 125,
            "cmd_quandrix_unlimited": 120,
            "commander_generic": 120,
            # Collector's Commander Decki
            "collector_cmd_silverquill_influence": 410,
            "collector_cmd_witherbloom_pestilence": 380,
            "collector_cmd_prismari_artistry": 350,
            "collector_cmd_lorehold_spirit": 350,
            "collector_cmd_quandrix_unlimited": 340,
            "collector_commander_generic": 340,
        },
    },
    {
        "set_name": "Marvel Super Heroes",
        "keywords": ["marvel"],
        "prices": {
            "play_booster": 15,
            "play_box": 370,
            "collector_booster": 125,
            "collector_box": 1320,
            "bundle": 135,
            "prerelease": 85,
            "draft_night": 245,
            "scene_box": 75,
            # Zwykłe Commander Decki
            "cmd_doom_prevails": 190,
            "cmd_avengers_assemble": 145,
            "cmd_wakanda_forever": 135,
            "cmd_fantastic_four": 115,
            "commander_generic": 115,
            # Collector's Commander Decki
            "collector_cmd_doom_prevails": 430,
            "collector_cmd_avengers_assemble": 360,
            "collector_cmd_wakanda_forever": 350,
            "collector_cmd_fantastic_four": 350,
            "collector_commander_generic": 350,
        },
    },
    {
        "set_name": "The Hobbit",
        "keywords": ["hobbit"],
        "prices": {
            "play_booster": 15,
            "play_box": 415,
            "collector_booster": 140,
            "collector_box": 1360,
            "bundle": 170,
            "prerelease": 105,
            "draft_night": 280,
            "scene_box": 100,
        },
    },
    {
        "set_name": "Reality Fracture",
        "keywords": ["reality fracture"],
        "prices": {
            "play_booster": 15,
            "play_box": 390,
            "collector_booster": 110,
            "collector_box": 1130,
            "bundle": 140,
            "prerelease": 90,
            "draft_night": 255,
            # Zwykłe Commander Decki
            "cmd_multiverse_reforged": 165,
            "commander_generic": 165,
            # Collector's Commander Decki
            "collector_cmd_multiverse_reforged": 390,
            "collector_commander_generic": 390,
        },
    },
    {
        "set_name": "Star Trek",
        "keywords": ["star trek"],
        "prices": {
            "play_booster": 15,
            "play_box": 375,
            "collector_booster": 125,
            "collector_box": 1270,
            "bundle": 150,
            "prerelease": 95,
            "draft_night": 260,
            "scene_box": 105,
            # Zwykłe Commander Decki
            "cmd_we_are_the_borg": 220,
            "cmd_landing_party": 165,
            "cmd_federation_fleet": 130,
            "cmd_klingon_fury": 130,
            "commander_generic": 130,
            # Collector's Commander Decki
            "collector_cmd_we_are_the_borg": 490,
            "collector_cmd_landing_party": 440,
            "collector_cmd_federation_fleet": 440,
            "collector_cmd_klingon_fury": 440,
            "collector_commander_generic": 440,
        },
    },
]

COMMANDER_DECK_KEYWORDS = [
    # Final Fantasy
    (["scions & spellcraft", "scions and spellcraft"], "cmd_scions_spellcraft"),
    (["limit break"], "cmd_limit_break"),
    (["counter blitz"], "cmd_counter_blitz"),
    (["revival trance"], "cmd_revival_trance"),
    # Bloomburrow
    (["squirreled away"], "cmd_squirreled_away"),
    (["animated army"], "cmd_animated_army"),
    (["peace offering"], "cmd_peace_offering"),
    (["family matters"], "cmd_family_matters"),
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
    "play_box": "Play Booster Box / Display",
    "collector_booster": "Collector Booster",
    "collector_box": "Collector Booster Box",
    "bundle": "Bundle",
    "prerelease": "Prerelease Pack",
    "draft_night": "Draft Night",
    "scene_box": "Scene Box",
    "beginner_box": "Beginner Box",
    # Zwykłe Commander Decki
    "commander_generic": "Commander Deck (zwykły — ogólny)",
    "cmd_scions_spellcraft": "Commander Deck (zwykły) — Scions & Spellcraft",
    "cmd_limit_break": "Commander Deck (zwykły) — Limit Break",
    "cmd_counter_blitz": "Commander Deck (zwykły) — Counter Blitz",
    "cmd_revival_trance": "Commander Deck (zwykły) — Revival Trance",
    "cmd_squirreled_away": "Commander Deck (zwykły) — Squirreled Away",
    "cmd_animated_army": "Commander Deck (zwykły) — Animated Army",
    "cmd_peace_offering": "Commander Deck (zwykły) — Peace Offering",
    "cmd_family_matters": "Commander Deck (zwykły) — Family Matters",
    "cmd_calling_all_angels": "Commander Deck (zwykły) — Calling All Angels",
    "cmd_keen_engineering": "Commander Deck (zwykły) — Keen Engineering",
    "cmd_wretched_ranks": "Commander Deck (zwykły) — Wretched Ranks",
    "cmd_reign_of_dragons": "Commander Deck (zwykły) — Reign of Dragons",
    "cmd_tramplesaurus_rex": "Commander Deck (zwykły) — Tramplesaurus Rex",
    "cmd_world_shaper": "Commander Deck (zwykły) — World Shaper",
    "cmd_counter_intelligence": "Commander Deck (zwykły) — Counter Intelligence",
    "cmd_dance_of_the_elements": "Commander Deck (zwykły) — Dance of the Elements",
    "cmd_blight_curse": "Commander Deck (zwykły) — Blight Curse",
    "cmd_turtle_power": "Commander Deck (zwykły) — Turtle Power!",
    "cmd_silverquill_influence": "Commander Deck (zwykły) — Silverquill Influence",
    "cmd_witherbloom_pestilence": "Commander Deck (zwykły) — Witherbloom Pestilence",
    "cmd_prismari_artistry": "Commander Deck (zwykły) — Prismari Artistry",
    "cmd_lorehold_spirit": "Commander Deck (zwykły) — Lorehold Spirit",
    "cmd_quandrix_unlimited": "Commander Deck (zwykły) — Quandrix Unlimited",
    "cmd_doom_prevails": "Commander Deck (zwykły) — Doom Prevails",
    "cmd_avengers_assemble": "Commander Deck (zwykły) — Avengers Assemble",
    "cmd_wakanda_forever": "Commander Deck (zwykły) — Wakanda Forever",
    "cmd_fantastic_four": "Commander Deck (zwykły) — The Fantastic Four",
    "cmd_multiverse_reforged": "Commander Deck (zwykły) — Multiverse Reforged",
    "cmd_we_are_the_borg": "Commander Deck (zwykły) — We Are the Borg",
    "cmd_landing_party": "Commander Deck (zwykły) — Landing Party",
    "cmd_federation_fleet": "Commander Deck (zwykły) — Federation Fleet",
    "cmd_klingon_fury": "Commander Deck (zwykły) — Klingon Fury",
    # Collector's Commander Decki
    "collector_commander_generic": "Collector's Commander Deck (ogólny)",
    "collector_cmd_scions_spellcraft": "Collector's Commander Deck — Scions & Spellcraft",
    "collector_cmd_limit_break": "Collector's Commander Deck — Limit Break",
    "collector_cmd_counter_blitz": "Collector's Commander Deck — Counter Blitz",
    "collector_cmd_revival_trance": "Collector's Commander Deck — Revival Trance",
    "collector_cmd_calling_all_angels": "Collector's Commander Deck — Calling All Angels",
    "collector_cmd_keen_engineering": "Collector's Commander Deck — Keen Engineering",
    "collector_cmd_wretched_ranks": "Collector's Commander Deck — Wretched Ranks",
    "collector_cmd_reign_of_dragons": "Collector's Commander Deck — Reign of Dragons",
    "collector_cmd_tramplesaurus_rex": "Collector's Commander Deck — Tramplesaurus Rex",
    "collector_cmd_world_shaper": "Collector's Commander Deck — World Shaper",
    "collector_cmd_counter_intelligence": "Collector's Commander Deck — Counter Intelligence",
    "collector_cmd_dance_of_the_elements": "Collector's Commander Deck — Dance of the Elements",
    "collector_cmd_blight_curse": "Collector's Commander Deck — Blight Curse",
    "collector_cmd_turtle_power": "Collector's Commander Deck — Turtle Power!",
    "collector_cmd_silverquill_influence": "Collector's Commander Deck — Silverquill Influence",
    "collector_cmd_witherbloom_pestilence": "Collector's Commander Deck — Witherbloom Pestilence",
    "collector_cmd_prismari_artistry": "Collector's Commander Deck — Prismari Artistry",
    "collector_cmd_lorehold_spirit": "Collector's Commander Deck — Lorehold Spirit",
    "collector_cmd_quandrix_unlimited": "Collector's Commander Deck — Quandrix Unlimited",
    "collector_cmd_doom_prevails": "Collector's Commander Deck — Doom Prevails",
    "collector_cmd_avengers_assemble": "Collector's Commander Deck — Avengers Assemble",
    "collector_cmd_wakanda_forever": "Collector's Commander Deck — Wakanda Forever",
    "collector_cmd_fantastic_four": "Collector's Commander Deck — The Fantastic Four",
    "collector_cmd_multiverse_reforged": "Collector's Commander Deck — Multiverse Reforged",
    "collector_cmd_we_are_the_borg": "Collector's Commander Deck — We Are the Borg",
    "collector_cmd_landing_party": "Collector's Commander Deck — Landing Party",
    "collector_cmd_federation_fleet": "Collector's Commander Deck — Federation Fleet",
    "collector_cmd_klingon_fury": "Collector's Commander Deck — Klingon Fury",
}
POLISH_STORES = [
    {"name": "Strefa MTG", "base_url": "https://strefamtg.pl", "require_magic_word": False,
     "urls": [
         "https://strefamtg.pl/4-magic-the-gathering?resultsPerPage=160",
         "https://strefamtg.pl/4-magic-the-gathering?resultsPerPage=160&page=2",
         "https://strefamtg.pl/4-magic-the-gathering?resultsPerPage=160&page=3",
         "https://strefamtg.pl/4-magic-the-gathering?resultsPerPage=160&page=4",
     ]},
    {"name": "Centrum MTG", "base_url": "https://www.centrum-mtg.com.pl", "require_magic_word": False,
     "urls": [
         "https://www.centrum-mtg.com.pl/magic-the-gathering",
         "https://www.centrum-mtg.com.pl/magic-the-gathering?page=2",
     ]},
    {"name": "Time4Magic", "base_url": "https://time4magic.pl", "require_magic_word": False,
     "urls": [
         "https://time4magic.pl/pl/c/Nauctis-The-Sunken-Realm/181",
         "https://time4magic.pl/star-trek-magic-the-gathering",
         "https://time4magic.pl/reality-fracture-magic-the-gathering",
         "https://time4magic.pl/the-hobbit-magic-the-gathering",
         "https://time4magic.pl/marvel-super-heroes-magic-the-gathering",
         "https://time4magic.pl/secrets-of-strixhaven-magic-the-gathering",
         "https://time4magic.pl/teenage-mutant-ninja-turtles-magic-the-gathering",
         "https://time4magic.pl/lorwyn-eclipsed-magic-the-gathering",
         "https://time4magic.pl/pl/c/Magic-the-Gathering-FINAL-FANTASY-Holiday-Release/101",
         "https://time4magic.pl/avatar-the-last-airbender-magic-the-gathering",
         "https://time4magic.pl/marvels-spiderman-magic-the-gathering",
         "https://time4magic.pl/edge-of-eternities-magic-the-gathering",
         "https://time4magic.pl/final-fantasy-magic-the-gathering",
         "https://time4magic.pl/bloomburrow-magic-the-gathering",
     ]},
    {"name": "Card Dojo", "base_url": "https://carddojo.pl", "require_magic_word": False,
     "urls": [
         "https://carddojo.pl/pl/c/Magic-the-Gathering/43",
         "https://carddojo.pl/pl/c/Magic-the-Gathering/43/2",
     ]},
    {"name": "Sklep Merfolk", "base_url": "https://sklep.merfolk.pl", "require_magic_word": False,
     "urls": [
         "https://sklep.merfolk.pl/category/BOOSTERY-I-BOXY-MTG-343892#OfertaProduktowa",
         "https://sklep.merfolk.pl/category/GOTOWE-TALIE-MTG-343882#OfertaProduktowa",
         "https://sklep.merfolk.pl/category/ZESTAWY-KART-MTG-343880#OfertaProduktowa",
     ]},
    {"name": "Dragonus", "base_url": "https://dragonus.pl", "require_magic_word": False,
     "urls": [
         "https://dragonus.pl/pl/searchquery/magic+booster/1/phot/5",
         "https://dragonus.pl/pl/searchquery/magic+commander/1/phot/5",
         "https://dragonus.pl/pl/searchquery/magic+bundle/1/phot/5",
         "https://dragonus.pl/pl/searchquery/magic+foundations/1/phot/5",
     ]},
    {"name": "Zgrani.pl", "base_url": "https://zgrani.pl", "require_magic_word": False,
     "urls": ["https://zgrani.pl/pl/menu/magic-the-gathering/boostery-157",
              "https://zgrani.pl/pl/menu/magic-the-gathering/gotowe-talie-168",
              "https://zgrani.pl/pl/menu/magic-the-gathering/kolekcje-i-zestawy-kart-301",
    ]},
    {"name": "Sklep Graal", "base_url": "https://sklep-graal.pl", "require_magic_word": False,
     "urls": ["https://sklep-graal.pl/pl/c/Bundle-Zestawy-Kolekcjonerskie/759",
              "https://sklep-graal.pl/pl/c/Boostery/760",
              "https://sklep-graal.pl/pl/c/Talie/766",
              "https://sklep-graal.pl/pl/c/Foundations/897",
              "https://sklep-graal.pl/pl/c/Prerelease-Pack/772",
    ]},
    {"name": "Pan Mysza", "base_url": "https://panmysza.pl", "require_magic_word": False,
     "urls": [
         "https://panmysza.pl/pl/c/Magic-The-Gathering/53",
         "https://panmysza.pl/pl/c/Star-Trek/878/1/full",
         "https://panmysza.pl/pl/c/Reality-Fracture/857/1/full",
         "https://panmysza.pl/pl/c/The-Hobbit/850/1/full",
         "https://panmysza.pl/pl/c/Avatar-The-Last-Airbender/748/1/full",
         "https://panmysza.pl/pl/c/Final-Fantasy/656/1/full",
         "https://panmysza.pl/pl/c/Marvel-Super-Heroes/824/1/full",
         "https://panmysza.pl/pl/c/Marvels-Spider-Man/717/1/full",
         "https://panmysza.pl/pl/c/Secrets-of-Strixhaven/788/1/full",
         "https://panmysza.pl/pl/c/Teenage-Mutant-Ninja-Turtles/769/1/full",
     ]},
    {"name": "Jaskinia Trolla", "base_url": "https://jaskiniatrolla.pl", "require_magic_word": False,
     "urls": [
         "https://jaskiniatrolla.pl/Star-Trek-c703",
         "https://jaskiniatrolla.pl/Reality-Fracture-c697",
         "https://jaskiniatrolla.pl/The-Hobbit-c696",
         "https://jaskiniatrolla.pl/Marvels-Super-Heroes-c693",
         "https://jaskiniatrolla.pl/Secrets-of-Strixhaven-c698",
         "https://jaskiniatrolla.pl/Teenage-Mutant-Ninja-Turtles-c685",
         "https://jaskiniatrolla.pl/Lorwyn-Eclipsed-c686",
         "https://jaskiniatrolla.pl/Avatar-the-Last-Airbender-c682",
         "https://jaskiniatrolla.pl/Marvels-Spiderman-c671",
         "https://jaskiniatrolla.pl/Final-Fantasy-c666",
         "https://jaskiniatrolla.pl/Inne-c588",
     ]},
    {"name": "Xjoy.pl", "base_url": "https://www.xjoy.pl", "require_magic_word": False,
     "urls": [
         "https://www.xjoy.pl/828-star-trek",
         "https://www.xjoy.pl/785-lorwyn-eclipsed",
         "https://www.xjoy.pl/824-reality-fracture",
         "https://www.xjoy.pl/780-avatar-the-last-airbender",
         "https://www.xjoy.pl/812-the-hobbit",
         "https://www.xjoy.pl/747-marvel-s-spider-man",
         "https://www.xjoy.pl/804-marvel-super-heroes",
         "https://www.xjoy.pl/737-final-fantasy",
         "https://www.xjoy.pl/799-secrets-of-strixhaven",
     ]},
    {"name": "Centrum Gier Pegaz", "base_url": "https://pegaz-gry.pl", "require_magic_word": False,
     "urls": [
         "https://pegaz-gry.pl/354-magic-the-gathering-star-trek",
         "https://pegaz-gry.pl/348-magic-the-gathering-reality-fracture",
         "https://pegaz-gry.pl/347-magic-the-gathering-the-hobbit",
         "https://pegaz-gry.pl/337-magic-the-gathering-marvel-super-heroes",
         "https://pegaz-gry.pl/327-magic-the-gathering-secrets-of-strixhaven",
         "https://pegaz-gry.pl/314-magic-the-gathering-lorwyn-eclipsed",
         "https://pegaz-gry.pl/310-magic-the-gathering-avatar-the-last-airbender",
         "https://pegaz-gry.pl/293-marvel-spider-man",
         "https://pegaz-gry.pl/287-mtg-edge-of-eternities-",
         "https://pegaz-gry.pl/278-magic-the-gathering-final-fantasy",
         "https://pegaz-gry.pl/256-mtg-fundations",
         "https://pegaz-gry.pl/251-mtg-bloomburrow",
     ]},
    {"name": "Stajnia Gier", "base_url": "https://stajnia-gier.pl", "require_magic_word": False,
     "urls": [
         "https://stajnia-gier.pl/kategoria/magic-the-gathering",
         "https://stajnia-gier.pl/kategoria/magic-the-gathering?strona=2",
         "https://stajnia-gier.pl/kategoria/magic-the-gathering?strona=3",
         "https://stajnia-gier.pl/kategoria/magic-the-gathering?strona=4",
         "https://stajnia-gier.pl/kategoria/magic-the-gathering?strona=5",
         "https://stajnia-gier.pl/kategoria/magic-the-gathering?strona=6",
         "https://stajnia-gier.pl/kategoria/magic-the-gathering?strona=7",
     ]},
    {"name": "Redraft", "base_url": "https://redraft.pl", "require_magic_word": False,
     "urls": [
         "https://redraft.pl/pl/menu/magic-the-gathering-165.html",
         "https://redraft.pl/pl/menu/magic-the-gathering-165.html?counter=1",
     ]},
    {"name": "Flamberg", "base_url": "https://flamberg.com.pl", "require_magic_word": False,
     "urls": [
         "https://flamberg.com.pl/pl/menu/magic-the-gathering-252?counter=1",
         "https://flamberg.com.pl/pl/menu/magic-the-gathering-252",
     ]},
    {"name": "Rebel.pl", "base_url": "https://www.rebel.pl", "require_magic_word": False,
     "urls": [
         "https://www.rebel.pl/karcianki/55-magic-the-gathering?availability=in-stock&path=7093,the-hobbit",
         "https://www.rebel.pl/karcianki/55-magic-the-gathering?availability=in-stock&path=6936,lorwyn-eclipsed",
         "https://www.rebel.pl/karcianki/55-magic-the-gathering?availability=in-stock&path=6937,secrets-of-strixhaven",
         "https://www.rebel.pl/karcianki/55-magic-the-gathering?availability=in-stock&path=6891,marvel-s-spider-man",
         "https://www.rebel.pl/karcianki/55-magic-the-gathering?availability=in-stock&path=7105,star-trek",
         "https://www.rebel.pl/karcianki/55-magic-the-gathering?availability=in-stock&path=6935,teenage-mutant-ninja-turtles",
         
     ]},
    {"name": "Mepel.pl", "base_url": "https://mepel.pl", "require_magic_word": False,
     "urls": [
         "https://mepel.pl/magic-the-gathering-gra-karciana",
         "https://mepel.pl/magic-the-gathering-gra-karciana/2",
         "https://mepel.pl/magic-the-gathering-gra-karciana/3",
         "https://mepel.pl/magic-the-gathering-gra-karciana/4",
         "https://mepel.pl/magic-the-gathering-gra-karciana/5",
     ]},
    {"name": "Aleplanszówki", "base_url": "https://aleplanszowki.pl", "require_magic_word": False,
     "urls": [
         "https://aleplanszowki.pl/603-magic-the-gathering",
         "https://aleplanszowki.pl/603-magic-the-gathering?page=2"
         "https://aleplanszowki.pl/603-magic-the-gathering?page=3",
     ]},
    {"name": "3Trolle", "base_url": "https://3trolle.pl", "require_magic_word": False,
     "urls": [
         "https://3trolle.pl/66-magic-the-gathering-tcg",
     ]},
    {"name": "Vanaheim", "base_url": "https://vanaheim.pl", "require_magic_word": False,
     "urls": [
         "https://vanaheim.pl/pl/2294-boostery",
         "https://vanaheim.pl/pl/2295-booster-box",
         "https://vanaheim.pl/pl/2296-bundle-i-zestawy",
         "https://vanaheim.pl/pl/1081-mtg-commander",
     ]},
    {"name": "Wargamer", "base_url": "https://sklep.wargamer.pl", "require_magic_word": False,
     "urls": [
         "https://sklep.wargamer.pl/pl/483-final-fantasy",
         "https://sklep.wargamer.pl/pl/482-marvel-s-spider-man",
         "https://sklep.wargamer.pl/pl/526-avatar-the-last-airbender",
         "https://sklep.wargamer.pl/pl/531-lorwyn-eclipsed",
         "https://sklep.wargamer.pl/pl/533-teenage-mutant-ninja-turtles",
         "https://sklep.wargamer.pl/pl/550-secrets-of-strixhaven",
         "https://sklep.wargamer.pl/pl/553-marvel-super-heroes",
         "https://sklep.wargamer.pl/pl/555-the-hobbit",
         "https://sklep.wargamer.pl/pl/571-star-trek",
     ]},
    {"name": "RGFK.pl", "base_url": "https://rgfk.pl", "require_magic_word": False,
     "urls": [
         "https://rgfk.pl/k/52418/karty-mtg?order=product.sales.desc",
         "https://rgfk.pl/k/52418/karty-mtg?order=product.sales.desc&page=2",
         "https://rgfk.pl/k/52418/karty-mtg?order=product.sales.desc&page=3",
     ]},
    {"name": "Gry Bez Prądu", "base_url": "https://grybezpradu.eu", "require_magic_word": False,
     "urls": [
         "https://grybezpradu.eu/magic-the-gathering-tcg",
     ]},
    {"name": "Skład Gier", "base_url": "https://skladgier.pl", "require_magic_word": False,
     "urls": [
         "https://skladgier.pl/collections/mtg-boostery",
         "https://skladgier.pl/collections/mtg-booster-boxy",
         "https://skladgier.pl/collections/mtg-decki",
     ]},
    {"name": "Planszolek", "base_url": "https://planszolek.pl", "require_magic_word": False,
     "urls": [
         "https://www.planszolek.pl/pl/c/Bundle-Pack/211",
         "https://www.planszolek.pl/pl/c/Inne-Zestawy/270",
         "https://www.planszolek.pl/pl/c/Boostery/47",
         "https://www.planszolek.pl/pl/c/Boostery/47/2",
         "https://www.planszolek.pl/pl/c/Booster-Boxy/48",
         "https://www.planszolek.pl/pl/c/Booster-Boxy/48/2",
         "https://www.planszolek.pl/pl/c/Commander-Decki/49",
         "https://www.planszolek.pl/pl/c/Commander-Decki/49/2",
         "https://www.planszolek.pl/pl/c/Gotowe-Talie/50",
     ]},
    {"name": "Bluegames", "base_url": "https://bluegames.pl", "require_magic_word": False,
     "urls": [
         "https://bluegames.pl/gry-karciane-tcg/magic-the-gathering",
     ]},
    {"name": "TCGlove", "base_url": "https://www.tcglove.pl", "require_magic_word": False,
     "urls": [
         "https://www.tcglove.pl/mtg-star-trek-universes-beyond",
         "https://www.tcglove.pl/mtg-reality-fracture",
         "https://www.tcglove.pl/mtg-wladca-pierscieni-hobbit",
         "https://www.tcglove.pl/secrets-of-strixhaven",
         "https://www.tcglove.pl/magic-final-fantasy",
         "https://www.tcglove.pl/mtg-marvel-super-heroes",
     ]},
    {"name": "Hobbity.pl", "base_url": "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering", "require_magic_word": False,
     "urls": [
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=2",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=3",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=4",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=5",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=6",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=7",
         "https://hobbity.pl/gry-karciane-kolekcjonerskie/magic-the-gathering?page=8",
     ]},
    {"name": "MagicznyRynek", "base_url": "https://magicznyrynek.pl/collections/magic-the-gathering/sealed/", "require_magic_word": False,
     "urls": [
         "https://magicznyrynek.pl/collections/magic-the-gathering/sealed/",
         "https://magicznyrynek.pl/collections/magic-the-gathering/sealed/?stock=in-stock&page=2",
         "https://magicznyrynek.pl/collections/magic-the-gathering/sealed/?stock=in-stock&page=3",
         "https://magicznyrynek.pl/collections/magic-the-gathering/sealed/?stock=in-stock&page=4",
     ]},
     {"name": "MagicCafe", "base_url": "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/", "require_magic_word": False,
     "urls": [
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=2",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=3",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=4",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=5",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=6",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=7",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=8",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=9",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=10",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=11",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=12",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=13",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=14",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=15",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=16",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=17",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=18",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=19",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=20",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=21",
         "https://magiccafe.eu/product-category/gry-karciane/magic-the-gathering-pl/?jsf=jet-woo-products-grid&pagenum=22",
     ]},
         
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
    card_copy = BeautifulSoup(str(card_soup), "html.parser")
    for tag in card_copy.select("del, s, .old-price, .regular-price, .price-old, .omnibus, .lowest-price"):
        tag.decompose()

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
    """Rozpoznaje dokładny typ produktu sealed oraz oddzielnie zwykłe i Collector's Commander Decki."""
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

    # Sprawdzamy najpierw talie Commander (z rozróżnieniem na edycję Collector's oraz zwykłą)
    is_collector_variant = any(
        phrase in t
        for phrase in [
            "collector's",
            "collectors",
            "collector edition",
            "collector commander",
            "edycja kolekcjonerska",
        ]
    )
    matched_cmd_key = None
    for kw_list, cmd_key in COMMANDER_DECK_KEYWORDS:
        if any(kw in t for kw in kw_list):
            matched_cmd_key = cmd_key
            break

    if "booster" not in t and (matched_cmd_key or "commander" in t):
        if is_collector_variant:
            return f"collector_{matched_cmd_key}" if matched_cmd_key else "collector_commander_generic"
        return matched_cmd_key if matched_cmd_key else "commander_generic"

    if "collector" in t and is_box:
        return "collector_box"
    if "collector" in t and ("booster" in t or "pack" in t):
        return "collector_booster"
    if "bundle" in t:
        return "bundle"
    if "prerelease" in t:
        return "prerelease"

    if (
        (is_box and ("booster" in t or "play" in t))
        or "play box" in t
        or "play display" in t
        or "booster display" in t
        or "display 36" in t
        or "display (36" in t
    ):
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


def fetch_direct_or_scraperapi(session, url, timeout=20):
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
        res = requests.get("https://api.scraperapi.com/", params=api_params, timeout=35)
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
        res, mode = fetch_direct_or_scraperapi(session, url, timeout=20)
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

        clean_reason = re.sub(r"\s*\(próg:.*?\)", "", deal["reason"])
        msg = (
            f"🔥 <b>Okazja MTG Sealed — {deal['store']}!</b>\n\n"
            f"📦 <b>{deal['title']}</b>\n"
            f"💰 Cena: <b>{deal['price']:.2f} zł</b>\n"
            f"🏷 {clean_reason}\n\n"
            f"🔗 <a href='{deal['url']}'>Przejdź do sklepu</a>"
        )
        print(f"[OKAZJA] {deal['store']} | {deal['title']} | {deal['price']} zł | {deal['reason']}")
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
