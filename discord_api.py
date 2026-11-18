"""Mini client Discord (API REST, sans connexion permanente) pour un bot."""
import json
import time
from pathlib import Path
from urllib.parse import quote

import requests

from config import DISCORD_TOKEN

API = "https://discord.com/api/v10"
CHOICES = {"✅": "garder", "🔞": "censure", "🌍": "croise", "⭐": "compil", "❌": "jeter"}
VALIDATE = {"✅": "valide", "🔁": "refaire", "❌": "jeter"}


def _req(method: str, path: str, **kw):
    headers = kw.pop("headers", {})
    headers["Authorization"] = f"Bot {DISCORD_TOKEN}"
    for _ in range(5):
        r = requests.request(method, f"{API}{path}", headers=headers, timeout=60, **kw)
        if r.status_code == 429:
            try:
                time.sleep(float(r.json().get("retry_after", 1)) + 0.2)
            except ValueError:
                time.sleep(2)
            continue
        if r.status_code >= 500:
            time.sleep(2)
            continue
        r.raise_for_status()
        return r.json() if r.content else None
    r.raise_for_status()


def send(channel_id: str, content: str = "", embeds=None, file: Path = None) -> dict:
    payload = {"content": content[:2000]}
    if embeds:
        payload["embeds"] = embeds
    if file:
        with open(file, "rb") as fh:
            return _req("POST", f"/channels/{channel_id}/messages",
                        data={"payload_json": json.dumps(payload)},
                        files={"files[0]": (file.name, fh, "video/mp4")})
    return _req("POST", f"/channels/{channel_id}/messages", json=payload)


def react(channel_id: str, message_id: str, emoji: str) -> None:
    _req("PUT", f"/channels/{channel_id}/messages/{message_id}/reactions/{quote(emoji)}/@me")
    time.sleep(0.3)


def add_buttons(channel_id: str, message_id: str, choices=CHOICES) -> None:
    """Le bot pose lui-même les réactions : tu n'as plus qu'à appuyer dessus."""
    for emoji in choices:
        react(channel_id, message_id, emoji)


def recent_messages(channel_id: str, pages: int = 3) -> list:
    msgs, before = [], None
    for _ in range(pages):
        params = {"limit": 100}
        if before:
            params["before"] = before
        batch = _req("GET", f"/channels/{channel_id}/messages", params=params) or []
        msgs.extend(batch)
        if len(batch) < 100:
            break
        before = batch[-1]["id"]
    return msgs


def user_choices(message: dict, choices=CHOICES) -> set:
    """Choix de l'humain : les réactions avec un compte > 1 (le bot compte pour 1)."""
    return {choices[r["emoji"]["name"]] for r in message.get("reactions", [])
            if r.get("emoji", {}).get("name") in choices and r.get("count", 0) >= 2}


def user_choice(message: dict, choices=CHOICES):
    found = user_choices(message, choices)
    for v in choices.values():  # ordre de priorité = ordre du dictionnaire
        if v in found:
            return v
    return None
