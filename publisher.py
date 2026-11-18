"""
Publication automatique des montages validés (✅ sur la vidéo dans #montages-xx).
Instagram : API Instagram (connexion Instagram), publication en Reel.
La vidéo est lue directement depuis Discord (lien de la pièce jointe, valable environ 24 h).
"""
import time
from datetime import datetime, timedelta, timezone

import requests

import config as C
import discord_api as D

PUBLISH_QUEUE = C.DATA / "publish_queue.json"
PUBLISHED = C.DATA / "published.json"
GRAPH = "https://graph.instagram.com/v21.0"


def ig_ready(lang):
    return bool(C.env(f"IG_TOKEN_{lang.upper()}") and C.env(f"IG_USER_{lang.upper()}"))


def _now():
    return datetime.now(timezone.utc)


def enqueue(montage_key, montage):
    queue = C.load_json(PUBLISH_QUEUE, default=[])
    if not ig_ready(montage["lang"]) or any(q["key"] == montage_key for q in queue):
        return False
    queue.append({"key": montage_key, "lang": montage["lang"], "platform": "instagram",
                  "added": _now().strftime("%Y-%m-%dT%H:%M:%SZ"), "tries": 0})
    C.save_json(PUBLISH_QUEUE, queue)
    return True


def _can_post(lang, published):
    """Rythme d'échauffement : X posts max par jour et un écart minimum entre deux posts."""
    mine = [p for p in published if p["lang"] == lang and p["platform"] == "instagram"]
    today = _now().strftime("%Y-%m-%d")
    if sum(1 for p in mine if p["at"].startswith(today)) >= C.IG_MAX_PER_DAY:
        return False
    if mine:
        last = datetime.strptime(mine[-1]["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if _now() - last < timedelta(hours=C.IG_MIN_GAP_HOURS):
            return False
    return True


def _video_url(channel_id, message_id):
    msg = D._req("GET", f"/channels/{channel_id}/messages/{message_id}")
    for a in msg.get("attachments", []):
        if a.get("filename", "").endswith(".mp4"):
            return a["url"]
    return None


def _ig_post(lang, video_url, caption):
    token, user = C.env(f"IG_TOKEN_{lang.upper()}"), C.env(f"IG_USER_{lang.upper()}")
    r = requests.post(f"{GRAPH}/{user}/media", timeout=60, data={
        "media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
        "share_to_feed": "true", "access_token": token})
    if r.status_code != 200:
        raise RuntimeError(f"création du Reel refusée : {r.text[:300]}")
    cid = r.json()["id"]
    for _ in range(40):  # Instagram télécharge et traite la vidéo (jusqu'à ~5 min)
        time.sleep(8)
        s = requests.get(f"{GRAPH}/{cid}", timeout=30,
                         params={"fields": "status_code,status", "access_token": token}).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"traitement Instagram en échec : {s}")
    else:
        raise RuntimeError("traitement Instagram trop long")
    p = requests.post(f"{GRAPH}/{user}/media_publish", timeout=60,
                      data={"creation_id": cid, "access_token": token})
    if p.status_code != 200:
        raise RuntimeError(f"publication refusée : {p.text[:300]}")
    media_id = p.json()["id"]
    link = requests.get(f"{GRAPH}/{media_id}", timeout=30,
                        params={"fields": "permalink", "access_token": token}).json().get("permalink", "")
    return media_id, link


def publish():
    queue = C.load_json(PUBLISH_QUEUE, default=[])
    if not queue:
        return
    montages = C.load_json(C.DATA / "montages.json")
    published = C.load_json(PUBLISHED, default=[])
    keep = []
    for item in queue:
        m = montages.get(item["key"])
        if not m or m.get("status") != "valide":
            continue
        if not _can_post(item["lang"], published):
            keep.append(item)
            continue
        ch = C.channel("MONTAGES", item["lang"])
        try:
            url = _video_url(ch, m["message_id"])
            if not url:
                raise RuntimeError("vidéo introuvable dans Discord")
            media_id, link = _ig_post(item["lang"], url, m["caption"])
            published.append({"key": item["key"], "lang": item["lang"], "platform": "instagram",
                              "at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"), "id": media_id, "link": link})
            m["status"] = "publie"
            D.send(ch, f"📲 Publié sur Instagram {item['lang'].upper()} : {link or media_id}")
        except Exception as e:
            item["tries"] += 1
            print(f"⚠️ Publication Instagram {item['key']} : {e}")
            if item["tries"] < 3:
                keep.append(item)
            else:
                D.send(ch, f"⚠️ Échec de publication Instagram après 3 essais : {e}")
    C.save_json(PUBLISH_QUEUE, keep)
    C.save_json(PUBLISHED, published[-500:])
    C.save_json(C.DATA / "montages.json", montages)


def check_tokens():
    """Prévient dans Discord quand un jeton Instagram approche de l'expiration (60 jours)."""
    for lang in C.LANGS:
        if not ig_ready(lang):
            continue
        r = requests.get(f"{GRAPH}/me", timeout=30,
                         params={"fields": "username", "access_token": C.env(f"IG_TOKEN_{lang.upper()}")})
        if r.status_code != 200:
            ch = C.channel("MONTAGES", lang)
            if ch:
                D.send(ch, f"⚠️ Le jeton Instagram {lang.upper()} ne marche plus : régénère-le sur developers.facebook.com "
                           f"et mets à jour le secret IG_TOKEN_{lang.upper()}.")


if __name__ == "__main__":
    import sys
    check_tokens() if len(sys.argv) > 1 and sys.argv[1] == "tokens" else publish()
