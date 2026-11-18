"""Classement d'un clip par catégorie, à partir de son titre (et de la transcription quand on l'a)."""
import re
import unicodedata

CATEGORIES = {
    "rage": {"emoji": "😡", "label": {"fr": "Rage", "en": "Rage", "es": "Rabia"}},
    "fail": {"emoji": "💥", "label": {"fr": "Fail", "en": "Fail"}},
    "incroyable": {"emoji": "🤯", "label": {"fr": "Incroyable", "en": "Insane"}},
    "decouverte": {"emoji": "🔍", "label": {"fr": "Découverte", "en": "Discovery"}},
    "course": {"emoji": "🏁", "label": {"fr": "Course / poursuite", "en": "Chase / race"}},
    "drole": {"emoji": "😂", "label": {"fr": "Drôle", "en": "Funny"}},
}

KEYWORDS = {
    "rage": ["enfadado", "grita", "se enoja", "furioso", "rage", "tilt", "enerve", "colere", "crie", "hurle", "pete un cable", "ragequit", "mad",
             "angry", "furious", "screams", "screaming", "lost it", "malaise", "insulte", "pourquoi"],
    "fail": ["choca", "falla", "se cae", "muere", "accidente", "fail", "rate", "foire", "crash", "accident", "chute", "tombe", "explose", "boulette", "erreur",
             "oups", "oops", "bug", "glitch", "wasted", "mort", "dies", "died", "trolled", "rip", "nul"],
    "incroyable": ["increible", "brutal", "locura", "imposible", "incroyable", "dingue", "dinguerie", "insane", "clutch", "wtf", "fou", "folie", "impossible",
                   "crazy", "unreal", "goat", "jamais vu", "never seen", "masterclass", "cascade", "stunt"],
    "decouverte": ["secreto", "oculto", "descubre", "secret", "easter egg", "cache", "decouvre", "decouverte", "found", "hidden", "discover",
                   "detail", "details", "reference", "map", "lieu", "location"],
    "course": ["persecucion", "policia", "carrera", "huye", "course", "poursuite", "police", "flic", "flics", "chase", "race", "cops", "fuite", "escape",
               "braquage", "heist", "etoiles", "stars", "wanted"],
    "drole": ["jaja", "jajaja", "xd", "risa", "gracioso", "mdr", "ptdr", "lol", "lmao", "drole", "funny", "rire", "laugh", "pnj", "npc", "hilarious",
              "kekw", "omegalul", "jpp", "😂", "💀"],
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def categorize(title: str, transcript: str = "") -> str:
    text = _norm(f"{title} {title} {transcript}")  # le titre compte double
    scores = {}
    for cat, words in KEYWORDS.items():
        scores[cat] = sum(len(re.findall(rf"(?<!\w){re.escape(_norm(w))}(?!\w)", text)) for w in words)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "drole"
