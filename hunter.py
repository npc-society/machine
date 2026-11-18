"""
Repérage des clips sur Twitch (gros streamers + pépites), envoi dans Discord
un message par clip, avec les boutons ✅ garder · ⭐ compil · ❌ jeter.
"""
import csv
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

import config as C
import discord_api as D
import worker as W
from categorize import CATEGORIES, _norm, categorize

STOP = set("""gta gta6 gtavi vi six the and for with this that what when your from just have like they them
then than into over very more most only also some been were will would could there their here dans pour avec
cette mais plus tout tous elle elles nous vous leur leurs sont etait comme quand quoi sans sous entre apres avant
bien trop faire fait part chez para como pero esta este todo todos cuando donde porque muy mas sobre entre desde
hasta clip stream live twitch moment moments best first""".split())


def theme_ideas(pool, min_streamers=4, top=5):
    """Mots qui reviennent dans les titres de clips de plusieurs streamers = idée de compil à thème."""
    import re
    by_word = {}
    for c in pool:
        words = [w for w in re.findall(r"[a-z0-9]+", _norm(c["title"])) if len(w) >= 4 and w not in STOP]
        grams = set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}
        for g in grams:
            d = by_word.setdefault(g, [set(), 0])
            d[0].add(c["broadcaster_id"])
            d[1] += 1
    ideas = [(w, len(s), n) for w, (s, n) in by_word.items() if len(s) >= min_streamers]
    ideas.sort(key=lambda x: (x[1], x[2], " " in x[0]), reverse=True)
    return ideas[:top]

API = "https://api.twitch.tv/helix"
DB_FILE = C.DATA / "clips_db.json"
STREAMERS_FILE = C.DATA / "streamers.json"


