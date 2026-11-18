"""
Textes de NPC Society : gros titre racoleur, commentaires moqueurs pour le bandeau défilant,
légende + hashtags, et traduction des sous-titres pour les versions croisées FR <-> EN.
Avec ANTHROPIC_API_KEY : textes écrits sur mesure à partir de ce qui se passe dans le clip.
Sans clé : modèles de texte par catégorie.
"""
import json
import random

import requests

import config as C
from categorize import CATEGORIES

HEADLINES = {
    "fr": {
        "rage": ["{s} PERD SON CALME SUR GTA 6", "LE MOMENT OÙ {s} CRAQUE EN DIRECT", "{s} VS GTA 6 : LA PATIENCE A LÂCHÉ"],
        "fail": ["{s} TENTE UN TRUC… ÇA TOURNE MAL", "{s} AVAIT UN PLAN. LE PLAN N'A PAS TENU", "GROSSE BOULETTE DE {s} SUR GTA 6"],
        "incroyable": ["{s} RÉUSSIT UN COUP INCROYABLE SUR GTA 6", "PERSONNE NE S'ATTENDAIT À ÇA DE {s}", "{s} SORT UNE ACTION FOLLE"],
        "decouverte": ["{s} TOMBE SUR UN DÉTAIL FOU DE GTA 6", "CE QUE {s} DÉCOUVRE DANS GTA 6", "{s} EXPLORE GTA 6 ET TROUVE ÇA"],
        "course": ["{s} CONTRE LA POLICE DE GTA 6", "COURSE-POURSUITE MOUVEMENTÉE POUR {s}", "{s} TENTE DE SEMER LA POLICE"],
        "drole": ["{s} ET GTA 6, ÇA DONNE ÇA", "LA SCÈNE ABSURDE DE {s} SUR GTA 6", "{s} NE S'ATTENDAIT PAS À ÇA"],
    },
    "en": {
        "rage": ["{s} LOSES HIS COOL IN GTA 6", "THE MOMENT {s} SNAPS LIVE", "{s} VS GTA 6: PATIENCE IS GONE"],
        "fail": ["{s} TRIES SOMETHING… IT GOES WRONG", "{s} HAD A PLAN. THE PLAN DID NOT SURVIVE", "BIG GTA 6 BLUNDER BY {s}"],
        "incroyable": ["{s} PULLS OFF SOMETHING INSANE IN GTA 6", "NOBODY EXPECTED THIS FROM {s}", "{s}'S WILDEST GTA 6 MOVE"],
        "decouverte": ["{s} FINDS A CRAZY GTA 6 DETAIL", "WHAT {s} JUST FOUND IN GTA 6", "{s} EXPLORES GTA 6 AND FINDS THIS"],
        "course": ["{s} VS THE GTA 6 POLICE", "A WILD CHASE FOR {s}", "{s} TRIES TO LOSE THE COPS"],
        "drole": ["{s} + GTA 6 = THIS", "{s}'S MOST ABSURD GTA 6 SCENE", "{s} DID NOT SEE THAT COMING"],
    },
    "es": {
        "rage": ["{s} PIERDE LA CALMA EN GTA 6", "EL MOMENTO EN QUE {s} EXPLOTA EN DIRECTO", "{s} VS GTA 6: SE ACABÓ LA PACIENCIA"],
        "fail": ["{s} INTENTA ALGO… Y SALE MAL", "{s} TENÍA UN PLAN. EL PLAN NO AGUANTÓ", "GRAN METEDURA DE PATA DE {s}"],
        "incroyable": ["{s} LOGRA ALGO INCREÍBLE EN GTA 6", "NADIE ESPERABA ESTO DE {s}", "LA JUGADA MÁS LOCA DE {s}"],
        "decouverte": ["{s} ENCUENTRA UN DETALLE LOCO DE GTA 6", "LO QUE {s} DESCUBRE EN GTA 6", "{s} EXPLORA GTA 6 Y ENCUENTRA ESTO"],
        "course": ["{s} CONTRA LA POLICÍA DE GTA 6", "UNA PERSECUCIÓN DE LOCOS PARA {s}", "{s} INTENTA DESPISTAR A LA POLICÍA"],
        "drole": ["{s} + GTA 6 = ESTO", "LA ESCENA MÁS ABSURDA DE {s}", "{s} NO SE ESPERABA ESTO"],
    },
}

