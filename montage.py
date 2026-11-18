"""
Montage automatique façon tabloïd (NPC Society), vidéo verticale 1080x1920 :
- détection de la facecam, sinon fond flouté
- sous-titres animés (Whisper), accroche, crédit du streamer, signature de la marque
- zooms sur les moments forts (pics audio) + mème texte + bruitage au pic principal
"""
import json
import math
import random
import re
import shutil
import subprocess
from pathlib import Path

import config as C
from categorize import categorize

W, H, FPS = 1080, 1920, 30
CAM_Y, CAM_H = 390, 480          # bandeau facecam (format 9:4, le visage respire)
GAME_H = 608                     # le jeu en 16:9 sur toute la largeur (mise en page facecam)
GAME_H_FULL = 810                # sans facecam : jeu plus grand (recadré en 4:3), moins de vide
LOGO_POS = (36, 48)
_whisper = None


# --- Outils -----------------------------------------------------------------
def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Commande échouée : {' '.join(map(str, cmd[:6]))}…\n{p.stderr[-2500:]}")
    return p.stdout


def probe(path: Path) -> dict:
    info = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                           "-show_format", str(path)]))
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    return {"w": int(v["width"]), "h": int(v["height"]), "dur": float(info["format"]["duration"]),
            "audio": any(s["codec_type"] == "audio" for s in info["streams"])}


def strip_emoji(text: str) -> str:
    return re.sub(r"[\U0001F000-\U0001FAFF☀-➿️‍]", "", text).strip()


def ass_text(text: str) -> str:
    return strip_emoji(text).replace("{", "(").replace("}", ")").replace("\n", " ").upper()


def ts(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


# --- Étapes -----------------------------------------------------------------
def download(url: str, dest: Path) -> Path:
    import yt_dlp
    dest.parent.mkdir(parents=True, exist_ok=True)
    opts = {"outtmpl": str(dest), "format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True,
            "overwrites": True}
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])
    return dest


def _model():
    global _whisper
    from faster_whisper import WhisperModel
    if _whisper is None:
        _whisper = WhisperModel(C.WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper


def transcribe(path: Path, lang: str) -> dict:
    """{'words': [(début, fin, mot)], 'segments': [(début, fin, texte)]}. Vide si Whisper indisponible."""
    try:
        segs, _ = _model().transcribe(str(path), language=lang, word_timestamps=True, vad_filter=True)
        segs = list(segs)
        return {"words": [(w.start, w.end, w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()],
                "segments": [(s.start, s.end, s.text.strip()) for s in segs if s.text.strip()]}
    except Exception as e:  # le montage continue sans sous-titres
        print(f"⚠️ Transcription impossible : {e}")
        return {"words": [], "segments": []}


def whisper_to_english(path: Path, lang: str) -> list:
    """Traduction directe vers l'anglais par Whisper (gratuit, sans clé API)."""
    try:
        segs, _ = _model().transcribe(str(path), language=lang, task="translate", vad_filter=True)
        return [(s.start, s.end, s.text.strip()) for s in segs if s.text.strip()]
    except Exception as e:
        print(f"⚠️ Traduction Whisper impossible : {e}")
        return []


def words_from_segments(segments) -> list:
    """Répartit le texte (traduit) d'un segment en mots horodatés, au prorata des lettres."""
    words = []
    for start, end, text in segments:
        toks = text.split()
        total = sum(len(t) for t in toks) or 1
        t = start
        for tok in toks:
            d = (end - start) * len(tok) / total
            words.append((t, t + d, tok))
            t += d
    return words


def audio_peaks(path: Path, dur: float, max_peaks: int = 3) -> list:
    """Moments les plus forts (cris, rires, explosions), du plus fort au moins fort."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    if not raw:
        return []
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    win = 800  # 100 ms
    n = len(x) // win
    if n < 10:
        return []
    rms = np.sqrt((x[: n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-9)
    rms = np.convolve(rms, np.ones(3) / 3, mode="same")
    thr = rms.mean() + 2.0 * rms.std()   # seul un vrai pic (cri, rire, explosion) déclenche le zoom
    peaks = []
    for i in np.argsort(rms)[::-1]:
        t = i * 0.1
        if rms[i] < thr or len(peaks) >= max_peaks:
            break
        if 1.0 < t < dur - 0.5 and all(abs(t - p) > 2.5 for p in peaks):
            peaks.append(round(float(t), 2))
    return peaks


class UnsafeClip(Exception):
    """Clip écarté automatiquement (nudité, hors jeu, sans intérêt)."""


def sample_frames(src: Path, work: Path, dur: float, n: int = 6, peak=None) -> list:
    """Quelques images du clip (petites) pour que l'IA « voie » ce qui se passe. Liste de (chemin, seconde)."""
    fdir = work / "ia"
    fdir.mkdir(parents=True, exist_ok=True)
    times = [dur * (k + 0.5) / n for k in range(n)]
    if peak is not None:
        times[-1] = min(peak + 0.3, dur - 0.1)
    out = []
    for k, t in enumerate(sorted(times)):
        p = fdir / f"i{k}.jpg"
        try:
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                 "-vf", "scale=640:-2", "-q:v", "5", str(p)])
            out.append((p, round(t, 1)))
        except RuntimeError:
            pass
    return out


