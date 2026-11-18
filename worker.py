"""
Lit tes réactions dans Discord et agit.
  Sur un clip proposé : ✅ short pour la chaîne du clip · 🌍 version traduite pour l'autre chaîne
                        · ⭐ garder pour la compil · ❌ jeter   (✅ et 🌍 peuvent se cumuler)
  Sur un short monté  : ✅ validé · 🔁 refaire (autre titre / tampon) · ❌ jeter

Commandes :
  python worker.py check        -> lit les réactions, prépare la file de montage (rapide)
  python worker.py render       -> monte les shorts en attente et les envoie dans #montages-<langue>
  python worker.py compil [fr]  -> compilation de la semaine avec les clips ⭐
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import config as C
import discord_api as D

DB_FILE = C.DATA / "clips_db.json"
QUEUE_FILE = C.DATA / "render_queue.json"
MONTAGES_FILE = C.DATA / "montages.json"


def set_output(name, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"{name}={value}\n")


def other_langs(lang):
    return [l for l in C.LANGS if l != lang]


def enqueue(queue, clip_id, lang):
    item = {"clip": clip_id, "lang": lang}
    if item not in queue:
        queue.append(item)


def check():
    db = C.load_json(DB_FILE)
    queue = [q if isinstance(q, dict) else {"clip": q, "lang": db.get(q, {}).get("lang", "fr")}
             for q in C.load_json(QUEUE_FILE, default=[])]
    montages = C.load_json(MONTAGES_FILE)
    by_msg = {v["message_id"]: v for v in db.values() if v.get("message_id")}
    by_mont = {m["message_id"]: m for m in montages.values() if m.get("message_id")}
    channels = {v["channel"] for v in db.values() if v.get("channel")}
    channels |= {C.channel("MONTAGES", l) for l in C.LANGS if C.channel("MONTAGES", l)}

    for ch in channels:
        for msg in D.recent_messages(ch):
            clip = by_msg.get(msg["id"])
            if clip and clip["status"] == "propose":
                picks = D.user_choices(msg)
                if "jeter" in picks:
                    clip["status"] = "jete"
                elif picks:
                    clip["status"] = "traite"
                    if "garder" in picks:
                        enqueue(queue, clip["id"], clip["lang"])
                    if "croise" in picks:
                        clip["cross"] = True
                        for l in other_langs(clip["lang"]):
                            enqueue(queue, clip["id"], l)
                    if "compil" in picks:
                        clip["compil"] = True
            m = by_mont.get(msg["id"])
            if m and m["status"] == "a_valider":
                choice = D.user_choice(msg, D.VALIDATE)
                if choice == "valide":
                    m["status"] = "valide"
                elif choice == "jeter":
                    m["status"] = "jete"
                elif choice == "refaire":
                    m["status"] = "refait"
                    c = db.get(m["clip_id"])
                    if c:
                        c["reroll"] = c.get("reroll", 0) + 1
                        enqueue(queue, m["clip_id"], m["lang"])

    C.save_json(DB_FILE, db)
    C.save_json(QUEUE_FILE, queue)
    C.save_json(MONTAGES_FILE, montages)
    print(f"{len(queue)} montage(s) en attente")
    set_output("queue", len(queue))


def render():
    import montage
    db = C.load_json(DB_FILE)
    queue = C.load_json(QUEUE_FILE, default=[])
    montages = C.load_json(MONTAGES_FILE)
    done = []
    for item in queue[: C.MAX_RENDERS_PER_RUN]:
        clip = db.get(item["clip"])
        if not clip:
            done.append(item)
            continue
        out_lang = item["lang"]
        work = C.OUT / f"{clip['id']}_{out_lang}"
        try:
            r = montage.render_short(clip, work, target_mb=C.DISCORD_MAX_MB, out_lang=out_lang)
            txt = r["texts"]
            ch = C.channel("MONTAGES", out_lang)
            cross = f"🌍 Clip {clip['lang'].upper()} sous-titré en {out_lang.upper()}\n" if out_lang != clip["lang"] else ""
            if out_lang != clip["lang"] and not r["translated"]:
                cross += "⚠️ Traduction indisponible (ajoute la clé ANTHROPIC_API_KEY)\n"
            reaction = Path(r["meme"]["reaction"]).name if r["meme"].get("reaction") else "-"
            content = (f"{cross}**{txt['title']}**\n```\n{txt['caption']}\n```"
                       f"Tampon : {r['meme'].get('stamp') or '-'} · réaction : {reaction} · mise en page : {r['layout']}\n"
                       f"✅ valider · 🔁 refaire · ❌ jeter")
            msg = D.send(ch, content, file=r["path"]) if ch else None
            if msg:
                D.add_buttons(ch, msg["id"], D.VALIDATE)
            montages[f"{clip['id']}:{out_lang}"] = {
                "clip_id": clip["id"], "lang": out_lang, "status": "a_valider",
                "message_id": msg["id"] if msg else None, "title": txt["title"], "caption": txt["caption"],
                "category": r["category"], "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            done.append(item)
        except Exception as e:
            print(f"⚠️ Échec du montage {clip['url']} ({out_lang}) : {e}")
            clip["errors"] = clip.get("errors", 0) + 1
            if clip["errors"] >= 3:
                clip["status"] = "erreur"
                done.append(item)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    queue = [q for q in queue if q not in done]
    C.save_json(DB_FILE, db)
    C.save_json(QUEUE_FILE, queue)
    C.save_json(MONTAGES_FILE, montages)


def compil(lang):
    import montage
    db = C.load_json(DB_FILE)
    picks = [c for c in db.values() if c.get("compil") and not c.get(f"compil_fait_{lang}")
             and (c["lang"] == lang or c.get("cross"))]
    picks = sorted(picks, key=lambda c: c["views"], reverse=True)[:10]
    if len(picks) < 3:
        print(f"[{lang}] pas assez de clips ⭐ pour une compilation ({len(picks)})")
        return
    title = {"fr": f"TOP {len(picks)} DE LA SEMAINE", "en": f"TOP {len(picks)} OF THE WEEK",
             "es": f"TOP {len(picks)} DE LA SEMANA"}.get(lang, f"TOP {len(picks)}")
    work = C.OUT / f"compil_{lang}"
    path = montage.render_compilation(picks, title, work, out_lang=lang)
    tag = f"compil-{lang}-{datetime.now(timezone.utc):%Y%m%d-%H%M}"
    link = ""
    try:  # trop lourde pour Discord : déposée dans les Releases GitHub
        subprocess.run(["gh", "release", "create", tag, str(path), "--title", f"{title} ({lang})",
                        "--notes", "Compilation générée automatiquement"], check=True)
        link = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/releases/tag/{tag}"
    except Exception as e:
        print(f"⚠️ Envoi dans les Releases impossible : {e}")
    credits = ", ".join(sorted({c["streamer"] for c in picks}))
    ch = C.channel("MONTAGES", lang)
    if ch:
        D.send(ch, f"🎬 **{title}** prête ({len(picks)} clips)\n{link}\nCrédits : {credits}")
    for c in picks:
        c[f"compil_fait_{lang}"] = True
    C.save_json(DB_FILE, db)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "render":
        render()
    elif cmd == "compil":
        for lang in (sys.argv[2:] or C.LANGS):
            compil(lang)