ANON = {"fr": "UN JOUEUR", "en": "THIS PLAYER", "es": "UN JUGADOR"}


def is_known(clip):
    """Streamer connu du grand public (gros ou moyen) : on peut miser sur son nom. Sinon, on mise sur l'action."""
    return clip.get("tier") in ("gros", "moyen") or (clip.get("views") or 0) >= 1500


FILLER = {"mdr", "ptdr", "lol", "lmao", "kekw", "omegalul", "xd", "jaja", "jajaja", "wtf", "clip", "gta", "gta6",
          "gtavi", "6", "vi", "lul", "pog", "poggers", "jpp"}


def headline_from_title(clip):
    """Le titre du clip Twitch (écrit par les viewers) décrit souvent bien l'action : on s'en sert s'il est exploitable."""
    import re as _re
    title = _re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D#@]", " ", clip.get("title", ""))
    words = [w for w in title.split() if w.lower().strip(".,!?:;") not in FILLER]
    if len(words) < 4 or len(" ".join(words)) > 70:
        return None
    text = " ".join(words).strip(" -:.,!").upper()
    s = clip["streamer"].upper()
    if not is_known(clip):  # petit streamer : son nom n'accroche personne, on mise sur l'action
        anon = ANON.get(clip.get("lang"), "THIS PLAYER")
        text = text.replace(s, anon).strip(" -:.,!") if s in text else text
        return text if len(text.split()) >= 3 else None
    return text if s in text else f"{s} : {text}"


# Commentaires moqueurs du bandeau défilant (utilisés sans clé IA)
TICKERS = {
    "es": {
        "rage": ["{s} ASEGURA QUE ESTÁ «MUY TRANQUILO»", "EL MANDO PRESENTA UNA DENUNCIA", "LOS VECINOS PIDEN SILENCIO"],
        "fail": ["{s} LO TENÍA «TODO CALCULADO»", "LAS ASEGURADORAS NO HACEN COMENTARIOS",
                 "UN NPC DECLARA: «VINO DIRECTO HACIA MÍ»"],
        "incroyable": ["LOS NPC PIDEN LA REPETICIÓN", "{s} AÚN NO HA EXPLICADO CÓMO", "LOS FÍSICOS DE LEONIDA, PERPLEJOS"],
        "decouverte": ["ROCKSTAR NO QUISO RESPONDER", "{s} SIGUE HUMILDE TRAS SU DESCUBRIMIENTO", "LAS TEORÍAS SE DISPARAN"],
        "course": ["LA POLICÍA DE VICE CITY PIDE REFUERZOS", "{s} SIGUE IGNORANDO EL CÓDIGO DE CIRCULACIÓN",
                   "NINGÚN SEMÁFORO FUE RESPETADO"],
        "drole": ["{s} NIEGA TODA RESPONSABILIDAD", "LOS NPC EN SHOCK", "SE HA ABIERTO UN GABINETE PSICOLÓGICO"],
    },
    "fr": {
        "rage": ["{s} ASSURE QU'IL EST « TRÈS CALME »", "LA MANETTE PORTE PLAINTE", "LES VOISINS DEMANDENT LE SILENCE"],
        "fail": ["{s} AVAIT POURTANT « TOUT CALCULÉ »", "LES ASSURANCES REFUSENT DE COMMENTER",
                 "UN PNJ TÉMOIGNE : « IL M'A FONCÉ DESSUS »"],
        "incroyable": ["LES PNJ DEMANDENT UN RALENTI", "{s} N'A TOUJOURS PAS EXPLIQUÉ COMMENT",
                       "LES PHYSICIENS DE LEONIDA PERPLEXES"],
        "decouverte": ["ROCKSTAR N'A PAS SOUHAITÉ RÉPONDRE", "{s} RESTE MODESTE APRÈS SA DÉCOUVERTE",
                       "LES THÉORIES FUSENT SUR LES RÉSEAUX"],
        "course": ["LA POLICE DE VICE CITY DEMANDE DES RENFORTS", "{s} IGNORE TOUJOURS LE CODE DE LA ROUTE",
                   "AUCUN FEU ROUGE N'A ÉTÉ RESPECTÉ"],
        "drole": ["{s} NIE TOUTE RESPONSABILITÉ", "LES PNJ SOUS LE CHOC", "UNE CELLULE PSYCHOLOGIQUE A ÉTÉ OUVERTE"],
    },
    "en": {
        "rage": ["{s} CLAIMS HE IS \"TOTALLY CALM\"", "CONTROLLER PRESSES CHARGES", "NEIGHBORS ASK FOR SILENCE"],
        "fail": ["{s} SAYS IT WAS \"ALL PART OF THE PLAN\"", "INSURERS DECLINE TO COMMENT",
                 "NPC SPEAKS: \"HE DROVE STRAIGHT AT ME\""],
        "incroyable": ["NPCS REQUEST A REPLAY", "{s} STILL HASN'T EXPLAINED HOW", "LEONIDA PHYSICISTS BAFFLED"],
        "decouverte": ["ROCKSTAR DECLINED TO COMMENT", "{s} STAYS HUMBLE AFTER DISCOVERY", "THEORIES SPREAD ONLINE"],
        "course": ["VICE CITY POLICE CALL FOR BACKUP", "{s} STILL IGNORES TRAFFIC LAWS", "NO RED LIGHT WAS RESPECTED"],
        "drole": ["{s} DENIES ALL RESPONSIBILITY", "NPCS IN SHOCK", "GRIEF COUNSELORS ON SITE"],
    },
}