NSFW_CLASSES = {"FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED",
                "BUTTOCKS_EXPOSED", "ANUS_EXPOSED"}


def nsfw_check(src: Path, work: Path, frames: int = 10, threshold: float = 0.45):
    """Analyse quelques images du clip avec NudeNet. Renvoie (ok, détail)."""
    try:
        from nudenet import NudeDetector
    except ImportError:
        print("⚠️ NudeNet absent : contrôle de nudité désactivé")
        return True, ""
    info = probe(src)
    fdir = work / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", f"fps={frames / max(info['dur'], 1):.4f},scale=960:-2",
         "-frames:v", str(frames), str(fdir / "f%02d.jpg")])
    det = NudeDetector()
    hits = []
    for f in sorted(fdir.glob("*.jpg")):
        for d in det.detect(str(f)):
            if d.get("class") in NSFW_CLASSES and d.get("score", 0) >= threshold:
                hits.append(d["class"])
    return (len(hits) < 2), ", ".join(sorted(set(hits)))  # 2 détections minimum pour éviter les faux positifs


def nsfw_timeline(src: Path, work: Path, fps: float = 2.0, threshold: float = 0.45):
    """Moments de nudité dans le clip : liste d'intervalles (début, fin) et part du clip concernée."""
    try:
        from nudenet import NudeDetector
    except ImportError:
        print("⚠️ NudeNet absent : contrôle de nudité désactivé")
        return [], 0.0
    info = probe(src)
    fdir = work / "frames"
    shutil.rmtree(fdir, ignore_errors=True)
    fdir.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", f"fps={fps},scale=960:-2", str(fdir / "f%04d.jpg")])
    det = NudeDetector()
    flagged = []
    for k, f in enumerate(sorted(fdir.glob("*.jpg"))):
        if any(d.get("class") in NSFW_CLASSES and d.get("score", 0) >= threshold for d in det.detect(str(f))):
            flagged.append(k / fps)
    intervals = []
    for t in flagged:  # on regroupe et on ajoute une marge de sécurité
        a, b = max(t - 0.75, 0), min(t + 1 / fps + 0.75, info["dur"])
        if intervals and a <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], b)
        else:
            intervals.append((a, b))
    covered = sum(b - a for a, b in intervals) / max(info["dur"], 1)
    return [(round(a, 2), round(b, 2)) for a, b in intervals], covered


def _enable(intervals) -> str:
    return "+".join(f"between(t,{a},{b})" for a, b in intervals)


def _face_detector(w, h):
    """YuNet (réseau de neurones, bien meilleur sur les petites webcams) ; repli sur Haar si indisponible."""
    import cv2
    model = C.ASSETS / "models" / "face_detection_yunet_2023mar.onnx"
    if model.exists() and hasattr(cv2, "FaceDetectorYN"):
        det = cv2.FaceDetectorYN.create(str(model), "", (w, h), 0.6, 0.3, 50)

        def find(img):
            _, faces = det.detect(img)
            return [(f[0], f[1], f[2], f[3]) for f in (faces if faces is not None else [])]
        return find
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        return None
    return lambda img: list(cascade.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 6,
                                                     minSize=(int(w * 0.02), int(w * 0.02))))


