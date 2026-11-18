"""Réglages communs. Tout se change via les variables / secrets GitHub."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "out"
ASSETS = ROOT / "assets"
BRAND_DIR = ROOT / "brand"
FONT = ASSETS / "fonts" / "Anton-Regular.ttf"


def env(name, default=""):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def env_int(name, default):
    try:
        return int(env(name, default))
    except ValueError:
        return default


# --- Twitch
TWITCH_CLIENT_ID = env("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = env("TWITCH_CLIENT_SECRET")
GAME_NAMES = [g.strip() for g in env("GAME_NAMES", "Grand Theft Auto VI").split(",") if g.strip()]
LANGS = [l.strip().lower() for l in env("LANGS", "fr,en").split(",") if l.strip()]

# --- Discord (bot)
DISCORD_TOKEN = env("DISCORD_BOT_TOKEN")


def channel(kind: str, lang: str) -> str:
    """kind = CLIPS ou MONTAGES. Ex. secret DISCORD_CLIPS_FR = id du salon #clips-fr"""
    return env(f"DISCORD_{kind}_{lang.upper()}")


# --- Taille des streamers et seuils
SMALL_MAX = env_int("SMALL_MAX", 300)
BIG_MIN = env_int("BIG_MIN", 3000)
MIN_VIEWS_BIG = env_int("MIN_VIEWS", 150)
MIN_VIEWS_SMALL = env_int("MIN_VIEWS_SMALL", 25)
PER_RUN_BIG = env_int("PER_RUN_BIG", 4)
PER_RUN_SMALL = env_int("PER_RUN_SMALL", 4)
DAILY_BIG = env_int("DAILY_BIG", 10)
DAILY_SMALL = env_int("DAILY_SMALL", 10)
STREAM_PAGES = env_int("STREAM_PAGES", 20)
CLIP_PAGES = env_int("CLIP_PAGES", 20)

# --- Montage
MAX_RENDERS_PER_RUN = env_int("MAX_RENDERS_PER_RUN", 10)
AUTO_PER_RUN = env_int("AUTO_PER_RUN", 2)          # clips montés d'office à chaque repérage, par langue
FLASH_SIZE = env_int("FLASH_SIZE", 3)              # nombre de brèves dans un flash info
FLASH_SECONDS = env_int("FLASH_SECONDS", 15)       # durée de chaque brève
MIN_CLIP_SECONDS = env_int("MIN_CLIP_SECONDS", 15)  # on ignore les clips trop courts
AUTO_MIN_SCORE = env_int("AUTO_MIN_SCORE", 6)      # note IA minimale (sur 10) pour un montage auto
THEME_SIZE = env_int("THEME_SIZE", 8)              # nombre de clips dans une compil à thème
MAX_CLIP_SECONDS = env_int("MAX_CLIP_SECONDS", 60)
WHISPER_MODEL = env("WHISPER_MODEL", "small")
DISCORD_MAX_MB = float(env("DISCORD_MAX_MB", "9.5"))  # limite d'upload Discord pour un bot : 10 Mo

# --- Textes optionnels générés par IA (sinon modèles de texte intégrés)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-haiku-5-5")
AI_MAX_CALLS_PER_DAY = env_int("AI_MAX_CALLS_PER_DAY", 500)  # ~0,15 $ max par jour avec Haiku 5.5

FLAGS = {"fr": "🇫🇷", "en": "🇬🇧", "es": "🇪🇸", "de": "🇩🇪", "pt": "🇧🇷", "it": "🇮🇹"}


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


BRAND = load_json(BRAND_DIR / "brand.json")
MEMES = load_json(BRAND_DIR / "memes.json")