FOOT = {
    "es": {"credit": "🎥 {s} — twitch.tv/{l} (pásate a apoyarle)",
           "cta": "📰 Síguenos: NPC Society cubre todos los sucesos de GTA 6."},
    "fr": {"credit": "🎥 {s} — twitch.tv/{l} (allez le soutenir)",
           "cta": "📰 Abonne-toi : NPC Society couvre tous les faits divers de GTA 6."},
    "en": {"credit": "🎥 {s} — twitch.tv/{l} (go support them)",
           "cta": "📰 Follow NPC Society for every GTA 6 headline."},
}


USAGE_FILE = C.DATA / "ai_usage.json"


def _count_call():
    """Plafond quotidien d'appels IA (AI_MAX_CALLS_PER_DAY). Au-delà : modèles de texte gratuits."""
    from datetime import date
    usage = C.load_json(USAGE_FILE)
    today = date.today().isoformat()
    n = usage.get(today, 0)
    if n >= C.AI_MAX_CALLS_PER_DAY:
        raise RuntimeError(f"plafond quotidien atteint ({C.AI_MAX_CALLS_PER_DAY} appels IA)")
    usage = {k: v for k, v in usage.items() if k >= today[:8]}  # on garde le mois en cours
    usage[today] = n + 1
    C.save_json(USAGE_FILE, usage)


ERRORS_FILE = C.DATA / "ai_errors.json"


def _log_error(where, e, resp=None):
    """Garde les 10 dernières erreurs IA (sans la clé) dans data/ai_errors.json pour le diagnostic."""
    from datetime import datetime, timezone
    errs = C.load_json(ERRORS_FILE, default=[])
    detail = str(e)[:300]
    if resp is not None:
        detail += f" | HTTP {resp.status_code} : {resp.text[:400]}"
    errs = (errs + [{"quand": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "où": where,
                      "erreur": detail}])[-10:]
    C.save_json(ERRORS_FILE, errs)


def _claude(prompt: str, max_tokens: int = 700, images=None) -> str:
    """Appel au modèle. images = liste de chemins .jpg (le modèle « voit » le clip)."""
    import base64
    _count_call()
    content = []
    for p in images or []:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode(open(p, "rb").read()).decode()}})
    content.append({"type": "text", "text": prompt})
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
        "x-api-key": C.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": C.ANTHROPIC_MODEL, "max_tokens": max(max_tokens, 1500),
              "thinking": {"type": "disabled"},
              "messages": [{"role": "user", "content": content}]})
    if r.status_code == 400 and "thinking" in r.text:  # si le modèle refuse ce réglage, on réessaie sans
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
            "x-api-key": C.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": C.ANTHROPIC_MODEL, "max_tokens": 4000, "messages": [{"role": "user", "content": content}]})
    if r.status_code != 200:
        _log_error("api", RuntimeError("réponse en erreur"), r)
        r.raise_for_status()
    data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if not text.strip():
        kinds = [b.get("type") for b in data.get("content", [])]
        _log_error("api", RuntimeError(f"réponse sans texte : stop={data.get('stop_reason')} blocs={kinds} "
                                       f"usage={data.get('usage')}"))
        raise RuntimeError("réponse IA vide")
    return text