def detect_facecam(path: Path, info: dict):
    """Cherche la webcam du streamer : un visage qui reste au même endroit d'une image à l'autre
    (les visages du jeu, eux, bougent). Renvoie la zone à recadrer (x, y, w, h) en pixels, ou None."""
    try:
        import cv2
    except ImportError:
        return None
    fw, fh = info["w"], info["h"]
    try:
        find = _face_detector(fw, fh)
    except Exception as e:
        print(f"⚠️ Détecteur de visage indisponible : {e}")
        return None
    if not find:
        return None
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    samples, hits = 14, []
    for k in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (k + 0.5) / samples))
        ok, frame = cap.read()
        if not ok:
            continue
        if frame.shape[1] != fw or frame.shape[0] != fh:
            frame = cv2.resize(frame, (fw, fh))
        for (x, y, w, h) in find(frame):
            if w < fw * 0.25:  # une webcam incrustée, pas un gros plan plein écran
                hits.append(((x + w / 2) / fw, (y + h / 2) / fh, w / fw, k))
    cap.release()
    if not hits:
        return None
    best = None  # on cherche le visage le plus stable (présent sur le plus d'images au même endroit)
    for cx, cy, _, _ in hits:
        group = [h for h in hits if abs(h[0] - cx) < 0.035 and abs(h[1] - cy) < 0.035]
        frames = len({h[3] for h in group})
        if not best or frames > best[0]:
            best = (frames, group)
    frames, group = best
    if frames < samples * 0.45:
        return None
    mx = sorted(h[0] for h in group)[len(group) // 2]
    my = sorted(h[1] for h in group)[len(group) // 2]
    face_w = sorted(h[2] for h in group)[len(group) // 2] * fw
    cw = min(face_w * 4.4, fw * 0.6)
    ch = cw * CAM_H / W
    x = min(max(mx * fw - cw / 2, 0), fw - cw)
    y = min(max(my * fh - ch * 0.45, 0), fh - ch)
    return tuple(int(v) // 2 * 2 for v in (x, y, cw, ch))


# --- Direction artistique « chaîne d'info satirique » ------------------------
def _bgr(hexrgb: str) -> str:
    return f"&H00{hexrgb[4:6]}{hexrgb[2:4]}{hexrgb[0:2]}"


def _col(name: str, default: str) -> str:
    return C.BRAND.get("colors", {}).get(name, default)


def ass_header() -> str:
    red, yel, blk = _bgr(_col("red", "E10600")), _bgr(_col("yellow", "FFD400")), _bgr(_col("black", "0E0E0E"))
    wht = "&H00FFFFFF"
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Head,Barlow Condensed ExtraBold,104,{blk},{wht},{yel},&H00000000,0,0,0,0,100,100,0,0,3,12,0,7,36,60,0,1
Style: Stamp,Archivo Black,54,{wht},{wht},{red},&H00000000,0,0,0,0,100,100,1,0,3,14,0,9,60,60,0,1
Style: Chyron,Barlow Condensed ExtraBold,46,{wht},{wht},{blk},&H00000000,0,0,0,0,100,100,1,0,3,11,0,7,0,0,0,1
Style: Ticker,Barlow Condensed ExtraBold,46,{wht},{wht},&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,4,0,0,0,1
Style: TickLbl,Barlow Condensed ExtraBold,46,{blk},{wht},{yel},&H00000000,0,0,0,0,100,100,1,0,3,14,0,4,0,0,0,1
Style: Band,Barlow Condensed,10,{red},{red},{red},&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Caption,Barlow Condensed Black,100,{wht},{wht},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,7,3,2,60,60,0,1
Style: Rank,Archivo Black,200,{yel},{wht},&H00000000,&HAA000000,0,0,0,0,100,100,0,0,1,10,6,5,60,60,0,1
Style: Kicker,Barlow Condensed ExtraBold,58,{wht},{wht},{red},&H00000000,0,0,0,0,100,100,2,0,3,12,0,8,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _seed_pick(options, seed):
    return random.Random(seed).choice(options) if options else None


def game_y(layout: str) -> int:
    return CAM_Y + CAM_H + 16 if layout == "facecam" else 470


def game_h(layout: str) -> int:
    return GAME_H if layout == "facecam" else GAME_H_FULL


def build_ass(path: Path, words, dur, txt, stamp, peak, streamer, lang, seed, layout, rank=None, brief=None,
              censored=None):
    b = C.BRAND
    end = ts(dur)
    ev = []
    red, wht = _bgr(_col("red", "E10600")), "&H00FFFFFF"
    gy = game_y(layout)
    gh = game_h(layout)
    bars = gy + gh                          # les barres d'info sont collées sous le clip

    # Gros titre racoleur sous le logo (le logo est incrusté en image)
    hy = 172
    hl = len(txt["headline"])
    hfs = 104 if hl <= 34 else 92 if hl <= 48 else 80   # titre long : police réduite pour rester sur 2-3 lignes
    ev.append(f"Dialogue: 5,0:00:00.05,{end},Head,,0,0,0,,{{\\fs{hfs}\\move(-1100,{hy},36,{hy},0,220)}}"
              f"{ass_text(txt['headline'])}")
    if brief:  # flash info : « BRÈVE 2/4 » en haut à droite
        word = {"fr": "BRÈVE", "es": "BREVE"}.get(lang, "BRIEF")
        ev.append(f"Dialogue: 6,0:00:00.00,{end},Kicker,,0,0,0,,{{\\an9\\pos({W - 36},52)}}{word} {brief[0]}/{brief[1]}")
    if rank is not None:
        ev.append(f"Dialogue: 6,0:00:00.00,{ts(min(dur, 3))},Rank,,0,0,0,,"
                  f"{{\\pos(540,{gy + gh // 2})\\fscx40\\fscy40\\t(0,160,\\fscx110\\fscy110)"
                  f"\\t(160,260,\\fscx100\\fscy100)}}#{rank}")

    # Barre « en direct » + bandeau défilant, juste sous le clip
    live = b.get("live", {}).get(lang, "LIVE")
    ev.append(f"Dialogue: 5,0:00:00.30,{end},Chyron,,0,0,0,,{{\\pos(0,{bars})\\fad(150,0)}}"
              f"  {{\\c{red}}}●{{\\c{wht}}} {ass_text(live)} · TWITCH.TV/{ass_text(streamer)}  ")
    band_y = bars + 68
    ev.append(f"Dialogue: 3,0:00:00.00,{end},Band,,0,0,0,,{{\\pos(0,{band_y})\\p1}}m 0 0 l {W} 0 l {W} 74 l 0 74{{\\p0}}")
    lines = list(txt.get("ticker") or [])
    extra = list(b.get("ticker", {}).get(lang, []))
    random.Random(seed + "t").shuffle(extra)
    seq = "   ●   ".join(ass_text(x) for x in (lines + extra[:2])) or ass_text(b.get("name", ""))
    speed = 170                                   # px/s ; le texte défile en boucle, le bandeau n'est jamais vide
    need = speed * dur + W
    reps = max(2, int(need / max(len(seq) * 19, 1)) + 2)
    crawl = ("   ●   ".join([seq] * reps))
    x0 = 330                                      # démarre déjà visible, juste après l'étiquette
    label = {"fr": "DERNIÈRE MINUTE", "es": "ÚLTIMA HORA"}.get(lang, "BREAKING NEWS")
    ev.append(f"Dialogue: 4,0:00:00.00,{end},Ticker,,0,0,0,,{{\\q2\\an4\\move({x0},{band_y + 38},{int(x0 - speed * dur)},"
              f"{band_y + 38},0,{int(dur * 1000)})}}{crawl}")
    ev.append(f"Dialogue: 6,0:00:00.00,{end},TickLbl,,0,0,0,,{{\\pos(14,{band_y + 38})}}{label}")

    # Sous-titres sur le bas du clip : blocs de 3 mots max, coupés aux pauses
    chunk, chunks = [], []
    for w in words:
        if chunk and (len(chunk) >= 3 or w[0] - chunk[-1][1] > 0.6):
            chunks.append(chunk)
            chunk = []
        chunk.append(w)
    if chunk:
        chunks.append(chunk)
    pop = r"{\fscx75\fscy75\t(0,110,\fscx106\fscy106)\t(110,190,\fscx100\fscy100)}"
    margin_v = H - (bars - 40)
    for i, ch in enumerate(chunks):
        start = ch[0][0]
        stop = min(ch[-1][1] + 0.25, chunks[i + 1][0][0] if i + 1 < len(chunks) else dur)
        ev.append(f"Dialogue: 2,{ts(start)},{ts(stop)},Caption,,0,0,{margin_v},,{pop}"
                  f"{ass_text(' '.join(x[2] for x in ch))}")

    # Tampon de presse au moment fort : petit autocollant dans le coin du clip (ne cache pas l'action)
    if stamp and peak is not None:
        anim = (f"{{\\an9\\pos({W - 28},{gy + 22})\\frz-4\\fscx180\\fscy180\\alpha&HFF&"
                f"\\t(0,140,\\fscx100\\fscy100\\alpha&H00&)}}")
        ev.append(f"Dialogue: 7,{ts(peak)},{ts(min(peak + 2.2, dur))},Stamp,,0,0,0,,{anim}{ass_text(stamp)}")
    # Passages masqués (nudité) : petite étiquette satirique sur le jeu
    word = {"fr": "CENSURÉ PAR LES PNJ", "es": "CENSURADO POR LOS NPC"}.get(lang, "CENSORED BY THE NPCS")
    for a, b in censored or []:
        ev.append(f"Dialogue: 7,{ts(a)},{ts(b)},Kicker,,0,0,0,,{{\\an7\\pos(24,{gy + 20})}}{word}")
    path.write_text(ass_header() + "\n".join(ev) + "\n", encoding="utf-8")


# --- Rendu ------------------------------------------------------------------
def pick_meme(lang: str, category: str, seed: str) -> dict:
    lib = C.MEMES.get(lang, {})
    entry = lib.get(category) or lib.get("drole") or {}
    stamp = _seed_pick(entry.get("stamps", []), seed + "s")
    sfx = _seed_pick(entry.get("sfx", []), seed + "x")
    reactions = [r for r in entry.get("reactions", []) if (C.ASSETS / "reactions" / lang / r).exists()]
    reaction = _seed_pick(reactions, seed + "r")
    return {"stamp": stamp, "sfx": sfx,
            "reaction": str(C.ASSETS / "reactions" / lang / reaction) if reaction else None}


def _esc(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:")


def encode(src: Path, out: Path, info, cam, peaks, ass_path, sfx: Path, sfx_at, target_mb, reaction=None,
           censor=None):
    dur = info["dur"]
    layout = "facecam" if cam else "flou"
    gy = game_y(layout)
    inputs = [["-i", str(src)]]
    fg = [f"[0:v]split=4[a][b][c][d]",
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=26:2,"
          f"eq=brightness=-0.18:saturation=0.75[bg]"]
    # Le jeu, zoomé aux moments forts (seulement le jeu, pas l'habillage)
    GH = game_h(layout)
    game = f"[b]scale={W}:{GH}:force_original_aspect_ratio=increase,crop={W}:{GH},setsar=1,fps={FPS}"
    if peaks:
        bumps = f"max(0,1-abs(it-{peaks[0]})/0.5)"
        game += (f",zoompan=z='1+0.06*{bumps}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":s={W}x{GH}:fps={FPS}")
    if censor:  # nudité : jeu fortement flouté sur ces passages
        game += f",boxblur=60:6:enable='{_enable(censor)}'"
    fg.append(game + "[game]")
    fg.append(f"[bg][game]overlay=0:{gy}[s1]")
    last = "s1"
    if False and censor and cam:  # (désactivé : la réaction est déjà en grand dans le bandeau facecam)
        x, y, cw, ch = cam
        zw = min(int(ch * W / GH) // 2 * 2, info["w"])
        zx = min(max(x + cw // 2 - zw // 2, 0), info["w"] - zw)
        fg.append(f"[d]crop={zw}:{ch}:{zx}:{y},scale={W}:{GH}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{GH},setsar=1[face]")
        fg.append(f"[{last}][face]overlay=0:{gy}:enable='{_enable(censor)}'[s1b]")
        last = "s1b"
    else:
        fg.append("[d]nullsink")
    if cam:
        x, y, cw, ch = cam
        camf = (f"[c]crop={cw}:{ch}:{x}:{y},scale={W}:{CAM_H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{CAM_H},setsar=1,fps={FPS}")
        if peaks:  # au moment fort, on zoome sur la tête du streamer
            cb = f"max(0,1-abs(it-{peaks[0]})/1.0)"
            camf += (f",zoompan=z='1+0.30*min(1,1.5*{cb})':d=1:x='iw/2-(iw/zoom/2)':y='ih*0.42-(ih/zoom/2)'"
                     f":s={W}x{CAM_H}:fps={FPS}")
        fg.append(camf + "[cam]")
        fg.append(f"[{last}][cam]overlay=0:{CAM_Y}[s2]")
        last = "s2"
    else:
        fg.append("[c]nullsink")

    r_audio, r_at, r_dur = False, (sfx_at or 0) + 0.25, 0
    if reaction and Path(reaction).exists():
        rp = Path(reaction)
        if rp.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            r_dur = 1.6
            inputs.append(["-loop", "1", "-t", str(r_dur), "-i", str(rp)])
        else:
            rinfo = probe(rp)
            r_dur = min(rinfo["dur"], 2.5)
            r_audio = rinfo["audio"]
            inputs.append(["-t", str(r_dur), "-i", str(rp)])
        r_at = min(r_at, max(dur - r_dur, 0))
        ri = len(inputs) - 1
        fg.append(f"[{ri}:v]scale=380:-2,pad=iw+12:ih+12:6:6:white,setpts=PTS-STARTPTS+{r_at}/TB[rx]")
        fg.append(f"[{last}][rx]overlay=W-w-24:{gy + GH}-h-24:enable='between(t,{r_at},{r_at + r_dur})'"
                  f":eof_action=pass[s3]")
        last = "s3"
    logo = C.ASSETS / "brand" / "logo_bug.png"
    if logo.exists():
        inputs.append(["-i", str(logo)])
        fg.append(f"[{last}][{len(inputs) - 1}:v]overlay={LOGO_POS[0]}:{LOGO_POS[1]}[s4]")
        last = "s4"
    fg.append(f"[{last}]ass='{_esc(ass_path)}':fontsdir='{_esc(C.FONT.parent)}'[v]")

    # Audio : stream + bruitage + son de la réaction
    mix = []
    if sfx and sfx.exists() and sfx_at is not None:
        inputs.append(["-i", str(sfx)])
        ms = int(sfx_at * 1000)
        fg.append(f"[{len(inputs) - 1}:a]adelay={ms}|{ms},volume=0.9[sx]")
        mix.append("[sx]")
    if r_audio:
        ms = int(r_at * 1000)
        fg.append(f"[{ri}:a]aresample=44100,adelay={ms}|{ms}[ra]")
        mix.append("[ra]")
    if info["audio"]:
        vol = f"volume='if(between(t,{r_at},{r_at + r_dur}),0.35,1)':eval=frame" if r_audio else "anull"
        fg.append(f"[0:a]{vol}[main]")
    else:
        inputs.append(["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=44100:cl=stereo"])
        fg.append(f"[{len(inputs) - 1}:a]anull[main]")
    fg.append(f"[main]{''.join(mix)}amix=inputs={1 + len(mix)}:normalize=0:duration=first,"
              f"alimiter=limit=0.95[aout]")

    cmd = ["ffmpeg", "-y", "-v", "error"] + [a for i in inputs for a in i]
    cmd += ["-filter_complex", ";".join(fg), "-map", "[v]", "-map", "[aout]",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", "-t", f"{dur:.2f}"]
    if target_mb:
        kbps = int(min(7000, max(900, target_mb * 8192 * 0.88 / dur - 128)))
        cmd += ["-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.25)}k", "-bufsize", f"{kbps * 2}k"]
    else:
        cmd += ["-crf", "21"]
    run(cmd + [str(out)])
    if target_mb and out.stat().st_size > target_mb * 1024 * 1024:  # trop lourd : on recompresse
        return encode(src, out, info, cam, peaks, ass_path, sfx, sfx_at, target_mb * 0.8, reaction)
    return out


def render_short(clip: dict, work: Path, target_mb=None, rank=None, src: Path = None, out_lang=None,
                 brief=None, strict=False, force_censor=False) -> dict:
    """strict=True (montages automatiques, flashs, compils) : on écarte les clips hors jeu, douteux ou sans intérêt."""
    """Monte un clip. out_lang = langue de la chaîne cible (sous-titres traduits si elle diffère du clip)."""
    import texts
    lang = clip["lang"]
    out_lang = out_lang or lang
    work.mkdir(parents=True, exist_ok=True)
    src = src or download(clip["url"], work / f"{clip['id']}_src.mp4")
    info = probe(src)
    if info["dur"] > C.SHORT_MAX_SECONDS + 5 and not brief:  # clip long : on garde le meilleur passage
        src = trim_best(src, work / "best.mp4", C.SHORT_MAX_SECONDS)
        info = probe(src)
    if force_censor:  # 🔞 : tu as signalé de la nudité → détection plus sensible, et jamais d'écart automatique
        nude, nude_ratio = nsfw_timeline(src, work, threshold=0.25)
        cam_early = detect_facecam(src, info)
    else:
        nude, nude_ratio = nsfw_timeline(src, work)
        cam_early = detect_facecam(src, info) if nude else None
        if nude and (nude_ratio > 0.5 or (not cam_early and nude_ratio > 0.35)):
            raise UnsafeClip(f"nudité sur {int(nude_ratio * 100)} % du clip")
    tr = transcribe(src, lang) if info["audio"] else {"words": [], "segments": []}
    transcript = " ".join(w[2] for w in tr["words"])
    words = tr["words"]
    translated = False
    if out_lang != lang and tr["segments"]:
        segs = texts.translate_segments(tr["segments"], lang, out_lang)
        if not segs and out_lang == "en":
            segs = whisper_to_english(src, lang)
        if segs:
            words = words_from_segments(segs)
            translated = True
        else:
            print(f"⚠️ Pas de traduction {lang}→{out_lang} : sous-titres d'origine conservés")
    category = categorize(clip["title"], transcript)
    seed = clip["id"] + out_lang + str(clip.get("reroll", 0))
    peaks = audio_peaks(src, info["dur"]) if info["audio"] else []
    frames = sample_frames(src, work, info["dur"], peak=peaks[0] if peaks else None) if C.ANTHROPIC_API_KEY else []
    txt = texts.describe(clip, category, transcript, seed=seed, lang=out_lang, frames=frames)
    a = txt.get("analysis")
    if a and a.get("categorie"):
        category = a["categorie"]
    # Nudité vue par l'IA mais pas par NudeNet : on floute seulement autour des images concernées (le reste garde
    # tout son contexte). Tout le clip seulement en dernier recours, si tu as demandé 🔞 et que rien n'est localisé.
    if not nude and ((a and a.get("nudite")) or force_censor):
        times = [frames[i - 1][1] for i in (a or {}).get("nudite_images", []) if 1 <= i <= len(frames)]
        for t in sorted(times):
            s0, s1 = max(t - 2.5, 0), min(t + 2.5, info["dur"])
            if nude and s0 <= nude[-1][1]:
                nude[-1] = (nude[-1][0], s1)
            else:
                nude.append((round(s0, 2), round(s1, 2)))
        if not nude and force_censor:
            nude = [(0.0, round(info["dur"], 2))]
        if nude:
            cam_early = cam_early or detect_facecam(src, info)
            if not cam_early and (strict or force_censor):
                raise UnsafeClip(f"nudité repérée, pas de facecam pour la version censurée ({(a or {}).get('raison', '')})")
    if a and strict:
        if not a["gameplay"]:
            raise UnsafeClip(f"pas du gameplay GTA ({a['raison']})")
        if not a["safe"] and not a.get("nudite"):
            raise UnsafeClip(f"contenu à risque ({a['raison']})")
        if a["score"] < C.AUTO_MIN_SCORE:
            raise UnsafeClip(f"pas assez drôle/intéressant : {a['score']}/10 ({a['raison']})")
    cam = cam_early if nude else detect_facecam(src, info)
    layout = "facecam" if cam else "flou"
    meme = pick_meme(out_lang, category, seed)
    peak = peaks[0] if peaks else (info["dur"] * 0.6 if info["dur"] > 4 else None)
    ass_path = work / f"{clip['id']}_{out_lang}.ass"
    build_ass(ass_path, words, info["dur"], txt, meme["stamp"] if C.STAMPS else None, peak, clip["streamer"], out_lang, seed,
              layout, rank=rank, brief=brief, censored=nude)
    sfx = None
    if meme["sfx"]:
        for ext in (".wav", ".mp3"):
            p = C.ASSETS / "sfx" / f"{meme['sfx']}{ext}"
            if p.exists():
                sfx = p
                break
    out = work / f"{clip['id']}_{out_lang}{'_r' + str(rank) if rank else ''}.mp4"
    encode(src, out, info, cam, peaks, ass_path, sfx, peak, target_mb, meme["reaction"], censor=nude)
    return {"path": out, "category": category, "transcript": transcript, "meme": meme, "texts": txt,
            "layout": layout, "duration": info["dur"], "source": src, "lang": out_lang,
            "translated": translated, "censored": nude, "analysis": a}


def render_intro(title: str, lang: str, work: Path, seconds: float = 2.4) -> Path:
    """Générique « édition spéciale » pour ouvrir les compilations."""
    ass = work / "intro.ass"
    blk = _col("black", "0E0E0E")
    edition = {"fr": "ÉDITION SPÉCIALE", "es": "EDICIÓN ESPECIAL"}.get(lang, "SPECIAL REPORT")
    ev = [
        f"Dialogue: 2,0:00:00.30,{ts(seconds)},Kicker,,0,0,0,,{{\\an8\\pos(540,900)}}{edition}",
        f"Dialogue: 2,0:00:00.45,{ts(seconds)},Head,,0,0,0,,{{\\an8\\pos(540,1010)\\fscx70\\fscy70"
        f"\\t(0,150,\\fscx100\\fscy100)}}{ass_text(title)}",
        f"Dialogue: 2,0:00:00.00,{ts(seconds)},Band,,0,0,0,,{{\\pos(0,1260)\\p1}}m 0 0 l {W} 0 l {W} 14 l 0 14{{\\p0}}",
    ]
    ass.write_text(ass_header() + "\n".join(ev) + "\n", encoding="utf-8")
    out = work / "intro.mp4"
    logo = C.ASSETS / "brand" / "logo_big.png"
    whoosh = C.ASSETS / "sfx" / "whoosh.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x{blk}:s={W}x{H}:r={FPS}:d={seconds}",
         "-i", str(logo), "-i", str(whoosh), "-filter_complex",
         f"[1:v]format=rgba[lg];[0:v][lg]overlay=(W-w)/2:560:enable='gte(t,0.1)'[bgv];"
         f"[bgv]ass='{_esc(ass)}':fontsdir='{_esc(C.FONT.parent)}'[v];"
         f"[2:a]apad,atrim=0:{seconds},aresample=44100,aformat=channel_layouts=stereo[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-t", str(seconds), str(out)])
    return out


def render_compilation(clips: list, title: str, work: Path, out_lang: str = None, strict=False) -> Path:
    """Top N en compte à rebours : #N ... #1 (le plus vu en dernier)."""
    work.mkdir(parents=True, exist_ok=True)
    ordered = sorted(clips, key=lambda c: c.get("views", 0))
    lang = out_lang or (ordered[0]["lang"] if ordered else "fr")
    parts = [render_intro(title, lang, work)]
    n = len(ordered)
    for i, clip in enumerate(ordered):
        try:
            r = render_short(clip, work / clip["id"], target_mb=None, rank=n - i, out_lang=lang, strict=strict,
                             force_censor=bool(clip.get("censure")))
            parts.append(r["path"])
        except Exception as e:
            print(f"⚠️ Clip ignoré ({clip['url']}) : {e}")
    out = work / f"compilation_{re.sub(r'[^a-z0-9]+', '_', title.lower())[:40]}.mp4"
    return concat(with_zaps(parts, work), out)


def trim_best(src: Path, out: Path, seconds: float = 9.0) -> Path:
    """Garde le meilleur moment du clip (autour du pic audio) pour les brèves."""
    info = probe(src)
    if info["dur"] <= seconds + 1:
        return src
    peaks = audio_peaks(src, info["dur"]) if info["audio"] else []
    p = peaks[0] if peaks else info["dur"] * 0.6
    start = min(max(p - seconds * 0.55, 0), info["dur"] - seconds)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(src), "-t", str(seconds),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(out)])
    return out


def concat(parts: list, out: Path, target_mb=None) -> Path:
    """Assemble plusieurs vidéos ; si target_mb, compresse pour tenir dans Discord."""
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{Path(p).resolve()}'\n" for p in parts), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart"]
    if target_mb:
        dur = sum(probe(Path(p))["dur"] for p in parts)
        kbps = int(min(6000, max(700, target_mb * 8192 * 0.88 / dur - 128)))
        cmd += ["-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.25)}k", "-bufsize", f"{kbps * 2}k"]
    else:
        cmd += ["-crf", "22"]
    run(cmd + [str(out)])
    if target_mb and out.stat().st_size > target_mb * 1024 * 1024:
        return concat(parts, out, target_mb * 0.8)
    return out


def render_zap(work: Path, channel: int, seconds: float = 0.5) -> Path:
    """Transition « zapping » : neige télé + numéro de chaîne + bruit de zap."""
    work.mkdir(parents=True, exist_ok=True)
    ass = work / f"zap{channel}.ass"
    ass.write_text(ass_header() + f"Dialogue: 1,0:00:00.00,{ts(seconds)},Kicker,,0,0,0,,"
                   f"{{\\an9\\pos({W - 40},60)\\3c&H000000&\\1c&H6CFF39&}}CH {channel:02d}\n", encoding="utf-8")
    out = work / f"zap{channel}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=gray:s={W // 4}x{H // 4}:r={FPS}:d={seconds}",
         "-i", str(C.ASSETS / "sfx" / "zap.wav"), "-filter_complex",
         f"[0:v]noise=alls=100:allf=t+u,hue=s=0,scale={W}:{H}:flags=neighbor,eq=contrast=1.6,"
         f"fade=t=in:st=0:d=0.08:color=white,ass='{_esc(ass)}':fontsdir='{_esc(C.FONT.parent)}'[v];"
         f"[1:a]apad,atrim=0:{seconds},aresample=44100,aformat=channel_layouts=stereo[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-t", str(seconds), str(out)])
    return out


def with_zaps(parts: list, work: Path) -> list:
    """Intercale une transition zapping entre chaque séquence."""
    out = []
    for i, p in enumerate(parts):
        if i > 0:
            out.append(render_zap(work, i + 1))
        out.append(p)
    return out


def render_flash(clips: list, title: str, work: Path, lang: str, target_mb=None) -> Path:
    """Flash info : générique + 3 à 5 brèves courtes (le meilleur moment de chaque clip)."""
    work.mkdir(parents=True, exist_ok=True)
    parts = [render_intro(title, lang, work)]
    n = len(clips)
    for i, clip in enumerate(clips, 1):
        try:
            w = work / clip["id"]
            w.mkdir(parents=True, exist_ok=True)
            full = download(clip["url"], w / "full.mp4")
            short = trim_best(full, w / "best.mp4", C.FLASH_SECONDS)
            r = render_short(clip, w, target_mb=None, src=short, out_lang=lang, brief=(i, n), strict=True,
                             force_censor=bool(clip.get("censure")))
            parts.append(r["path"])
        except Exception as e:
            print(f"⚠️ Brève ignorée ({clip['url']}) : {e}")
    return concat(with_zaps(parts, work), work / "flash.mp4", target_mb)
