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
    "es": {
        "rage": ["UN STREAMER PIERDE LOS NERVIOS EN DIRECTO", "{s} EXPLOTA: LOS VECINOS LO OYERON TODO",
                 "CRISIS DE NERVIOS EN VICE CITY: {s} ROMPE SU SILENCIO"],
        "fail": ["ROBA UN COCHE Y SE ARREPIENTE AL INSTANTE", "{s}: LA TRAGEDIA QUE NADIE VIO VENIR",
                 "NO VAS A CREER LO QUE HIZO {s}"],
        "incroyable": ["{s} LOGRA LO IMPOSIBLE, LOS EXPERTOS SIN PALABRAS", "LO QUE HIZO {s} TE VA A IMPACTAR",
                       "LOS NPC TODAVÍA NO SE LO CREEN"],
        "decouverte": ["LO QUE ROCKSTAR NO QUERÍA QUE SUPIERAS", "{s} DESCUBRE UN SECRETO DE GTA 6",
                       "REVELADO: EL DETALLE QUE LO CAMBIA TODO"],
        "course": ["PERSECUCIÓN: LA POLICÍA DE VICE CITY HUMILLADA", "{s} DEJA ATRÁS A LA POLICÍA",
                   "FUGA ESPECTACULAR: UN TESTIGO LO CUENTA"],
        "drole": ["INSÓLITO: {s} DEJA EN SHOCK A VICE CITY", "ESCÁNDALO: LOS NPC DENUNCIAN A {s}",
                  "TODO SOBRE EL INCIDENTE DE {s}"],
    },
    "fr": {
        "rage": ["UN STREAMER PERD LES PÉDALES EN DIRECT", "{s} CRAQUE : LES VOISINS ONT TOUT ENTENDU",
                 "CRISE DE NERFS À VICE CITY : {s} SORT DU SILENCE"],
        "fail": ["IL VOLE UN VÉHICULE ET LE REGRETTE AUSSITÔT", "{s} : LE DRAME QUE PERSONNE N'AVAIT VU VENIR",
                 "VOUS N'ALLEZ PAS CROIRE CE QUE {s} A FAIT"],
        "incroyable": ["{s} RÉALISE L'IMPOSSIBLE, LES EXPERTS SANS VOIX", "CE QUE {s} A FAIT VA VOUS CHOQUER",
                       "LES PNJ N'EN REVIENNENT TOUJOURS PAS"],
        "decouverte": ["CE QUE ROCKSTAR NE VOULAIT PAS QUE VOUS SACHIEZ", "{s} DÉCOUVRE UN SECRET DE GTA 6",
                       "RÉVÉLATIONS : LE DÉTAIL QUI CHANGE TOUT"],
        "course": ["COURSE-POURSUITE : LA POLICE DE VICE CITY HUMILIÉE", "{s} SÈME LA POLICE ET LE CHAOS",
                   "FUITE SPECTACULAIRE : UN TÉMOIN RACONTE"],
        "drole": ["INSOLITE : {s} PROVOQUE LA STUPEUR À VICE CITY", "SCANDALE : LES PNJ PORTENT PLAINTE CONTRE {s}",
                  "ON VOUS DIT TOUT SUR L'INCIDENT {s}"],
    },
    "en": {
        "rage": ["STREAMER LOSES IT LIVE ON AIR", "{s} SNAPS: NEIGHBORS HEARD EVERYTHING",
                 "MELTDOWN IN VICE CITY: {s} BREAKS SILENCE"],
        "fail": ["MAN STEALS CAR, IMMEDIATELY REGRETS IT", "{s}: THE TRAGEDY NOBODY SAW COMING",
                 "YOU WON'T BELIEVE WHAT {s} JUST DID"],
        "incroyable": ["{s} DOES THE IMPOSSIBLE, EXPERTS SPEECHLESS", "WHAT {s} DID WILL SHOCK YOU",
                       "NPCS STILL CAN'T BELIEVE IT"],
        "decouverte": ["WHAT ROCKSTAR DIDN'T WANT YOU TO KNOW", "{s} UNCOVERS A GTA 6 SECRET",
                       "REVEALED: THE DETAIL THAT CHANGES EVERYTHING"],
        "course": ["HIGH-SPEED CHASE: VICE CITY POLICE HUMILIATED", "{s} LEAVES COPS IN THE DUST",
                   "DRAMATIC ESCAPE: WITNESS SPEAKS OUT"],
        "drole": ["BIZARRE: {s} STUNS VICE CITY", "SCANDAL: NPCS FILE COMPLAINT AGAINST {s}",
                  "EVERYTHING WE KNOW ABOUT THE {s} INCIDENT"],
    },
}

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


def _claude(prompt: str, max_tokens: int = 700) -> str:
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
        "x-api-key": C.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": C.ANTHROPIC_MODEL, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def _json(text: str):
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0])
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
    s = clip["streamer"].upper()
    rnd = random.Random(seed)
    headline = rnd.choice(HEADLINES[lang][category]).format(s=s)
    ticker = [t.format(s=s) for t in rnd.sample(TICKERS[lang][category], k=min(2, len(TICKERS[lang][category])))]
    title = headline.capitalize() + " 📰"
    return {"headline": headline, "ticker": ticker, "title": title,
            "caption": _caption(clip, lang, title, category)}


def _ai(clip, category, transcript, lang):
    lang_name = {"fr": "français", "en": "English", "es": "español"}.get(lang, lang)
    prompt = (
        "Tu écris pour NPC Society, une page TikTok/Instagram qui parodie les chaînes d'info et la presse à "
        "scandale : chaque moment de streamer sur GTA 6 est traité comme un fait divers. "
        f"Écris en {lang_name}. Streamer : {clip['streamer']}. Catégorie : {category}. "
        f"Titre du clip sur Twitch : « {clip['title']} ». Ce qui se dit dans le clip : « {transcript[:1500]} ».\n"
        "Donne :\n"
        "- headline : gros titre racoleur en MAJUSCULES, 5 à 10 mots, lié à ce qui se passe vraiment dans le clip ;\n"
        "- ticker : 2 commentaires moqueurs façon bandeau d'info en MAJUSCULES (6 à 10 mots chacun), qui "
        "commentent l'action précise du clip avec ironie (faux témoignages, fausses réactions officielles, "
        "pince-sans-rire) ;\n"
        "- title : le gros titre réécrit normalement avec 1 emoji, pour la légende.\n"
        "Règles : on se moque de la situation, jamais de la personne ; pas d'insulte, pas de politique, "
        "pas de vrai média cité. Réponds uniquement en JSON : {\"headline\": \"\", \"ticker\": [\"\", \"\"], \"title\": \"\"}"
    )
    d = _json(_claude(prompt))
    return {"headline": d["headline"], "ticker": d["ticker"][:3], "title": d["title"],
            "caption": _caption(clip, lang, d["title"], category)}


def describe(clip, category, transcript="", seed=None, lang=None):
    seed = seed or clip["id"]
    lang = lang or clip["lang"]
    if C.ANTHROPIC_API_KEY:
        try:
            return _ai(clip, category, transcript, lang)
        except Exception as e:
            print(f"⚠️ IA indisponible, modèle de texte utilisé : {e}")
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
