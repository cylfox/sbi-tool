"""
PSX SBI Downloader
==================
Identifies PSX CHD files by matching track sizes against DuckStation's discdb.yaml,
then downloads the correct LibCrypt SBI files from psxdatacenter.com and renames them
to match each CHD filename.

Usage:
    py sbi_downloader.py <chd_folder>             # Download SBI files
    py sbi_downloader.py <chd_folder> --dry-run    # Preview matches without downloading

Requirements:
    pip install pyyaml requests py7zr

Dependencies (auto-downloaded on first run):
    - chdman.exe (from MAME via namDHC, GPL-2.0+)
    - discdb.yaml (from DuckStation, CC BY-NC-ND 4.0)
"""

import os
import re
import sys
import subprocess
import tempfile
import shutil
import requests
import py7zr
import yaml

# ── Configuration ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHDMAN = os.path.join(SCRIPT_DIR, "chdman.exe")
DISCDB = os.path.join(SCRIPT_DIR, "discdb.yaml")
SBI_BASE_URL = "https://psxdatacenter.com/"

# ── Auto-download URLs ──
CHDMAN_URL = "https://github.com/umageddon/namDHC/releases/download/v1.13/chdman.exe"
DISCDB_URL = "https://raw.githubusercontent.com/stenzek/duckstation/master/data/resources/discdb.yaml"


def ensure_dependencies():
    """Download chdman.exe and discdb.yaml if they don't exist."""
    if not os.path.isfile(CHDMAN):
        print(f"chdman.exe not found. Downloading from namDHC (MAME)...")
        try:
            resp = requests.get(CHDMAN_URL, timeout=60)
            resp.raise_for_status()
            with open(CHDMAN, "wb") as f:
                f.write(resp.content)
            print(f"  Saved: {CHDMAN} ({len(resp.content) / 1024 / 1024:.1f} MB)")
        except Exception as e:
            print(f"  ERROR: Could not download chdman.exe: {e}")
            print(f"  Please download it manually from: {CHDMAN_URL}")
            sys.exit(1)

    if not os.path.isfile(DISCDB):
        print(f"discdb.yaml not found. Downloading from DuckStation...")
        try:
            resp = requests.get(DISCDB_URL, timeout=60)
            resp.raise_for_status()
            with open(DISCDB, "wb") as f:
                f.write(resp.content)
            print(f"  Saved: {DISCDB} ({len(resp.content) / 1024 / 1024:.1f} MB)")
        except Exception as e:
            print(f"  ERROR: Could not download discdb.yaml: {e}")
            print(f"  Please download it manually from: {DISCDB_URL}")
            sys.exit(1)

    print()