def _json(text: str):
    found = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not found:
        raise ValueError(f"pas de JSON dans la réponse : {text[:200]!r}")
    start = min(found)
    end = max(text.rfind("}"), text.rfind("]")) + 1
    return json.loads(text[start:end])


def _caption(clip, lang, title, category):
    f = FOOT.get(lang, FOOT["en"])
    s = clip["streamer"]
    tags = list(C.BRAND.get("hashtags", {}).get(lang, ["#GTA6"]))
    tags.append("#" + "".join(ch for ch in s if ch.isalnum()))
    tags.append("#" + CATEGORIES[category]["label"]["en"].split()[0].lower())
    return f"{title}\n\n{f['credit'].format(s=s, l=s.lower())}\n{f['cta']}\n\n{' '.join(tags)}"


def _template(clip, category, seed, lang):
    lang = lang if lang in HEADLINES else "en"
    s = clip["streamer"].upper() if is_known(clip) else ANON.get(lang, "THIS PLAYER")
    rnd = random.Random(seed)
    headline = (headline_from_title(clip) if lang == clip.get("lang") else None) \
        or rnd.choice(HEADLINES[lang][category]).format(s=s)
    ticker = [t.format(s=s) for t in rnd.sample(TICKERS[lang][category], k=min(2, len(TICKERS[lang][category])))]
    title = headline.capitalize() + " 📰"
    return {"headline": headline, "ticker": ticker, "title": title,
            "caption": _caption(clip, lang, title, category)}


def _ai(clip, category, transcript, lang, frames=None):
    lang_name = {"fr": "français", "en": "English", "es": "español"}.get(lang, lang)
    known = is_known(clip)
    example = {"fr": "UN JOUEUR VOLE UN AVION ET FINIT DANS L'OCÉAN",
               "en": "PLAYER STEALS A PLANE, ENDS UP IN THE OCEAN",
               "es": "UN JUGADOR ROBA UN AVIÓN Y ACABA EN EL MAR"}.get(lang, "")
    prompt = (
        "Tu travailles pour NPC Society, une page TikTok/Instagram qui reprend les moments marquants de streamers "
        "sur GTA 6, avec un habillage de chaîne d'info légèrement satirique.\n"
        f"Les images jointes viennent du clip, dans l'ordre. Streamer : {clip['streamer']} "
        f"({'connu' if known else 'peu connu'}). Titre du clip sur Twitch : « {clip['title']} ». "
        f"Catégorie devinée : {category}. Ce qui se dit : « {transcript[:1500] or '(rien de clair)'} ».\n\n"
        "1) ANALYSE (sois strict) :\n"
        "- gameplay : true seulement si les images montrent bien le jeu GTA en train d'être joué. false si c'est "
        "surtout autre chose (vidéo YouTube regardée en réaction, film, IRL, écran d'attente, menu, discussion "
        "face caméra sans jeu).\n"
        "- nudite : true si on voit de la nudité ou un contenu sexuel, même dans le jeu.\n"
        "- safe : false si propos haineux, harcèlement, contenu sexuel explicite, infos personnelles, vraie mise en danger.\n"
        "- score : de 1 à 10, à quel point le clip est drôle OU intéressant pour quelqu'un qui scrolle. Sois exigeant : "
        "1-4 = banal, peu d'action, discussion ou menu, incompréhensible sans contexte ; 5-6 = correct ; "
        "7+ = il se passe vraiment quelque chose (réaction forte, chaos, exploit, absurde, découverte).\n"
        "- categorie : rage, fail, incroyable, decouverte, course ou drole.\n"
        f"2) TEXTES en {lang_name} :\n"
        "- headline : titre en MAJUSCULES, 6 à 11 mots, façon titre de média accrocheur, qui DÉCRIT L'ACTION visible "
        "(qui fait quoi, avec quoi, où, et ce qui tourne mal ou bien), pour qu'on comprenne le sujet sans le son. "
        "L'action passe avant le streamer : "
        + (f"tu peux citer {clip['streamer']} si ça aide, mais l'action doit être claire. " if known else
           f"ne cite PAS le pseudo, dis « un joueur » ou décris le personnage (exemple : « {example} »). ") +
        "Ton taquin, un peu moqueur ;\n"
        "- ticker : 2 courts commentaires ironiques en MAJUSCULES (6 à 10 mots) sur l'action précise ;\n"
        "- title : le titre réécrit normalement avec 1 emoji, pour la légende.\n"
        "Règles : jamais insultant ni humiliant ; jamais trompeur (n'invente ni fait, ni chiffre, ni citation absents "
        "du clip) ; pas de politique ; pas de vrai média cité. Si l'action est floue, reste général.\n"
        "Réponds uniquement en JSON : {\"gameplay\": true, \"nudite\": false, \"safe\": true, \"score\": 7, "
        "\"raison\": \"...\", \"categorie\": \"drole\", \"headline\": \"\", \"ticker\": [\"\", \"\"], \"title\": \"\"}"
    )
    d = _json(_claude(prompt, 700, images=frames))
    analysis = {"categorie": d.get("categorie") if d.get("categorie") in CATEGORIES else None,
                "gameplay": bool(d.get("gameplay", True)), "nudite": bool(d.get("nudite", False)),
                "safe": bool(d.get("safe", True)), "score": int(d.get("score", 5)), "raison": d.get("raison", "")}
    return {"headline": d["headline"], "ticker": d["ticker"][:3], "title": d["title"],
            "caption": _caption(clip, lang, d["title"], category), "analysis": analysis}


