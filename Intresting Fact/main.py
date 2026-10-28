#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interesting Fact Video Automation  (ENGLISH ONLY)
-------------------------------------------------
Folder (sab kuch "Intresting Fact" ke andar):
  Topics/<topic>/fact.txt + link.txt   <- random 3 topics, har topic se 1 fact + 1 random image
  hook.txt      <- 1 line = 1 hook (random, shocking voice)
  title.txt     <- 1 line = 1 title
  hashtag.txt   <- 1 line = 1 hashtag set
  track.json    <- facts/titles/hashtags 100-day cooldown
  config.json   <- names, message, voice settings
  music/  output/  fonts/

Features:
  * English human neural voice (edge-tts), energetic tone
  * hook.txt se random hook -> shocking voice -> impact sound -> phir 3 facts
  * "hmm / aww / oh / wow ..." par natural pause, "..." par pause, [pause] / [pause 1.5] tag
  * 10 templates (transition + filter + zoom + caption style)
  * Music: lamba -> trim, chhota -> crossfade merge
  * Upload fallback chain -> GitHub raw link
  * Webhook: WEBHOOK_INTRESTING_FACT
  * output/ me video, 3 din baad auto delete
"""
import asyncio
import glob
import hashlib
import io
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
TOPICS_DIR = BASE / "Topics"
OUTPUT_DIR = BASE / "output"
TMP_DIR = BASE / "_tmp"
TRACK_FILE = BASE / "track.json"
CONFIG_FILE = BASE / "config.json"
MUSIC_DIR = BASE / "music"
FONT_DIR = BASE / "fonts"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
W, H, FPS = 1080, 1920, 30
BG_W, BG_H = 1800, 3200          # zoompan ke liye bada source (smooth zoom)

DEFAULT_CONFIG = {
    "automation_name": "Interesting Fact Automation",
    "social_media_name": "YouTube Shorts, Instagram Reels, Facebook Reels",
    "success_message": "Video successfully created and sent for posting!",
    "cooldown_days": 100,
    "output_keep_days": 3,
    "facts_per_video": 3,
    "voice": "auto",                 # "auto" (random) ya fixed e.g. "en-US-GuyNeural"
    "voices": [],                    # optional: apni voice list, [] = built-in list
    "voice_rate": "+12%",
    "voice_pitch": "+4Hz",
    "voice_volume": "+30%",
    "hook_rate": "+18%",             # shocking hook tone
    "hook_pitch": "+12Hz",
    "hook_volume": "+50%",
    "interj_rate": "-4%",            # hmm / aww / oh / wow ...
    "interj_pitch": "+10Hz",
    "interj_volume": "+40%",
    "interjection_pause": 0.45,
    "ellipsis_pause": 0.6,
    "hook_gap": 0.55,                # hook ke baad fact start hone se pehle ruk
    "hook_sfx": True,
    "music_volume": 0.14,
    "transition_duration": 0.5,
}

ENGLISH_VOICES = [
    "en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-AndrewNeural",
    "en-US-BrianNeural", "en-US-EricNeural", "en-US-AriaNeural", "en-US-JennyNeural",
    "en-GB-RyanNeural", "en-IN-PrabhatNeural",
]

DEFAULT_HOOKS = [
    "Stop scrolling! These three facts will blow your mind!",
    "Wait... you will not believe the third fact!",
    "Oh! Your brain is about to get an upgrade!",
    "Only one percent of people know these three facts. Are you one of them?",
]
ORDINALS = ["Fact number one.", "Fact number two.", "Fact number three.",
            "Fact number four.", "Fact number five."]
CTA = "Follow for more amazing facts!"
LABEL_HOOK = "WATCH TILL THE END"
LABEL_FACT = "FACT {i} / {n}"

# in words par pause aata hai ("hmm", "aww", "oh" ...)
INTERJECTIONS = {
    "hmm", "hm", "mmm", "mm", "aww", "aw", "oh", "ohh", "ooh", "wow", "whoa", "woah",
    "ah", "ahh", "aha", "uh", "um", "oops", "yikes", "huh", "gosh", "boom", "yay", "hmmm",
}
PUNCT = string.punctuation + "\u2026\u2014\u2013\u201c\u201d\u2018\u2019"
PAUSE_TAG = re.compile(r"\[pause(?:\s+(\d+(?:\.\d+)?))?\]", re.I)

# --------------------------------------------------------------------------
# 10 TEMPLATES  (transition + color grade + zoom + caption colors)
# --------------------------------------------------------------------------
TEMPLATES = [
    dict(name="neon_glow",
         transitions=["slideleft", "circleopen", "smoothleft", "zoomin"],
         zooms=["in", "pan_l", "out", "pan_r"],
         grade="eq=contrast=1.12:saturation=1.45:brightness=0.02,"
               "colorbalance=bs=0.12:rs=-0.05:bh=0.10:rh=0.06,vignette=angle=PI/5",
         grain=6, accent="#FF2BD6", hi="#00F5FF", stroke="#08001A", bar="#00F5FF", pos=0.66),
    dict(name="cinematic_gold",
         transitions=["fadeblack", "dissolve", "smoothup", "circleclose"],
         zooms=["in", "up", "out", "down"],
         grade="eq=contrast=1.10:saturation=1.15:gamma=0.95,"
               "colorbalance=rs=0.08:gs=0.03:bs=-0.10:rh=0.10:bh=-0.08,vignette=angle=PI/4",
         grain=10, accent="#FF8800", hi="#FFC400", stroke="#1A0F00", bar="#FFC400", pos=0.68),
    dict(name="glitch_tech",
         transitions=["pixelize", "hlslice", "vuslice", "radial"],
         zooms=["pan_r", "in", "pan_l", "out"],
         grade="eq=contrast=1.20:saturation=0.9,colorbalance=gs=0.10:gm=0.06,"
               "rgbashift=rh=-7:bh=7:enable='lt(mod(t,2.4),0.14)'",
         grain=8, accent="#00C27A", hi="#39FF14", stroke="#001A0A", bar="#39FF14", pos=0.64),
    dict(name="hot_energy",
         transitions=["wipeleft", "diagtl", "zoomin", "slideright"],
         zooms=["in", "diag", "in", "pan_l"],
         grade="eq=contrast=1.20:saturation=1.60,colorbalance=rs=0.10:bs=-0.08:rh=0.08,"
               "vignette=angle=PI/5",
         grain=4, accent="#FF2D2D", hi="#FFE600", stroke="#200000", bar="#FF2D2D", pos=0.66),
    dict(name="cool_space",
         transitions=["circleopen", "smoothup", "fadegrays", "horzopen"],
         zooms=["out", "in", "down", "pan_r"],
         grade="eq=contrast=1.10:saturation=1.20:brightness=-0.02,"
               "colorbalance=bs=0.14:bm=0.08:rs=-0.06,vignette=angle=PI/4.5",
         grain=6, accent="#7A5CFF", hi="#5CC8FF", stroke="#000A1F", bar="#5CC8FF", pos=0.67),
    dict(name="sunset_vibes",
         transitions=["slideup", "wipeup", "dissolve", "rectcrop"],
         zooms=["pan_l", "in", "up", "out"],
         grade="eq=contrast=1.08:saturation=1.35,colorbalance=rm=0.10:gm=0.02:bm=-0.12:rh=0.08,"
               "vignette=angle=PI/5",
         grain=5, accent="#FF5E5B", hi="#FFB02E", stroke="#240800", bar="#FFB02E", pos=0.65),
    dict(name="noir_pop",
         transitions=["fadeblack", "hblur", "squeezeh", "vertclose"],
         zooms=["in", "out", "diag", "pan_r"],
         grade="hue=s=0.12,eq=contrast=1.30:brightness=-0.02,vignette=angle=PI/3.5",
         grain=9, accent="#FFFFFF", hi="#FFE600", stroke="#000000", bar="#FFE600", pos=0.68),
    dict(name="retro_vhs",
         transitions=["hlwind", "hrwind", "vuwind", "vdwind"],
         zooms=["pan_l", "pan_r", "in", "out"],
         grade="curves=preset=cross_process,eq=saturation=1.2,rgbashift=rh=4:bh=-4,"
               "vignette=angle=PI/4",
         grain=9, accent="#EE4266", hi="#FFD23F", stroke="#1A0010", bar="#FFD23F", pos=0.66),
    dict(name="mint_fresh",
         transitions=["circleclose", "vertopen", "smoothright", "diagbr"],
         zooms=["out", "up", "in", "pan_l"],
         grade="eq=contrast=1.05:saturation=1.30:brightness=0.04,"
               "colorbalance=gs=0.08:bs=0.04:rs=-0.05",
         grain=3, accent="#00B3FF", hi="#00FFC6", stroke="#00141F", bar="#00FFC6", pos=0.66),
    dict(name="royal_purple",
         transitions=["slidedown", "wipedown", "diagtr", "fadeblack"],
         zooms=["diag", "in", "down", "out"],
         grade="eq=contrast=1.12:saturation=1.30,colorbalance=rs=0.08:bs=0.14:gs=-0.06:bh=0.08,"
               "vignette=angle=PI/4.5",
         grain=6, accent="#8E2DE2", hi="#D6A8FF", stroke="#10001F", bar="#D6A8FF", pos=0.67),
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def log(*a):
    print(*a, flush=True)


def now_utc():
    return datetime.now(timezone.utc)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text("utf-8")))
        except Exception as e:
            log("config.json read error:", e)
    if os.getenv("COOLDOWN_DAYS"):
        cfg["cooldown_days"] = int(os.getenv("COOLDOWN_DAYS"))
    return cfg


def read_lines(path, skip_comments=True):
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8-sig").splitlines():
        line = line.strip()
        if not line or (skip_comments and line.startswith("//")):
            continue
        out.append(line)
    return out


def uid(text):
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def hex2rgb(h, a=None):
    h = h.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return rgb + ((a,) if a is not None else ())


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        log("COMMAND FAILED:", " ".join(map(str, cmd))[:600])
        log(p.stderr[-2500:])
        raise RuntimeError("ffmpeg/ffprobe failed")
    return p.stdout


def media_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


# --------------------------------------------------------------------------
# track.json  (facts / titles / hashtags  ->  cooldown)
# --------------------------------------------------------------------------
def load_track():
    data = {}
    if TRACK_FILE.exists():
        try:
            data = json.loads(TRACK_FILE.read_text("utf-8"))
        except Exception:
            log("track.json corrupt -> fresh start")
    for k in ("facts", "titles", "hashtags"):
        data.setdefault(k, {})
    data.setdefault("meta", {})
    return data


def save_track(track):
    tmp = TRACK_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(track, indent=2, ensure_ascii=False), "utf-8")
    tmp.replace(TRACK_FILE)


def in_cooldown(entry, days):
    if not entry:
        return False
    try:
        last = datetime.fromisoformat(entry["last_used"])
    except Exception:
        return False
    return now_utc() - last < timedelta(days=days)


def mark_used(bucket, text, **extra):
    k = uid(text)
    e = bucket.get(k, {"count": 0})
    e.update(extra)
    e["text"] = text
    e["count"] = e.get("count", 0) + 1
    e["last_used"] = now_utc().isoformat()      # cooldown yahin se dobara 100 din
    bucket[k] = e


def pick_unique(lines, bucket, days, default):
    if not lines:
        return default
    avail = [l for l in lines if not in_cooldown(bucket.get(uid(l)), days)]
    if avail:
        return random.choice(avail)
    log("WARNING: saare title/hashtag cooldown me hain -> sabse purana use ho raha hai")
    return min(lines, key=lambda l: bucket.get(uid(l), {}).get("last_used", ""))


# --------------------------------------------------------------------------
# topics / facts / hook / images
# --------------------------------------------------------------------------
def discover_topics():
    """Intresting Fact/Topics/<topic>/fact.txt + link.txt"""
    if not TOPICS_DIR.exists():
        raise SystemExit(f"'Topics' folder nahi mila: {TOPICS_DIR}")
    return [d for d in sorted(TOPICS_DIR.iterdir())
            if d.is_dir() and (d / "fact.txt").exists() and (d / "link.txt").exists()]


def pick_facts(topics, track, n, days):
    random.shuffle(topics)                      # random topic folder
    chosen = []
    for t in topics:                            # ek folder se sirf ek fact
        avail = [f for f in read_lines(t / "fact.txt")
                 if not in_cooldown(track["facts"].get(uid(f)), days)]
        if avail:
            chosen.append({"topic": t.name.replace("_", " ").replace("-", " "),
                           "dir": t, "text": random.choice(avail)})
        else:
            log(f"[skip] {t.name}: sab facts cooldown me hain")
        if len(chosen) == n:
            break
    if len(chosen) < n:
        raise SystemExit(f"Sirf {len(chosen)} topic available hain, {n} chahiye. "
                         "Naye facts/topic folders add karo.")
    return chosen


def pick_hook(track):
    hooks = read_lines(BASE / "hook.txt") or DEFAULT_HOOKS
    last = track["meta"].get("last_hook")
    pool = [h for h in hooks if h != last] or hooks
    return random.choice(pool)


def cover_and_blur(img):
    """Landscape image -> blurred bg + centered foreground, warna cover-crop."""
    def cover(im, w, h):
        r = max(w / im.width, h / im.height)
        nw, nh = int(im.width * r) + 1, int(im.height * r) + 1
        im = im.resize((nw, nh), Image.LANCZOS)
        l, t = (nw - w) // 2, (nh - h) // 2
        return im.crop((l, t, l + w, t + h))

    if img.width / img.height > 0.9:
        bg = cover(img, BG_W // 4, BG_H // 4).filter(ImageFilter.GaussianBlur(10))
        bg = bg.resize((BG_W, BG_H), Image.BICUBIC)
        bg = Image.eval(bg, lambda v: int(v * 0.55))
        r = BG_W / img.width
        fg = img.resize((BG_W, int(img.height * r)), Image.LANCZOS)
        bg.paste(fg, (0, (BG_H - fg.height) // 2))
        return bg
    return cover(img, BG_W, BG_H)


def download_image(links, dest, used):
    cand = [u for u in links if u not in used] or list(links)
    random.shuffle(cand)
    for url in cand:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": UA})
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if min(img.size) < 300:
                raise ValueError("image too small")
            cover_and_blur(img).save(dest, "JPEG", quality=92)
            used.add(url)
            return url
        except Exception as e:
            log(f"  image fail ({url[:60]}): {e}")
    raise RuntimeError("Koi bhi image download nahi hui")


# --------------------------------------------------------------------------
# voice over  (English voice + pauses + shocking hook)
# --------------------------------------------------------------------------
def pick_voice(cfg):
    forced = os.getenv("VOICE_NAME") or cfg["voice"]
    if forced and forced != "auto":
        return forced
    return random.choice(cfg["voices"] or ENGLISH_VOICES)


def split_with_pauses(text, cfg):
    """Text ko chunks me todta hai: har chunk ke baad pause.
    Pause aata hai: interjection (hmm/aww/oh/wow..), '...', [pause], [pause 1.5]"""
    text = PAUSE_TAG.sub(lambda m: f" \u27e6{m.group(1) or '0.7'}\u27e7 ", text)
    chunks, buf = [], []

    def flush(pause=0.0, interj=False):
        if buf:
            chunks.append({"text": " ".join(buf), "pause": pause, "interj": interj})
            buf.clear()
        elif pause and chunks:
            chunks[-1]["pause"] += pause

    for tok in text.split():
        m = re.fullmatch(r"\u27e6([\d.]+)\u27e7", tok)
        if m:
            flush(float(m.group(1)))
            continue
        core = tok.strip(PUNCT).lower()
        core = re.sub(r"(.)\1{2,}", r"\1\1", core)          # hmmmm -> hmm
        ell = tok.endswith(("...", "\u2026"))
        if core in INTERJECTIONS:
            flush(0.12)
            buf.append(tok)
            flush(max(cfg["interjection_pause"], cfg["ellipsis_pause"] if ell else 0), True)
            continue
        buf.append(tok)
        if ell:
            flush(cfg["ellipsis_pause"])
    flush(0)
    return chunks


def prosody_for(kind, interj, cfg):
    if interj:
        return cfg["interj_rate"], cfg["interj_pitch"], cfg["interj_volume"]
    if kind == "hook":
        return cfg["hook_rate"], cfg["hook_pitch"], cfg["hook_volume"]
    return cfg["voice_rate"], cfg["voice_pitch"], cfg["voice_volume"]


async def _edge(text, voice, out, pros):
    import edge_tts
    rate, pitch, vol = pros
    kw = dict(rate=rate, pitch=pitch, volume=vol)
    try:
        comm = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kw)
    except TypeError:
        comm = edge_tts.Communicate(text, voice, **kw)
    bounds = []
    with open(out, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                bounds.append((ch["text"], s, s + ch["duration"] / 1e7))
    return bounds


def synth_chunk(text, voice, out, pros):
    err = None
    for _ in range(3):
        try:
            b = asyncio.run(_edge(text, voice, out, pros))
            if Path(out).stat().st_size > 800:
                return b
        except Exception as e:
            err = e
            time.sleep(2)
    log("edge-tts fail:", err, "-> gTTS fallback")
    from gtts import gTTS
    gTTS(text, lang="en").save(str(out))
    return []


def token_times(text, bounds, dur):
    words = text.split()
    if not words:
        return []
    if bounds and len(bounds) == len(words):
        return [(w, s, e) for w, (_, s, e) in zip(words, bounds)]
    tot = sum(len(w) + 1 for w in words)
    t, out = 0.0, []
    for w in words:
        d = dur * (len(w) + 1) / tot
        out.append((w, t, t + d))
        t += d
    return out


def make_silence(path, dur):
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "anullsrc=r=24000:cl=mono", "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(path)])


def build_voice(text, voice, kind, out_wav, cfg):
    """Text -> voice wav (pauses ke saath) + caption word timings."""
    chunks = split_with_pauses(text, cfg)
    pieces, tokens, t = [], [], 0.0
    stem = out_wav.stem
    for k, c in enumerate(chunks):
        mp3 = TMP_DIR / f"{stem}_c{k}.mp3"
        wav = TMP_DIR / f"{stem}_c{k}.wav"
        bounds = synth_chunk(c["text"], voice, mp3, prosody_for(kind, c["interj"], cfg))
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1",
             "-c:a", "pcm_s16le", str(wav)])
        d = media_duration(wav)
        for w, s, e in token_times(c["text"], bounds, d):
            tokens.append((w, s + t, e + t))
        pieces.append(wav)
        t += d
        if c["pause"] > 0.01:
            sil = TMP_DIR / f"{stem}_s{k}.wav"
            make_silence(sil, c["pause"])
            pieces.append(sil)
            t += c["pause"]
    lst = TMP_DIR / f"{stem}_concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in pieces), "utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(out_wav)])
    return tokens, media_duration(out_wav)


def make_impact_sfx(path):
    """Hook ke start par 'boom' impact sound."""
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "aevalsrc=exprs='0.9*sin(2*PI*(70-45*t)*t)*exp(-5*t)':s=44100:d=0.8",
         "-c:a", "pcm_s16le", str(path)])


# --------------------------------------------------------------------------
# captions (PIL) - word highlight karaoke style
# --------------------------------------------------------------------------
_font_cache = {}


def get_font(size):
    if size in _font_cache:
        return _font_cache[size]
    paths = []
    if FONT_DIR.exists():
        paths += [str(p) for p in sorted(FONT_DIR.glob("*.ttf"))]
    for pat in ("NotoSans-ExtraBold.ttf", "NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        paths += glob.glob(f"/usr/share/fonts/**/{pat}", recursive=True)
    try:
        fm = subprocess.run(["fc-match", "-f", "%{file}", "sans:bold"],
                            capture_output=True, text=True, timeout=10).stdout.strip()
        if fm:
            paths.append(fm)
    except Exception:
        pass
    for p in paths:
        try:
            f = ImageFont.truetype(p, size)
            _font_cache[size] = f
            return f
        except Exception:
            continue
    f = ImageFont.load_default(size)
    _font_cache[size] = f
    return f


def make_label_layer(label, topic, tpl):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gh = int(H * 0.5)
    for i in range(gh):                                  # bottom dark gradient
        a = int(175 * (i / gh) ** 1.6)
        d.line([(0, H - gh + i), (W, H - gh + i)], fill=(0, 0, 0, a))
    f = get_font(62)
    tw = d.textlength(label, font=f)
    pw, ph = int(tw + 100), 104
    x0, y0 = (W - pw) // 2, 250
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=52, fill=hex2rgb(tpl["accent"], 235))
    d.text((W / 2, y0 + ph / 2), label, font=f, fill="#FFFFFF", anchor="mm",
           stroke_width=3, stroke_fill=hex2rgb(tpl["stroke"]))
    if topic:
        d.text((W / 2, y0 + ph + 28), topic.upper(), font=get_font(50), fill="#FFFFFF",
               anchor="mt", stroke_width=5, stroke_fill=hex2rgb(tpl["stroke"]))
    return layer


def draw_caption(layer, words, active, tpl):
    img = layer.copy()
    if not words:
        return img
    d = ImageDraw.Draw(img)
    size = 104
    font = get_font(size)
    gap = int(size * 0.28)
    max_w = W - 150
    lines, cur, cw = [], [], 0
    for gi, w in words:
        wl = d.textlength(w, font=font)
        add = wl if not cur else wl + gap
        if cur and cw + add > max_w:
            lines.append(cur)
            cur, cw = [(gi, w, wl)], wl
        else:
            cur.append((gi, w, wl))
            cw += add
    lines.append(cur)
    lh = int(size * 1.3)
    y0 = int(H * tpl["pos"]) - lh * len(lines) // 2
    sw = max(8, size // 9)
    for li, line in enumerate(lines):
        lw = sum(x[2] for x in line) + gap * (len(line) - 1)
        x = (W - lw) / 2
        for gi, w, wl in line:
            col = tpl["hi"] if gi == active else "#FFFFFF"
            d.text((x, y0 + li * lh), w, font=font, fill=col,
                   stroke_width=sw, stroke_fill=hex2rgb(tpl["stroke"]))
            x += wl + gap
    return img


def make_chunks(tokens, max_words=3):
    chunks, cur = [], []
    for i, (w, _, _) in enumerate(tokens):
        cur.append(i)
        if len(cur) >= max_words or w[-1:] in ".!?":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_caption_list(seg_dir, tokens, lead, L, label_layer, tpl):
    seg_dir.mkdir(parents=True, exist_ok=True)
    disp = [(w.upper(), s + lead, e + lead) for w, s, e in tokens]
    empty = seg_dir / "empty.png"
    label_layer.save(empty)
    events = []
    for chunk in make_chunks(tokens):
        for pos, idx in enumerate(chunk):
            start = disp[idx][1]
            end = disp[chunk[pos + 1]][1] if pos + 1 < len(chunk) else disp[idx][2] + 0.06
            events.append((start, end, chunk, idx))
    entries, t, n = [], 0.0, 0
    for k, (s, e, chunk, active) in enumerate(events):
        s = max(s, t)
        if k + 1 < len(events):
            e = min(e, max(events[k + 1][0], s + 0.05))
        if e - s < 0.03:
            continue
        if s - t > 0.02:
            entries.append((empty, s - t))
        p = seg_dir / f"f{n:03d}.png"
        draw_caption(label_layer, [(i, disp[i][0]) for i in chunk], active, tpl).save(p)
        n += 1
        entries.append((p, e - s))
        t = e
    if L - t > 0.02 or not entries:
        entries.append((empty, max(L - t, 0.1)))
    lst = seg_dir / "list.ffconcat"
    with open(lst, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for p, dur in entries:
            f.write(f"file '{p.as_posix()}'\nduration {dur:.3f}\n")
        f.write(f"file '{entries[-1][0].as_posix()}'\n")
    return lst


# --------------------------------------------------------------------------
# video render
# --------------------------------------------------------------------------
def zoom_expr(style, N):
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return {
        "in":    (f"1+0.22*on/{N}", cx, cy),
        "out":   (f"1.22-0.22*on/{N}", cx, cy),
        "pan_l": ("1.18", f"(iw-iw/zoom)*(1-on/{N})", cy),
        "pan_r": ("1.18", f"(iw-iw/zoom)*on/{N}", cy),
        "up":    ("1.18", cx, f"(ih-ih/zoom)*(1-on/{N})"),
        "down":  ("1.18", cx, f"(ih-ih/zoom)*on/{N}"),
        "diag":  (f"1+0.2*on/{N}", f"(iw-iw/zoom)*on/{N}", f"(ih-ih/zoom)*on/{N}"),
    }[style]


def render_segment(img, cap_list, L, zoom, tpl, out):
    N = int(round(L * FPS))
    z, x, y = zoom_expr(zoom, N)
    grade = tpl["grade"]
    if tpl["grain"]:
        grade += f",noise=alls={tpl['grain']}:allf=t"
    fc = (f"[0:v]zoompan=z='{z}':x='{x}':y='{y}':d={N}:s={W}x{H}:fps={FPS},"
          f"{grade},format=yuv420p[bg];"
          f"[1:v]fps={FPS},format=rgba[cap];"
          f"[bg][cap]overlay=0:0:format=auto,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(img),
         "-f", "concat", "-safe", "0", "-i", str(cap_list),
         "-filter_complex", fc, "-map", "[v]", "-frames:v", str(N), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", str(out)])


def prepare_music(src, total, out):
    """Music ko video ki exact length par fit karta hai.
    - music lamba  -> total tak trim (end par fade-out assemble me lagta hai)
    - music chhota -> usi track ko dobara jodta hai (smooth crossfade), phir total tak trim"""
    dur = media_duration(src)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if dur >= total:
        cmd += ["-i", str(src), "-t", f"{total:.2f}", "-ar", "44100", "-ac", "2",
                "-c:a", "pcm_s16le", str(out)]
        run(cmd)
        log(f"music: {dur:.1f}s > video {total:.1f}s -> trimmed")
        return out
    reps = int(total // max(dur - 1.0, 1.0)) + 2        # crossfade ki wajah se thoda extra
    xf = max(0.3, min(1.5, dur / 3))
    for _ in range(reps):
        cmd += ["-i", str(src)]
    chain, prev = [], "[0:a]"
    for k in range(1, reps):
        lab = f"[m{k}]"
        chain.append(f"{prev}[{k}:a]acrossfade=d={xf:.2f}:c1=tri:c2=tri{lab}")
        prev = lab
    cmd += ["-filter_complex", ";".join(chain), "-map", prev, "-t", f"{total:.2f}",
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out)]
    run(cmd)
    log(f"music: {dur:.1f}s < video {total:.1f}s -> {reps}x merged with crossfade")
    return out


def assemble(segs, voices, starts, total, transitions, D, tpl, music, sfx, cfg, out):
    n = len(segs)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in segs:
        cmd += ["-i", str(s)]
    for v, _ in voices:
        cmd += ["-i", str(v)]
    cmd += ["-f", "lavfi", "-i", f"color=c={tpl['bar']}:s={W}x14:r={FPS}:d={total:.2f}"]
    bar_idx = 2 * n
    nxt = 2 * n + 1
    sfx_idx = music_idx = None
    if sfx:
        cmd += ["-i", str(sfx)]
        sfx_idx = nxt
        nxt += 1
    if music:
        cmd += ["-i", str(music)]
        music_idx = nxt

    f = []
    prev = "[0:v]"
    for k in range(1, n):
        lab = f"[x{k}]"
        f.append(f"{prev}[{k}:v]xfade=transition={transitions[k-1]}:duration={D}:"
                 f"offset={starts[k]:.3f}{lab}")
        prev = lab
    f.append(f"{prev}fade=t=in:st=0:d=0.3,fade=t=out:st={total-0.5:.2f}:d=0.5[xf]")
    f.append(f"[xf][{bar_idx}:v]overlay=x='-w+W*t/{total:.2f}':y=100[v]")

    fmt = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
    for i, (_, delay) in enumerate(voices):
        f.append(f"[{n+i}:a]{fmt},adelay={int(delay*1000)}:all=1[a{i}]")
    mix_in = "".join(f"[a{i}]" for i in range(n))
    f.append(f"{mix_in}amix=inputs={n}:normalize=0:duration=longest,"
             f"highpass=f=70,acompressor=threshold=0.12:ratio=3:attack=5:release=80:makeup=2,"
             f"equalizer=f=3500:t=q:w=1:g=2,volume=1.5,alimiter=limit=0.95,"
             f"apad=whole_dur={total:.2f}[vo0]")
    if sfx:
        f.append(f"[{sfx_idx}:a]{fmt},volume=0.8[sx]")
        f.append("[vo0][sx]amix=inputs=2:normalize=0:duration=first[vo]")
    else:
        f.append("[vo0]anull[vo]")
    if music:
        f.append(f"[{music_idx}:a]{fmt},volume={cfg['music_volume']},afade=t=in:d=1.5,"
                 f"afade=t=out:st={total-2:.2f}:d=2[m]")
        f.append("[vo]asplit=2[vo1][vo2]")
        f.append("[m][vo2]sidechaincompress=threshold=0.03:ratio=12:attack=10:release=400[md]")
        f.append("[vo1][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        f.append("[vo]loudnorm=I=-14:TP=-1.5:LRA=11[a]")

    cmd += ["-filter_complex", ";".join(f), "-map", "[v]", "-map", "[a]",
            "-t", f"{total:.2f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    run(cmd)


# --------------------------------------------------------------------------
# upload servers (ek fail -> doosra -> teesra ... -> GitHub raw)
# --------------------------------------------------------------------------
def _clean(url):
    url = url.strip()
    if not url.startswith("http"):
        raise ValueError(f"bad response: {url[:120]}")
    return url


def up_catbox(p):
    with open(p, "rb") as f:
        r = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"},
                          files={"fileToUpload": (p.name, f, "video/mp4")},
                          headers={"User-Agent": UA}, timeout=300)
    r.raise_for_status()
    return _clean(r.text)


def up_litterbox(p):
    with open(p, "rb") as f:
        r = requests.post("https://litterbox.catbox.moe/resources/internals/api.php",
                          data={"reqtype": "fileupload", "time": "72h"},
                          files={"fileToUpload": (p.name, f, "video/mp4")},
                          headers={"User-Agent": UA}, timeout=300)
    r.raise_for_status()
    return _clean(r.text)


def up_uguu(p):
    with open(p, "rb") as f:
        r = requests.post("https://uguu.se/upload?output=text",
                          files={"files[]": (p.name, f, "video/mp4")},
                          headers={"User-Agent": UA}, timeout=300)
    r.raise_for_status()
    return _clean(r.text)


def up_0x0(p):
    with open(p, "rb") as f:
        r = requests.post("https://0x0.st", files={"file": (p.name, f, "video/mp4")},
                          headers={"User-Agent": "interesting-fact-bot/1.0"}, timeout=300)
    r.raise_for_status()
    return _clean(r.text)


def up_tmpfiles(p):
    with open(p, "rb") as f:
        r = requests.post("https://tmpfiles.org/api/v1/upload",
                          files={"file": (p.name, f, "video/mp4")},
                          headers={"User-Agent": UA}, timeout=300)
    r.raise_for_status()
    url = _clean(r.json()["data"]["url"])
    return url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)


UPLOAD_SERVERS = [("catbox.moe", up_catbox), ("litterbox.catbox.moe", up_litterbox),
                  ("uguu.se", up_uguu), ("0x0.st", up_0x0), ("tmpfiles.org", up_tmpfiles)]


def github_raw_fallback(path):
    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if not repo:
        return str(path)
    top = Path(run(["git", "rev-parse", "--show-toplevel"]).strip())
    rel = path.resolve().relative_to(top).as_posix()
    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run(["git", "add", "-f", rel])
    run(["git", "commit", "-m", f"video fallback: {path.name}"])
    subprocess.run(["git", "pull", "--rebase", "--autostash"], check=False)
    run(["git", "push"])
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{quote(rel)}"


def upload_video(path):
    for name, fn in UPLOAD_SERVERS:
        for attempt in (1, 2):
            try:
                log(f"[upload] {name} (try {attempt})")
                url = fn(path)
                log(f"[upload] OK -> {url}")
                return url, name
            except Exception as e:
                log(f"[upload] {name} failed: {e}")
                time.sleep(2)
    log("[upload] sab servers fail -> GitHub raw link")
    return github_raw_fallback(path), "github-raw"


# --------------------------------------------------------------------------
# webhook
# --------------------------------------------------------------------------
def send_webhook(payload):
    url = os.getenv("WEBHOOK_INTRESTING_FACT")
    if not url:
        log("WEBHOOK_INTRESTING_FACT set nahi hai -> webhook skip")
        return False
    for i in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=60)
            if r.status_code < 300:
                log("[webhook] sent", r.status_code)
                return True
            log("[webhook] status", r.status_code, r.text[:200])
        except Exception as e:
            log("[webhook] error", e)
        time.sleep(3 * i)
    return False


# --------------------------------------------------------------------------
# cleanup (3 din baad output video delete)
# --------------------------------------------------------------------------
def cleanup_old(days):
    if not OUTPUT_DIR.exists():
        return
    for f in OUTPUT_DIR.glob("fact_video_*.mp4"):
        m = re.search(r"(\d{8}_\d{6})", f.name)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        if now_utc() - ts > timedelta(days=days):
            f.unlink()
            log("[cleanup] deleted", f.name)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    cfg = load_config()
    OUTPUT_DIR.mkdir(exist_ok=True)
    cleanup_old(cfg["output_keep_days"])
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir()
    track = load_track()
    days, n = cfg["cooldown_days"], cfg["facts_per_video"]

    topics = discover_topics()
    log(f"{len(topics)} topic folders mile")
    facts = pick_facts(topics, track, n, days)

    titles = read_lines(BASE / "title.txt")
    hashtags = read_lines(BASE / "hashtag.txt", skip_comments=False)
    title = pick_unique(titles, track["titles"], days, "3 Mind-Blowing Facts You Didn't Know")
    hashtag = pick_unique(hashtags, track["hashtags"], days, "#facts #didyouknow #shorts")
    hook = pick_hook(track)                                   # hook.txt se random

    # template (pichli baar wala repeat nahi)
    last_tpl = track["meta"].get("last_template")
    tpl = random.choice([t for t in TEMPLATES if t["name"] != last_tpl] or TEMPLATES)
    D = float(cfg["transition_duration"])
    log("template:", tpl["name"])

    voice = pick_voice(cfg)
    log(f"voice: {voice} | hook: '{hook[:60]}'")

    # images: hook (topic 1 ki doosri image) + har fact ki image
    log("downloading images ...")
    used = set()
    img_paths = []
    seq = [facts[0]] + facts            # hook, fact1, fact2, fact3
    for i, f in enumerate(seq):
        p = TMP_DIR / f"img{i}.jpg"
        links = read_lines(f["dir"] / "link.txt")
        f["img_url" if i else "hook_img_url"] = download_image(links, p, used)
        img_paths.append(p)

    # narration  (hook + facts)
    narr = [dict(text=hook, kind="hook", label=LABEL_HOOK, topic="")]
    for i, f in enumerate(facts):
        intro = ORDINALS[i] if i < len(ORDINALS) else f"Fact number {i + 1}."
        t = f"{intro} [pause 0.2] {f['text']}"
        if i == len(facts) - 1:
            t += f" [pause 0.3] {CTA}"
        narr.append(dict(text=t, kind="fact", label=LABEL_FACT.format(i=i + 1, n=n),
                         topic=f["topic"]))

    lead, pad, tail = 0.15, 0.35, 0.6
    voices, Ls, token_sets = [], [], []
    for i, seg in enumerate(narr):
        wav = TMP_DIR / f"vo{i}.wav"
        tokens, dur = build_voice(seg["text"], voice, seg["kind"], wav, cfg)
        gap = cfg["hook_gap"] if seg["kind"] == "hook" else pad
        L = lead + dur + gap + D + (tail if i == len(narr) - 1 else 0)
        Ls.append(L)
        voices.append(wav)
        token_sets.append(tokens)

    starts = [0.0]
    for k in range(1, len(narr)):
        starts.append(starts[-1] + Ls[k - 1] - D)
    total = starts[-1] + Ls[-1]

    zooms, prev_z = [], None
    for _ in narr:
        z = random.choice([x for x in tpl["zooms"] if x != prev_z] or tpl["zooms"])
        zooms.append(z)
        prev_z = z
    transitions, prev_t = [], None
    for _ in range(len(narr) - 1):
        t = random.choice([x for x in tpl["transitions"] if x != prev_t] or tpl["transitions"])
        transitions.append(t)
        prev_t = t

    log("rendering segments ...")
    seg_files = []
    for i, seg in enumerate(narr):
        sdir = TMP_DIR / f"seg{i}"
        layer = make_label_layer(seg["label"], seg["topic"], tpl)
        lst = build_caption_list(sdir, token_sets[i], lead, Ls[i], layer, tpl)
        out = TMP_DIR / f"seg{i}.mp4"
        render_segment(img_paths[i], lst, Ls[i], zooms[i], tpl, out)
        seg_files.append(out)

    tracks = sorted(list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.m4a"))
                    + list(MUSIC_DIR.glob("*.wav"))) if MUSIC_DIR.exists() else []
    music = random.choice(tracks) if tracks else None
    log("music:", music.name if music else "none (music/ folder me mp3 daalo)")
    if music:
        music = prepare_music(music, total, TMP_DIR / "music_fit.wav")
    sfx = None
    if cfg["hook_sfx"]:
        sfx = TMP_DIR / "impact.wav"
        make_impact_sfx(sfx)

    stamp = now_utc().strftime("%Y%m%d_%H%M%S")
    final = OUTPUT_DIR / f"fact_video_{stamp}.mp4"
    log("final assemble ...")
    assemble(seg_files, [(v, starts[i] + lead) for i, v in enumerate(voices)],
             starts, total, transitions, D, tpl, music, sfx, cfg, final)
    log(f"video ready: {final} ({final.stat().st_size/1e6:.1f} MB, {total:.1f}s)")

    # track.json update -> 100 din cooldown dobara start
    for f in facts:
        mark_used(track["facts"], f["text"], topic=f["topic"])
    mark_used(track["titles"], title)
    mark_used(track["hashtags"], hashtag)
    track["meta"]["last_template"] = tpl["name"]
    track["meta"]["last_hook"] = hook
    track["meta"]["total_videos"] = track["meta"].get("total_videos", 0) + 1
    save_track(track)

    video_url, server = upload_video(final)
    payload = {
        "automation_name": cfg["automation_name"],
        "social_media_name": cfg["social_media_name"],
        "message": cfg["success_message"],
        "video_url": video_url,
        "title": title,
        "hashtags": hashtag,
        "caption": f"{title}\n\n{hashtag}",
        "upload_server": server,
        "template": tpl["name"],
        "voice": voice,
        "hook": hook,
        "topics": [f["topic"] for f in facts],
        "facts": [f["text"] for f in facts],
        "created_at": now_utc().isoformat(),
    }
    ok = send_webhook(payload)
    cleanup_old(cfg["output_keep_days"])
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    return 0 if ok or not os.getenv("WEBHOOK_INTRESTING_FACT") else 1


if __name__ == "__main__":
    sys.exit(main())