# ── SBI database from psxdatacenter.com/sbifiles.html ──
# Every serial that has a LibCrypt SBI file available, mapped to its download path.
# Multi-disc games have each disc serial pointing to the same archive.
SBI_DB = {
    "SLES-01226": "sbifiles/Actua Ice Hockey 2 (E) [SLES-01226] sbi.7z",
    "SLES-02563": "sbifiles/Anstoss - Premier Manager (G) [SLES-02563] sbi.7z",
    "SCES-01564": "sbifiles/Ape Escape (E) [SCES-01564] sbi.7z",
    "SCES-02028": "sbifiles/Ape Escape (F) [SCES-02028] sbi.7z",
    "SCES-02029": "sbifiles/Ape Escape (G) [SCES-02029] sbi.7z",
    "SCES-02030": "sbifiles/Ape Escape (I) [SCES-02030] sbi.7z",
    "SCES-02031": "sbifiles/Ape Escape (S) [SCES-02031] sbi.7z",
    "SLES-03324": "sbifiles/Asterix - Mega Madness (E) [SLES-03324] sbi.7z",
    "SCES-02366": "sbifiles/Barbie - Aventure Equestre (F) [SCES-02366] sbi.7z",
    "SCES-02365": "sbifiles/Barbie - Race & Ride (E) [SCES-02365] sbi.7z",
    "SCES-02367": "sbifiles/Barbie - Race & Ride (G) [SCES-02367] sbi.7z",
    "SCES-02368": "sbifiles/Barbie - Race & Ride (I) [SCES-02368] sbi.7z",
    "SCES-02369": "sbifiles/Barbie - Race & Ride (S) [SCES-02369] sbi.7z",
    "SCES-02488": "sbifiles/Barbie - Sports Extreme (F) [SCES-02488] sbi.7z",
    "SCES-02487": "sbifiles/Barbie - Super Sports (E) [SCES-02487] sbi.7z",
    "SCES-02489": "sbifiles/Barbie - Super Sports (G) [SCES-02489] sbi.7z",
    "SCES-02490": "sbifiles/Barbie - Super Sports (I) [SCES-02490] sbi.7z",
    "SCES-02491": "sbifiles/Barbie - Super Sports (S) [SCES-02491] sbi.7z",
    "SLES-02977": "sbifiles/BDFL Manager 2001 (G) [SLES-02977] sbi.7z",
    "SLES-03605": "sbifiles/BDFL Manager 2002 (G) [SLES-03605] sbi.7z",
    "SLES-02293": "sbifiles/Canal+ Premier Manager (F)(S)(I) [SLES-02293] sbi.7z",
    "SCES-02834": "sbifiles/Crash Bash (E)(F)(G)(I)(S) [SCES-02834] sbi.7z",
    "SCES-02105": "sbifiles/CTR - Crash Team Racing (E)(F)(G)(I)(S) (No EDC) [SCES-02105] sbi.7z",
    "SLES-02207": "sbifiles/Dino Crisis (E) [SLES-02207] sbi.7z",
    "SLES-02208": "sbifiles/Dino Crisis (F) [SLES-02208] sbi.7z",
    "SLES-02209": "sbifiles/Dino Crisis (G) [SLES-02209] sbi.7z",
    "SLES-02210": "sbifiles/Dino Crisis (I) [SLES-02210] sbi.7z",
    "SLES-02211": "sbifiles/Dino Crisis (S) [SLES-02211] sbi.7z",
    "SLES-03189": "sbifiles/Disney's 102 Dalmatians - Puppies to the Rescue (E) [SLES-03189] sbi.7z",
    "SLES-03191": "sbifiles/Disney's 102 Dalmatians - Puppies to the Rescue (F)(G)(S)(I)(Du) [SLES-03191] sbi.7z",
    "SCES-02006": "sbifiles/Disney Libro Animato Creativo - Mulan (I) [SCES-02006] sbi.7z",
    "SCES-02005": "sbifiles/Disney's Mulan (G) [SCES-02005] sbi.7z",
    "SCES-02007": "sbifiles/Disney's Mulan (S) [SCES-02007] sbi.7z",
    "SCES-01695": "sbifiles/Disney's Story Studio - Mulan (E) [SCES-01695] sbi.7z",
    "SCES-01431": "sbifiles/Disney's Tarzan (E) [SCES-01431] sbi.7z",
    "SCES-02185": "sbifiles/Disney's Tarzan (Du) [SCES-02185] sbi.7z",
    "SCES-01516": "sbifiles/Disney's Tarzan (F) [SCES-01516] sbi.7z",
    "SCES-01517": "sbifiles/Disney's Tarzan (G) [SCES-01517] sbi.7z",
    "SCES-01518": "sbifiles/Disney's Tarzan (I) [SCES-01518] sbi.7z",
    "SCES-01519": "sbifiles/Disney's Tarzan (S) [SCES-01519] sbi.7z",
    "SCES-02182": "sbifiles/Disney's Tarzan (Sw) [SCES-02182] sbi.7z",
    "SCES-02264": "sbifiles/Disney's Verhalenstudio - Mulan (Du) [SCES-02264] sbi.7z",
    "SLES-02538": "sbifiles/EA Sports Superbike 2000 (E)(F)(G)(I)(S)(Sw) [SLES-02538] sbi.7z",
    "SLES-01715": "sbifiles/Eagle One - Harrier Attack (E)(F)(G)(I)(S) [SLES-01715] sbi.7z",
    "SCES-01704": "sbifiles/Esto es Futbol (S) [SCES-01704] sbi.7z",
    "SLES-02722": "sbifiles/F1 2000 (E)(F)(G)(Du) [SLES-02722] sbi.7z",
    "SLES-02724": "sbifiles/F1 2000 (I) [SLES-02724] sbi.7z",
    # Final Fantasy IX (all disc serials)
    "SLES-02965": "sbifiles/Final Fantasy IX (E) [SLES-02965] sbi.7z",
    "SLES-12965": "sbifiles/Final Fantasy IX (E) [SLES-02965] sbi.7z",
    "SLES-22965": "sbifiles/Final Fantasy IX (E) [SLES-02965] sbi.7z",
    "SLES-32965": "sbifiles/Final Fantasy IX (E) [SLES-02965] sbi.7z",
    "SLES-02966": "sbifiles/Final Fantasy IX (F) [SLES-02966] sbi.7z",
    "SLES-12966": "sbifiles/Final Fantasy IX (F) [SLES-02966] sbi.7z",
    "SLES-22966": "sbifiles/Final Fantasy IX (F) [SLES-02966] sbi.7z",
    "SLES-32966": "sbifiles/Final Fantasy IX (F) [SLES-02966] sbi.7z",
    "SLES-02967": "sbifiles/Final Fantasy IX (G) [SLES-02967] sbi.7z",
    "SLES-12967": "sbifiles/Final Fantasy IX (G) [SLES-02967] sbi.7z",
    "SLES-22967": "sbifiles/Final Fantasy IX (G) [SLES-02967] sbi.7z",
    "SLES-32967": "sbifiles/Final Fantasy IX (G) [SLES-02967] sbi.7z",
    "SLES-02968": "sbifiles/Final Fantasy IX (I) [SLES-02968] sbi.7z",
    "SLES-12968": "sbifiles/Final Fantasy IX (I) [SLES-02968] sbi.7z",
    "SLES-22968": "sbifiles/Final Fantasy IX (I) [SLES-02968] sbi.7z",
    "SLES-32968": "sbifiles/Final Fantasy IX (I) [SLES-02968] sbi.7z",
    "SLES-02969": "sbifiles/Final Fantasy IX (S) [SLES-02969] sbi.7z",
    "SLES-12969": "sbifiles/Final Fantasy IX (S) [SLES-02969] sbi.7z",
    "SLES-22969": "sbifiles/Final Fantasy IX (S) [SLES-02969] sbi.7z",
    "SLES-32969": "sbifiles/Final Fantasy IX (S) [SLES-02969] sbi.7z",
    # Final Fantasy VIII (all disc serials)
    "SLES-02080": "sbifiles/Final Fantasy VIII (E) [SLES-02080] sbi.7z",
    "SLES-12080": "sbifiles/Final Fantasy VIII (E) [SLES-02080] sbi.7z",
    "SLES-22080": "sbifiles/Final Fantasy VIII (E) [SLES-02080] sbi.7z",
    "SLES-32080": "sbifiles/Final Fantasy VIII (E) [SLES-02080] sbi.7z",
    "SLES-02081": "sbifiles/Final Fantasy VIII (F) [SLES-02081] sbi.7z",
    "SLES-12081": "sbifiles/Final Fantasy VIII (F) [SLES-02081] sbi.7z",
    "SLES-22081": "sbifiles/Final Fantasy VIII (F) [SLES-02081] sbi.7z",
    "SLES-32081": "sbifiles/Final Fantasy VIII (F) [SLES-02081] sbi.7z",
    "SLES-02082": "sbifiles/Final Fantasy VIII (G) [SLES-02082] sbi.7z",
    "SLES-12082": "sbifiles/Final Fantasy VIII (G) [SLES-02082] sbi.7z",
    "SLES-22082": "sbifiles/Final Fantasy VIII (G) [SLES-02082] sbi.7z",
    "SLES-32082": "sbifiles/Final Fantasy VIII (G) [SLES-02082] sbi.7z",
    "SLES-02083": "sbifiles/Final Fantasy VIII (I) [SLES-02083] sbi.7z",
    "SLES-12083": "sbifiles/Final Fantasy VIII (I) [SLES-02083] sbi.7z",
    "SLES-22083": "sbifiles/Final Fantasy VIII (I) [SLES-02083] sbi.7z",
    "SLES-32083": "sbifiles/Final Fantasy VIII (I) [SLES-02083] sbi.7z",
    "SLES-02084": "sbifiles/Final Fantasy VIII (S) [SLES-02084] sbi.7z",
    "SLES-12084": "sbifiles/Final Fantasy VIII (S) [SLES-02084] sbi.7z",
    "SLES-22084": "sbifiles/Final Fantasy VIII (S) [SLES-02084] sbi.7z",
    "SLES-32084": "sbifiles/Final Fantasy VIII (S) [SLES-02084] sbi.7z",
    "SLES-02978": "sbifiles/Football Manager Campionato 2001 (I) [SLES-02978] sbi.7z",
    "SCES-01979": "sbifiles/Formula One 99 (E)(F)(G)(I) [SCES-01979] sbi.7z",
    "SLES-02767": "sbifiles/Frontschweine (Hogs of War) (G) [SLES-02767] sbi.7z",
    "SCES-01702": "sbifiles/Fussball Live (G) [SCES-01702] sbi.7z",
    "SLES-03062": "sbifiles/Fussball Manager 2001 (G) [SLES-03062] sbi.7z",
    "SLES-02328": "sbifiles/Galerians (E) [SLES-02328] sbi.7z",
    "SLES-12328": "sbifiles/Galerians (E) [SLES-02328] sbi.7z",
    "SLES-22328": "sbifiles/Galerians (E) [SLES-02328] sbi.7z",
    "SLES-02329": "sbifiles/Galerians (F) [SLES-02329] sbi.7z",
    "SLES-12329": "sbifiles/Galerians (F) [SLES-02329] sbi.7z",
    "SLES-22329": "sbifiles/Galerians (F) [SLES-02329] sbi.7z",
    "SLES-02330": "sbifiles/Galerians (G) [SLES-02330] sbi.7z",
    "SLES-12330": "sbifiles/Galerians (G) [SLES-02330] sbi.7z",
    "SLES-22330": "sbifiles/Galerians (G) [SLES-02330] sbi.7z",
    "SLES-01241": "sbifiles/Gekido - Urban Fighters (E)(F)(G)(I)(S) [SLES-01241] sbi.7z",
    "SLES-01041": "sbifiles/Hogs of War (E) [SLES-01041] sbi.7z",
    "SCES-01444": "sbifiles/Jackie Chan Stuntmaster (E) [SCES-01444] sbi.7z",
    "SLES-01362": "sbifiles/Le Mans 24 Hours (E)(F)(G)(S)(I)(P) [SLES-01362] sbi.7z",
    "SCES-01701": "sbifiles/Le Monde des Bleus - Le jeu officiel de l'equipe de France (F) [SCES-01701] sbi.7z",
    "SLES-01301": "sbifiles/Legacy of Kain - Soul Reaver (E) [SLES-01301] sbi.7z",
    "SLES-02024": "sbifiles/Legacy of Kain - Soul Reaver (F) [SLES-02024] sbi.7z",
    "SLES-02025": "sbifiles/Legacy of Kain - Soul Reaver (G) [SLES-02025] sbi.7z",
    "SLES-02027": "sbifiles/Legacy of Kain - Soul Reaver (I) [SLES-02027] sbi.7z",
    "SLES-02026": "sbifiles/Legacy of Kain - Soul Reaver (S) [SLES-02026] sbi.7z",
    "SLES-02766": "sbifiles/Les Cochons de Guerre (Hogs of War) (F) [SLES-02766] sbi.7z",
    "SLES-02975": "sbifiles/LMA Manager 2001 (E) [SLES-02975] sbi.7z",
    "SLES-03603": "sbifiles/LMA Manager 2002 (E) [SLES-03603] sbi.7z",
    "SLES-03530": "sbifiles/Lucky Luke - Western Fever (E)(F)(G)(I)(S)(Du) [SLES-03530] sbi.7z",
    "SCES-00311": "sbifiles/MediEvil (E) [SCES-00311] sbi.7z",
    "SCES-01492": "sbifiles/MediEvil (F) [SCES-01492] sbi.7z",
    "SCES-01493": "sbifiles/MediEvil (G) [SCES-01493] sbi.7z",
    "SCES-01494": "sbifiles/MediEvil (I) [SCES-01494] sbi.7z",
    "SCES-01495": "sbifiles/MediEvil (S) [SCES-01495] sbi.7z",
    "SCES-02544": "sbifiles/MediEvil 2 (E)(F)(G) [SCES-02544] sbi.7z",
    "SCES-02545": "sbifiles/MediEvil 2 (S)(I)(P) [SCES-02545] sbi.7z",
    "SCES-02546": "sbifiles/MediEvil 2 (R) [SCES-02546] sbi.7z",
    "SLES-03519": "sbifiles/Men in Black - The Series - Crashdown (E) [SLES-03519] sbi.7z",
    "SLES-03520": "sbifiles/Men in Black - The Series - Crashdown (F) [SLES-03520] sbi.7z",
    "SLES-03521": "sbifiles/Men in Black - The Series - Crashdown (G) [SLES-03521] sbi.7z",
    "SLES-03522": "sbifiles/Men in Black - The Series - Crashdown (I) [SLES-03522] sbi.7z",
    "SLES-03523": "sbifiles/Men in Black - The Series - Crashdown (S) [SLES-03523] sbi.7z",
    "SLES-01545": "sbifiles/Michelin Rally Masters - Race of Champions (E)(G)(Sw) [SLES-01545] sbi.7z",
    "SLES-02395": "sbifiles/Michelin Rally Masters - Race of Champions (F)(I)(S) [SLES-02395] sbi.7z",
    "SLES-02839": "sbifiles/Mike Tyson Boxing (E)(F)(G)(I)(S) [SLES-02839] sbi.7z",
    "SLES-01906": "sbifiles/Mission - Impossible (E)(F)(G)(I)(S) [SLES-01906] sbi.7z",
    "SLES-02830": "sbifiles/MoHo (E)(F)(G)(I)(S) [SLES-02830] sbi.7z",
    "SLES-02689": "sbifiles/Need for Speed - Porsche 2000 (E)(G)(Sw) [SLES-02689] sbi.7z",
    "SLES-02700": "sbifiles/Need for Speed - Porsche 2000 (F)(S)(I) [SLES-02700] sbi.7z",
    "SLES-02086": "sbifiles/N-Gen Racing (E)(F)(G)(I)(S) [SLES-02086] sbi.7z",
    "SLES-02558": "sbifiles/Parasite Eve II (E) [SLES-02558] sbi.7z",
    "SLES-12558": "sbifiles/Parasite Eve II (E) [SLES-02558] sbi.7z",
    "SLES-02559": "sbifiles/Parasite Eve II (F) [SLES-02559] sbi.7z",
    "SLES-12559": "sbifiles/Parasite Eve II (F) [SLES-02559] sbi.7z",
    "SLES-02560": "sbifiles/Parasite Eve II (G) [SLES-02560] sbi.7z",
    "SLES-12560": "sbifiles/Parasite Eve II (G) [SLES-02560] sbi.7z",
    "SLES-02561": "sbifiles/Parasite Eve II (S) [SLES-02561] sbi.7z",
    "SLES-12561": "sbifiles/Parasite Eve II (S) [SLES-02561] sbi.7z",
    "SLES-02562": "sbifiles/Parasite Eve II (I) [SLES-02562] sbi.7z",
    "SLES-12562": "sbifiles/Parasite Eve II (I) [SLES-02562] sbi.7z",
    "SLES-02992": "sbifiles/Premier Manager 2000 (E) [SLES-02992] sbi.7z",
    "SLES-00017": "sbifiles/Prince Naseem Boxing (E)(F)(G)(I)(S) [SLES-00017] sbi.7z",
    "SLES-01943": "sbifiles/Radikal Bikers (E)(F)(G)(I)(S) [SLES-01943] sbi.7z",
    "SLES-02824": "sbifiles/RC Revenge (E)(F)(G)(S) [SLES-02824] sbi.7z",
    "SLES-02529": "sbifiles/Resident Evil 3 - Nemesis (E) [SLES-02529] sbi.7z",
    "SLES-02530": "sbifiles/Resident Evil 3 - Nemesis (F) [SLES-02530] sbi.7z",
    "SLES-02531": "sbifiles/Resident Evil 3 - Nemesis (G) [SLES-02531] sbi.7z",
    "SLES-02698": "sbifiles/Resident Evil 3 - Nemesis (Ir) [SLES-02698] sbi.7z",
    "SLES-02533": "sbifiles/Resident Evil 3 - Nemesis (I) [SLES-02533] sbi.7z",
    "SLES-02532": "sbifiles/Resident Evil 3 - Nemesis (S) [SLES-02532] sbi.7z",
    "SLES-00995": "sbifiles/Ronaldo V-Football (E)(F)(Du)(Sw) [SLES-00995] sbi.7z",
    "SLES-02681": "sbifiles/Ronaldo V-Football (G)(S)(I)(P) [SLES-02681] sbi.7z",
    "SLES-02112": "sbifiles/Saga Frontier 2 (E) [SLES-02112] sbi.7z",
    "SLES-02113": "sbifiles/Saga Frontier 2 (F) [SLES-02113] sbi.7z",
    "SLES-02118": "sbifiles/Saga Frontier 2 (G) [SLES-02118] sbi.7z",
    "SLES-02763": "sbifiles/Sno-Cross Championship Racing (E)(F)(G)(I)(S) [SLES-02763] sbi.7z",
    "SCES-02290": "sbifiles/Space Debris (E) [SCES-02290] sbi.7z",
    "SCES-02430": "sbifiles/Space Debris (F) [SCES-02430] sbi.7z",
    "SCES-02431": "sbifiles/Space Debris (G) [SCES-02431] sbi.7z",
    "SCES-02432": "sbifiles/Space Debris (I) [SCES-02432] sbi.7z",
    "SCES-01763": "sbifiles/Speed Freaks (E) [SCES-01763] sbi.7z",
    "SCES-02104": "sbifiles/Spyro 2 - Gateway to Glimmer (E)(F)(G)(I)(S) [SCES-02104] sbi.7z",
    "SCES-02835": "sbifiles/Spyro - Year of the Dragon (E)(F)(G)(I)(S) (v1.1) [SCES-02835] sbi.7z",
    "SLES-02857": "sbifiles/Sydney 2000 (E) [SLES-02857] sbi.7z",
    "SLES-02858": "sbifiles/Sydney 2000 (F) [SLES-02858] sbi.7z",
    "SLES-02859": "sbifiles/Sydney 2000 (G) [SLES-02859] sbi.7z",
    "SLES-02861": "sbifiles/Sydney 2000 (S) [SLES-02861] sbi.7z",
    "SLES-03245": "sbifiles/TechnoMage - De Terugkeer der Eeuwigheid (Du) [SLES-03245] sbi.7z",
    "SLES-02831": "sbifiles/TechnoMage - Die Rueckkehr der Ewigkeit (G) [SLES-02831] sbi.7z",
    "SLES-03242": "sbifiles/TechnoMage - En Quete de L'Eternite (F) [SLES-03242] sbi.7z",
    "SLES-03241": "sbifiles/TechnoMage - Return of Eternity (E) [SLES-03241] sbi.7z",
    "SLES-03489": "sbifiles/The Italian Job (E) [SLES-03489] sbi.7z",
    "SLES-03626": "sbifiles/The Italian Job (G) [SLES-03626] sbi.7z",
    "SLES-02688": "sbifiles/Theme Park World (E)(F)(G)(I)(S)(Du)(Sw) [SLES-02688] sbi.7z",
    "SCES-01700": "sbifiles/This Is Football (E) [SCES-01700] sbi.7z",
    "SCES-01703": "sbifiles/This Is Football (I) [SCES-01703] sbi.7z",
    "SCES-01882": "sbifiles/This Is Football (F)(Du) [SCES-01882] sbi.7z",
    "SLES-02572": "sbifiles/TOCA World Touring Cars (E)(F)(G) [SLES-02572] sbi.7z",
    "SLES-02573": "sbifiles/TOCA World Touring Cars (I)(S) [SLES-02573] sbi.7z",
    "SLES-02704": "sbifiles/UEFA Euro 2000 (E) [SLES-02704] sbi.7z",
    "SLES-02705": "sbifiles/UEFA Euro 2000 (F) [SLES-02705] sbi.7z",
    "SLES-02706": "sbifiles/UEFA Euro 2000 (G) [SLES-02706] sbi.7z",
    "SLES-02707": "sbifiles/UEFA Euro 2000 (I) [SLES-02707] sbi.7z",
    "SLES-01733": "sbifiles/UEFA Striker (E)(F)(G)(I)(S)(Du) [SLES-01733] sbi.7z",
    "SLES-02071": "sbifiles/Urban Chaos (E)(S)(I) [SLES-02071] sbi.7z",
    "SLES-02355": "sbifiles/Urban Chaos (G) [SLES-02355] sbi.7z",
    "SLES-02754": "sbifiles/Vagrant Story (E) [SLES-02754] sbi.7z",
    "SLES-02755": "sbifiles/Vagrant Story (F) [SLES-02755] sbi.7z",
    "SLES-02756": "sbifiles/Vagrant Story (G) [SLES-02756] sbi.7z",
    "SLES-01907": "sbifiles/V-Rally - Championship Edition 2 (E)(F)(G) [SLES-01907] sbi.7z",
    "SLES-02733": "sbifiles/Walt Disney World Quest - Magical Racing Tour (E)(F)(G)(I)(S)(Du)(Sw)(N)(D) [SLES-02733] sbi.7z",
}