def describe(clip, category, transcript="", seed=None, lang=None, frames=None):
    """Titres + analyse du clip (images + transcription). Sans clé IA : modèles de texte, pas d'analyse."""
    seed = seed or clip["id"]
    lang = lang or clip["lang"]
    if C.ANTHROPIC_API_KEY:
        try:
            return _ai(clip, category, transcript, lang, frames)
        except Exception as e:
            print(f"⚠️ IA indisponible, modèle de texte utilisé : {e}")
            _log_error("describe", e)
    return _template(clip, category, seed, lang)


def translate_segments(segments, src, dst):
    """Traduit des segments [(début, fin, texte)] en gardant le minutage. Nécessite ANTHROPIC_API_KEY."""
    if not C.ANTHROPIC_API_KEY or not segments:
        return []
    names = {"fr": "français", "en": "anglais", "es": "espagnol", "de": "allemand"}
    payload = [{"i": i, "t": t} for i, (_, _, t) in enumerate(segments)]
    prompt = (f"Traduis ces sous-titres de streamer du {names.get(src, src)} vers le {names.get(dst, dst)}, "
              "en langage oral et naturel (argot gaming compris), en gardant le ton et les insultes légères "
              "atténuées. Garde le même nombre d'éléments et les mêmes « i ». Réponds uniquement en JSON : "
              f"[{{\"i\": 0, \"t\": \"...\"}}].\n{json.dumps(payload, ensure_ascii=False)}")
    try:
        out = {d["i"]: d["t"] for d in _json(_claude(prompt, 2000))}
        return [(s, e, out.get(i, t)) for i, (s, e, t) in enumerate(segments)]
    except Exception as e:
        print(f"⚠️ Traduction IA impossible : {e}")
        return []


def rate_clip(clip, transcript, category):
    """Note IA du clip : drôle ou intéressant (1-10) et publiable (pas de propos haineux, sexuels, etc.).
    Renvoie None sans clé API (le clip est alors gardé)."""
    if not C.ANTHROPIC_API_KEY:
        return None
    prompt = (
        "Tu tries des clips de streamers sur GTA 6 pour une page TikTok/Instagram d'humour. "
        f"Streamer : {clip['streamer']}. Titre du clip : « {clip['title']} ». Catégorie : {category}. "
        f"Ce qui se dit : « {transcript[:2000]} ».\n"
        "Note de 1 à 10 à quel point ce clip est drôle OU intéressant pour quelqu'un qui scrolle "
        "(réaction forte, situation absurde, exploit, découverte ; 1-4 = banal ou incompréhensible sans contexte). "
        "safe = false si le clip contient des propos haineux, du harcèlement, du contenu sexuel explicite, "
        "des infos personnelles ou une vraie mise en danger. "
        "Réponds uniquement en JSON : {\"score\": 7, \"safe\": true, \"raison\": \"...\"}"
    )
    try:
        d = _json(_claude(prompt, 300))
        return {"score": int(d.get("score", 5)), "safe": bool(d.get("safe", True)), "raison": d.get("raison", "")}
    except Exception as e:
        print(f"⚠️ Note IA impossible : {e}")
        return None
