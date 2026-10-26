"""Build the background, particles, karaoke captions and the final MP4; plus thumbnails."""
import html, math, os, random, re, subprocess
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get("FONT_DIR", os.path.join(HERE, "..", "fonts"))
FONT_DEV = os.environ.get("FONT_DEV", os.path.join(FONTS, "Mukta-ExtraBold.ttf"))
FONT_THUMB = os.environ.get("FONT_THUMB", os.path.join(FONTS, "Baloo2-ExtraBold.ttf"))
FONT_SERIF = os.environ.get("FONT_SERIF", os.path.join(FONTS, "DMSerifDisplay-Regular.ttf"))
CAP_FONT = os.environ.get("CAP_FONT_NAME", "Mukta ExtraBold")
W, H, FPS = 1920, 1080, 24


def fill(tpl, vals):
    s = open(os.path.join(HERE, "templates", tpl), encoding="utf-8").read()
    for k, v in vals.items():
        s = s.replace("{{" + k + "}}", str(v))
    return s


def shot(page_html, out, w, h, work):
    from playwright.sync_api import sync_playwright
    src = os.path.join(work, os.path.basename(out) + ".html")
    open(src, "w", encoding="utf-8").write(page_html)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.goto("file://" + os.path.abspath(src))
        pg.wait_for_timeout(800)
        pg.screenshot(path=out)
        b.close()


def book_vals(p):
    t = p["theme"]
    words = p["book"].split()
    longest = max(len(x) for x in words)
    title_px = max(52, min(92, int(820 / max(longest, 6))))
    return {"FONT_DEV": "file://" + FONT_DEV, "FONT_SERIF": "file://" + FONT_SERIF, "FONT_THUMB": "file://" + FONT_THUMB,
            "bg1": t["bg1"], "bg2": t["bg2"], "cover1": t["cover1"], "cover2": t["cover2"], "ink": t["ink"],
            "cover_tag": html.escape(p.get("cover_tag", "")), "cover_sub": html.escape(p.get("cover_sub", "")),
            "author": html.escape(p["author"]), "book_html": "<br>".join(html.escape(x) for x in words),
            "title_px": title_px, "title_px_t": int(title_px * 0.8), "title_px_s": int(title_px * 0.5),
            "thumb_bg": t.get("thumb_bg") or f"linear-gradient(115deg,{t['bg1']} 30%,{t['bg2']} 130%)"}


def background(p, work):
    out = os.path.join(work, "bg.png")
    shot(fill("frame.html", book_vals(p)), out, W, H, work)
    return out


def particles(p, work, seconds=12):
    """Seamless looping glow particles on black; blended onto the background with 'screen'."""
    rgb = tuple(int(x) for x in p["theme"].get("dust", "255,220,150").split(","))
    rnd = random.Random(7)
    pts = [dict(x=rnd.random() * W, y=rnd.random() * H, r=rnd.uniform(2, 5), k=rnd.choice([1, 1, 2]),
                ph=rnd.random() * 6.28, tw=rnd.choice([1, 2, 3])) for _ in range(55)]
    d = os.path.join(work, "pt")
    os.makedirs(d, exist_ok=True)
    n = seconds * FPS
    for i in range(n):
        f = i / n
        im = Image.new("RGB", (W, H), (0, 0, 0))
        dr = ImageDraw.Draw(im)
        for q in pts:
            y = (q["y"] - f * q["k"] * H) % H
            x = q["x"] + 14 * math.sin(2 * math.pi * f + q["ph"])
            a = 0.35 + 0.35 * math.sin(2 * math.pi * f * q["tw"] + q["ph"])
            c = tuple(int(v * a) for v in rgb)
            r = q["r"]
            dr.ellipse([x - r, y - r, x + r, y + r], fill=c)
        im = im.filter(ImageFilter.GaussianBlur(1.6))
        im.save(os.path.join(d, f"{i:04d}.png"))
    out = os.path.join(work, "particles.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", os.path.join(d, "%04d.png"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out], check=True)
    return out


def ass_color(hexc):
    h = hexc.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def ts(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def lines(words, max_words=4, max_chars=26):
    """Group timed words into short caption lines; break at sentence punctuation."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x[2] for x in cur)
        if len(cur) >= max_words or len(text) >= max_chars or re.search(r"[।?!,]$", w[2]):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def captions(words, p, work, total):
    hi = ass_color(p["theme"].get("hi", "#3CE36A"))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{CAP_FONT},124,&H00FFFFFF,&H00FFFFFF,&H64000000,&H96000000,0,0,0,0,100,100,0,0,1,2,5,5,720,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    groups = lines(words)
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0][0] if gi + 1 < len(groups) else total
        g_end = min(nxt, g[-1][1] + 1.2)
        clean = [re.sub(r"[{}\\]", "", x[2]) for x in g]
        for wi, w in enumerate(g):
            start = w[0]
            end = g[wi + 1][0] if wi + 1 < len(g) else g_end
            if end <= start:
                continue
            txt = " ".join((f"{{\\c{hi}}}{c}{{\\c&H00FFFFFF&}}" if i == wi else c) for i, c in enumerate(clean))
            ev.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{txt}")
    path = os.path.join(work, "cap.ass")
    open(path, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
    return path


def video(p, audio, words, work, out):
    from tts import dur
    total = dur(audio)
    bg = background(p, work)
    pt = particles(p, work)
    ass = captions(words, p, work, total)
    hi = p["theme"].get("hi", "#3CE36A").lstrip("#")
    esc = ass.replace("\\", "/").replace(":", "\\:")
    fdir = FONTS.replace(":", "\\:")
    fc = (f"[0:v]format=gbrp[b];[1:v]format=gbrp[q];[b][q]blend=all_mode=screen,format=yuv420p,"
          f"ass='{esc}':fontsdir='{fdir}',"
          f"drawbox=x=0:y=ih-8:w='iw*t/{total:.2f}':h=8:color=0x{hi}@0.9:t=fill[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", "-loop", "1", "-framerate", str(FPS), "-i", bg,
                    "-stream_loop", "-1", "-i", pt, "-i", audio, "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
                    "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                    "-maxrate", "2500k", "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", out], check=True)
    return out


def thumbnails(p, work, photo_path=None):
    v = book_vals(p)
    outs = []
    a = p["thumb_a"]
    words_a = f"<span>{html.escape(a[0])}</span><span class='box'>{html.escape(a[1])}</span><span>{html.escape(a[2])}</span>"
    oa = os.path.join(work, "thumb_A.png")
    shot(fill("thumb.html", {**v, "variant": "A", "words": words_a, "photo_div": "", "photo": ""}), oa, 1280, 720, work)
    outs.append(oa)
    b = p["thumb_b"]
    words_b = f"<span>{html.escape(b[0])}</span><span class='brush'>{html.escape(b[1])}</span><span>{html.escape(b[2])}</span>"
    has = bool(photo_path)
    ob = os.path.join(work, "thumb_B.png")
    shot(fill("thumb.html", {**v, "variant": "B has-photo" if has else "B", "words": words_b,
                             "photo_div": '<div class="photo"></div>' if has else "",
                             "photo": "file://" + os.path.abspath(photo_path) if has else ""}), ob, 1280, 720, work)
    outs.append(ob)
    return outs