def get_track_sizes_from_chd(chd_path):
    """Run chdman info and extract track frame counts, convert to byte sizes."""
    try:
        result = subprocess.run(
            [CHDMAN, "info", "-i", chd_path],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
    except Exception as e:
        print(f"  ERROR running chdman: {e}")
        return None

    tracks = []
    for m in re.finditer(r"TRACK:(\d+)\s+TYPE:(\S+)\s+.*?FRAMES:(\d+)", output):
        track_num = int(m.group(1))
        frames = int(m.group(3))
        byte_size = frames * 2352
        tracks.append((track_num, byte_size))

    return tracks


def build_discdb_lookup(discdb_path):
    """Build lookups from discdb.yaml: track sizes -> serial."""
    print("Loading discdb.yaml...")
    with open(discdb_path, "r", encoding="utf-8") as f:
        db = yaml.safe_load(f)

    size_to_serial = {}
    sizes_tuple_to_serial = {}

    for serial, info in db.items():
        if not isinstance(info, dict) or "trackData" not in info:
            continue
        name = info.get("name", "")
        for variant in info["trackData"]:
            if not isinstance(variant, dict) or "tracks" not in variant:
                continue
            track_sizes = []
            for t in variant["tracks"]:
                if isinstance(t, dict) and "size" in t:
                    track_sizes.append(t["size"])

            if track_sizes:
                size_to_serial.setdefault(track_sizes[0], []).append((serial, name))
                sizes_tuple_to_serial.setdefault(tuple(track_sizes), []).append((serial, name))

    print(f"  Loaded {len(db)} entries, {len(size_to_serial)} unique first-track sizes")
    return size_to_serial, sizes_tuple_to_serial


def identify_serial(tracks, size_to_serial, sizes_tuple_to_serial):
    """Given track sizes from a CHD, find the serial number."""
    if not tracks:
        return None, None

    sizes = tuple(s for _, s in sorted(tracks))

    if sizes in sizes_tuple_to_serial:
        return sizes_tuple_to_serial[sizes][0]

    first_size = tracks[0][1]
    if first_size in size_to_serial:
        return size_to_serial[first_size][0]

    return None, None


def download_and_extract_sbi(serial, sbi_path, chd_filename, chd_dir, dry_run=False):
    """Download .7z, extract .sbi, rename to match CHD filename."""
    chd_base = os.path.splitext(chd_filename)[0]
    target_sbi = chd_base + ".sbi"
    target_path = os.path.join(chd_dir, target_sbi)

    if os.path.exists(target_path):
        print(f"  SKIP (already exists): {target_sbi}")
        return True

    if dry_run:
        print(f"  WOULD download: {sbi_path}")
        print(f"  WOULD save as:  {target_sbi}")
        return True

    url = SBI_BASE_URL + sbi_path.replace(" ", "%20")
    print(f"  Downloading: {url}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR downloading: {e}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, "sbi.7z")
        with open(archive_path, "wb") as f:
            f.write(resp.content)

        try:
            with py7zr.SevenZipFile(archive_path, "r") as z:
                z.extractall(tmpdir)
        except Exception as e:
            print(f"  ERROR extracting 7z: {e}")
            return False

        sbi_files = []
        for root, dirs, files in os.walk(tmpdir):
            for fn in files:
                if fn.lower().endswith(".sbi"):
                    sbi_files.append(os.path.join(root, fn))

        if not sbi_files:
            print(f"  ERROR: No .sbi files found in archive")
            return False

        chosen_sbi = None
        if len(sbi_files) == 1:
            chosen_sbi = sbi_files[0]
        else:
            serial_variants = [serial.upper(), serial.replace("-", "_").upper(), serial.replace("-", "").upper()]
            for sf in sbi_files:
                sf_upper = os.path.basename(sf).upper()
                if any(v in sf_upper for v in serial_variants):
                    chosen_sbi = sf
                    break
            if not chosen_sbi:
                chosen_sbi = sbi_files[0]
                print(f"  WARNING: Multiple SBI files, picked: {os.path.basename(chosen_sbi)}")

        shutil.copy2(chosen_sbi, target_path)
        print(f"  SAVED: {target_sbi}")
        return True


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: py sbi_downloader.py <chd_folder> [--dry-run]")
        print()
        print("Scans CHD files, identifies them via discdb.yaml, and downloads")
        print("matching SBI (LibCrypt) files from psxdatacenter.com.")
        print()
        print("Options:")
        print("  --dry-run    Preview matches without downloading")
        sys.exit(0)

    chd_dir = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.isdir(chd_dir):
        print(f"ERROR: '{chd_dir}' is not a valid directory")
        sys.exit(1)

    ensure_dependencies()

    if dry_run:
        print("=" * 70)
        print("  DRY RUN MODE - No files will be downloaded")
        print("=" * 70)

    size_to_serial, sizes_tuple_to_serial = build_discdb_lookup(DISCDB)

    chd_files = sorted(f for f in os.listdir(chd_dir) if f.lower().endswith(".chd"))
    print(f"\nScanning {len(chd_files)} CHD files in: {chd_dir}\n")

    matched = []
    no_sbi = []
    failed = []

    for chd in chd_files:
        chd_path = os.path.join(chd_dir, chd)
        print(f"[{chd}]")

        tracks = get_track_sizes_from_chd(chd_path)
        if not tracks:
            print(f"  FAILED: Could not read track info")
            failed.append(chd)
            continue

        serial, name = identify_serial(tracks, size_to_serial, sizes_tuple_to_serial)
        if not serial:
            print(f"  NOT FOUND in discdb (track sizes: {[s for _, s in tracks]})")
            failed.append(chd)
            continue

        print(f"  Serial: {serial} ({name})")

        if serial in SBI_DB:
            sbi_path = SBI_DB[serial]
            matched.append((chd, serial, name, sbi_path))
            download_and_extract_sbi(serial, sbi_path, chd, chd_dir, dry_run)
        else:
            no_sbi.append((chd, serial))
            print(f"  No SBI needed")

        print()

    print("=" * 70)
    print(f"  SUMMARY")
    print(f"  Total CHD files:     {len(chd_files)}")
    print(f"  SBI downloaded:      {len(matched)}")
    print(f"  No SBI needed:       {len(no_sbi)}")
    print(f"  Failed to identify:  {len(failed)}")
    print("=" * 70)

    if matched:
        print(f"\n  Games with SBI files:")
        for chd, serial, name, _ in matched:
            print(f"    {serial} - {name}")

    if failed:
        print(f"\n  Could not identify (patched/fan-translated ROMs won't match):")
        for chd in failed:
            print(f"    {chd}")


if __name__ == "__main__":
    main()