# --- Twitch -----------------------------------------------------------------
def get_token() -> str:
    r = requests.post("https://id.twitch.tv/oauth2/token", params={
        "client_id": C.TWITCH_CLIENT_ID, "client_secret": C.TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def helix(token, path, params):
    headers = {"Client-Id": C.TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
    r = None
    for attempt in range(4):
        r = requests.get(f"{API}/{path}", headers=headers, params=params, timeout=20)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def paginate(token, path, params, max_pages):
    items, cursor = [], None
    for _ in range(max_pages):
        p = dict(params, first=100)
        if cursor:
            p["after"] = cursor
        page = helix(token, path, p)
        items.extend(page.get("data", []))
        cursor = page.get("pagination", {}).get("cursor")
        if not cursor or not page.get("data"):
            break
    return items


def find_game_ids(token):
    ids = {}
    for name in C.GAME_NAMES:
        data = helix(token, "games", {"name": name}).get("data", [])
        if data:
            ids[data[0]["id"]] = data[0]["name"]
        else:
            print(f"⚠️ Catégorie introuvable : {name}")
    if not ids:
        sys.exit("Aucune catégorie trouvée : vérifie GAME_NAMES.")
    return ids


# --- Streamers --------------------------------------------------------------
def tier(viewers):
    if viewers is None or viewers < C.SMALL_MAX:
        return "petit"
    return "moyen" if viewers < C.BIG_MIN else "gros"


def update_streamers(streamers, streams, now):
    for s in streams:
        e = streamers.setdefault(s["user_id"], {
            "name": s["user_name"], "login": s["user_login"], "lang": s["language"],
            "max_viewers": 0, "clips_retenus": 0, "first_seen": now.strftime("%Y-%m-%d")})
        e["name"] = s["user_name"]
        e["max_viewers"] = max(e["max_viewers"], s["viewer_count"])
        e["last_seen"] = now.strftime("%Y-%m-%d %H:%M")


def export_streamers_csv(streamers):
    rows = sorted(streamers.values(), key=lambda e: (e["lang"], -e["clips_retenus"], -e["max_viewers"]))
    with (C.DATA / "streamers.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["langue", "streamer", "taille", "max_viewers_vus", "clips_retenus", "twitch",
                    "premiere_detection", "derniere_detection", "contacte", "accord"])
        for e in rows:
            w.writerow([e["lang"], e["name"], tier(e["max_viewers"]), e["max_viewers"], e["clips_retenus"],
                        f"https://twitch.tv/{e['login']}", e.get("first_seen", ""), e.get("last_seen", ""), "", ""])


# --- Scoring ----------------------------------------------------------------
def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def velocity(c, now):
    return c["view_count"] / max((now - parse_ts(c["created_at"])).total_seconds() / 3600, 0.5)


def buzz_ratio(c):
    return c["view_count"] / max(c["_viewers"] or 20, 10)


# --- Discord ----------------------------------------------------------------
TIER_LABEL = {"gros": "🏆 gros", "moyen": "📈 moyen", "petit": "💎 pépite"}
TIER_COLOR = {"gros": 0xFFB000, "moyen": 0xFF6A2E, "petit": 0xFF2E88}


def clip_embed(c, now, rank_label=""):
    cat = CATEGORIES[c["_cat"]]
    viewers = f"{c['_viewers']} viewers" if c["_viewers"] else "viewers ?"
    return {
        "title": f"{rank_label}{cat['emoji']} {c['title']}"[:256],
        "url": c["url"],
        "description": (f"**{c['broadcaster_name']}** · {TIER_LABEL[c['_tier']]} ({viewers})\n"
                        f"{c['view_count']} vues · {round(c['duration'])} s · 🔥 {round(velocity(c, now))} vues/h"
                        f" · ×{buzz_ratio(c):.1f}\nCatégorie : **{cat['label']['fr']}**"),
        "image": {"url": c["thumbnail_url"]},
        "timestamp": c["created_at"],
        "color": TIER_COLOR[c["_tier"]],
        "footer": {"text": "✅ short · 🌍 version traduite pour l'autre chaîne · ⭐ compil · ❌ jeter"},
    }


def propose(c, lang, now, db, auto=False):
    ch = C.channel("CLIPS", lang)
    if not ch or not C.DISCORD_TOKEN:
        print(f"[{lang}] salon Discord non configuré, clip archivé seulement : {c['title']}")
        msg = None
    else:
        emb = clip_embed(c, now)
        if auto:
            emb["footer"]["text"] = "🤖 Montage automatique lancé · " + emb["footer"]["text"]
        msg = D.send(ch, embeds=[emb])
        D.add_buttons(ch, msg["id"])
    db[c["id"]] = {
        "id": c["id"], "lang": lang, "title": c["title"], "url": c["url"], "created_at": c["created_at"],
        "streamer": c["broadcaster_name"], "streamer_id": c["broadcaster_id"], "tier": c["_tier"],
        "viewers": c["_viewers"], "views": c["view_count"], "duration": c["duration"],
        "thumbnail": c["thumbnail_url"], "game": c.get("_game", ""), "category": c["_cat"],
        "status": "propose", "channel": ch, "message_id": msg["id"] if msg else None,
        "proposed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# --- Main -------------------------------------------------------------------
def run(mode="hunt"):
    if not C.TWITCH_CLIENT_ID or not C.TWITCH_CLIENT_SECRET:
        sys.exit("Il manque TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET")
    now = datetime.now(timezone.utc)
    token = get_token()
    games = find_game_ids(token)
    streamers = C.load_json(STREAMERS_FILE)
    db = C.load_json(DB_FILE)
    queue = C.load_json(W.QUEUE_FILE, default=[])

    window = timedelta(hours=6) if mode == "hunt" else timedelta(hours=24)
    clips = []
    for gid, gname in games.items():
        for lang in C.LANGS:
            update_streamers(streamers, paginate(token, "streams", {"game_id": gid, "language": lang},
                                                 C.STREAM_PAGES), now)
        for c in paginate(token, "clips", {"game_id": gid,
                                            "started_at": (now - window).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                            "ended_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, C.CLIP_PAGES):
            c["_game"] = gname
            clips.append(c)
    print(f"{len(clips)} clips, {len(streamers)} streamers connus")

    for lang in C.LANGS:
        pool = []
        for c in clips:
            if c.get("language") != lang or not (C.MIN_CLIP_SECONDS <= c["duration"] <= C.MAX_CLIP_SECONDS):
                continue
            s = streamers.get(c["broadcaster_id"])
            c["_viewers"] = s["max_viewers"] if s else None
            if c["_viewers"] is None:  # streamer hors ligne : on estime sa taille via les vues du clip
                c["_tier"] = "gros" if c["view_count"] >= 1500 else "petit"
            else:
                c["_tier"] = tier(c["_viewers"])
            c["_cat"] = categorize(c["title"])
            pool.append(c)
        big = [c for c in pool if c["_tier"] != "petit" and c["view_count"] >= C.MIN_VIEWS_BIG]
        small = [c for c in pool if c["_tier"] == "petit" and c["view_count"] >= C.MIN_VIEWS_SMALL]

        if mode == "hunt":
            big = sorted((c for c in big if c["id"] not in db), key=lambda c: velocity(c, now),
                         reverse=True)[:C.PER_RUN_BIG]
            small = sorted((c for c in small if c["id"] not in db), key=buzz_ratio,
                           reverse=True)[:C.PER_RUN_SMALL]
            # Montage automatique des meilleurs (alternance gros / pépite), sans attendre ton ✅
            interleaved = [x for pair in zip(big, small) for x in pair] + big[len(small):] + small[len(big):]
            auto_ids = {c["id"] for c in interleaved[:C.AUTO_PER_RUN]}
            for c in big + small:
                propose(c, lang, now, db, auto=c["id"] in auto_ids)
                if c["id"] in auto_ids:
                    W.enqueue(queue, c["id"], lang, db, auto=True)
                if c["broadcaster_id"] in streamers:
                    streamers[c["broadcaster_id"]]["clips_retenus"] += 1
            print(f"[{lang}] {len(big)} gros + {len(small)} pépites proposés")
        else:  # récap du jour
            ch = C.channel("CLIPS", lang)
            top = sorted(big, key=lambda c: c["view_count"], reverse=True)[:C.DAILY_BIG]
            gems = sorted(small, key=buzz_ratio, reverse=True)[:C.DAILY_SMALL]
            ideas = theme_ideas(pool)
            if ch and C.DISCORD_TOKEN and ideas:
                lines = "\n".join(f"• **{w}** — {n} streamers, {k} clips" for w, n, k in ideas)
                D.send(ch, f"💡 **Idées de compils à thème** (ce qui revient chez plusieurs streamers aujourd'hui)\n"
                           f"{lines}\nPour en lancer une : Run workflow → action `theme` + le mot-clé.")
            if ch and C.DISCORD_TOKEN:
                flag = C.FLAGS.get(lang, lang.upper())
                for header, lst in ((f"{flag} ⭐ **TOP {len(top)} DU JOUR** — {now:%d/%m}", top),
                                    (f"{flag} 💎 **TOP {len(gems)} PÉPITES DU JOUR** — {now:%d/%m}", gems)):
                    if not lst:
                        continue
                    embeds = [clip_embed(c, now, f"{i}. ") for i, c in enumerate(lst, 1)]
                    for k in range(0, len(embeds), 10):
                        D.send(ch, header if k == 0 else "", embeds=embeds[k:k + 10])

    cutoff = now - timedelta(days=10)
    db = {k: v for k, v in db.items() if parse_ts(v["created_at"]) > cutoff or v.get("compil")}
    C.save_json(DB_FILE, db)
    C.save_json(W.QUEUE_FILE, queue)
    C.save_json(STREAMERS_FILE, streamers)
    export_streamers_csv(streamers)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "hunt")
