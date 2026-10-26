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
    s = s.replace("{{BOOK}}", book3d())
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
            "thumb_bg": t.get("thumb_bg") or f"linear-gradient(115deg,{t['bg1']} 30%,{t['bg2']} 130%)",
            "BOOK_CSS": BOOK_CSS, "FIT_JS": FIT_JS}


# A real-looking 3D hardcover: front cover + visible page block + soft floor shadow.
# Size each book with --w/--h/--d on the .b3 element; the title auto-shrinks so the whole cover always fits.
BOOK_CSS = """
.b3{position:absolute;width:var(--w);height:var(--h);perspective:2400px;z-index:2}
.b3:after{content:"";position:absolute;left:4%;right:-6%;bottom:-5%;height:9%;border-radius:50%;
 background:radial-gradient(closest-side,rgba(0,0,0,.6),transparent);filter:blur(6px);z-index:-1}
.b3in{position:relative;width:100%;height:100%;transform-style:preserve-3d;transform:rotateY(var(--ry,-14deg))}
.b3 .face{position:absolute;top:0;left:0;backface-visibility:hidden;box-sizing:border-box}
.b3 .front{width:100%;height:100%;transform:translateZ(calc(var(--d)/2));overflow:hidden;
 background:linear-gradient(160deg,var(--c1),var(--c2));border-radius:3px 10px 10px 3px;color:var(--ink);
 display:flex;flex-direction:column;justify-content:space-between;padding:calc(var(--w)*.11) calc(var(--w)*.1) calc(var(--w)*.1) calc(var(--w)*.14)}
.b3 .front:before{content:"";position:absolute;left:0;top:0;bottom:0;width:calc(var(--w)*.075);
 background:linear-gradient(90deg,rgba(0,0,0,.28),rgba(255,255,255,.25) 55%,rgba(0,0,0,.12) 75%,transparent)}
.b3 .front:after{content:"";position:absolute;inset:0;pointer-events:none;
 background:linear-gradient(115deg,rgba(255,255,255,.35) 0%,rgba(255,255,255,0) 38%,rgba(0,0,0,0) 70%,rgba(0,0,0,.18) 100%)}
.b3 .pages{width:var(--d);height:calc(100% - 10px);top:5px;left:calc(var(--w) - var(--d)/2);transform:rotateY(90deg);
 background:linear-gradient(90deg,rgba(0,0,0,.22),rgba(0,0,0,0) 30%,rgba(0,0,0,0) 70%,rgba(0,0,0,.15)),
 repeating-linear-gradient(90deg,#fbf7ee 0 2px,#ddd4c2 2px 3px)}
.b3 .back{width:100%;height:100%;transform:rotateY(180deg) translateZ(calc(var(--d)/2));background:var(--c2);border-radius:10px 3px 3px 10px}
.b3 .top{width:100%;height:var(--d);top:calc(var(--d)/-2);transform:rotateX(90deg);background:#efe8da}
.b3 .tag{font-size:calc(var(--w)*.052);opacity:.75;font-weight:700;position:relative}
.b3 .t{font-family:Serif,serif;font-size:calc(var(--w)*.19);line-height:1.02;position:relative;overflow-wrap:normal}
.b3 .s{font-size:calc(var(--w)*.06);line-height:1.35;opacity:.85;position:relative}
.b3 .a{font-size:calc(var(--w)*.052);letter-spacing:.16em;text-transform:uppercase;font-weight:700;position:relative}
"""

FIT_JS = """<script>
document.fonts.ready.then(function(){document.querySelectorAll('.b3 .front').forEach(function(f){
 var t=f.querySelector('.t'),s=parseFloat(getComputedStyle(t).fontSize);
 while((f.scrollHeight>f.clientHeight+1||t.scrollWidth>t.clientWidth+1)&&s>14){s-=1;t.style.fontSize=s+'px';}
});});
</script>"""


def book3d(cls=""):
    return ('<div class="b3 ' + cls + '"><div class="b3in">'
            '<div class="face back"></div><div class="face top"></div><div class="face pages"></div>'
            '<div class="face front"><div class="tag">{{cover_tag}}</div><div class="t">{{book_html}}</div>'
            '<div class="s">{{cover_sub}}</div><div class="a">{{author}}</div></div></div></div>')


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


def captions(words, p, work, total, bottom=False):
    hi = ass_color(p["theme"].get("hi", "#3CE36A"))
    if bottom:  # full-screen pictures: captions bottom-centre with a thick outline so they read on any photo
        style = f"Style: Cap,{CAP_FONT},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,3,2,120,120,70,1"
    else:
        style = f"Style: Cap,{CAP_FONT},124,&H00FFFFFF,&H00FFFFFF,&H64000000,&H96000000,0,0,0,0,100,100,0,0,1,2,5,5,720,60,0,1"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style}

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
    """Scene-by-scene video (new pictures every ~12 s). If pictures cannot be found, falls back to the
    single-screen book video. Returns (mp4, first scene picture or None)."""
    from tts import dur
    total = dur(audio)
    bg = background(p, work)
    hi = p["theme"].get("hi", "#3CE36A").lstrip("#")
    fdir = FONTS.replace(":", "\\:")
    if os.environ.get("VIDEO_STYLE", "scenes") == "scenes":
        try:
            import scenes
            sv, first = scenes.build(p, words, total, bg, work)
            ass = captions(words, p, work, total, bottom=True)
            esc = ass.replace("\\", "/").replace(":", "\\:")
            fc = (f"[0:v]ass='{esc}':fontsdir='{fdir}',"
                  f"drawbox=x=0:y=ih-8:w='iw*t/{total:.2f}':h=8:color=0x{hi}@0.9:t=fill[v]")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", "-i", sv, "-i", audio, "-filter_complex", fc,
                            "-map", "[v]", "-map", "1:a", "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "26", "-maxrate", "4000k", "-bufsize", "8000k",
                            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out], check=True)
            return out, first
        except Exception as e:
            print("scene video failed, using the book-screen video instead:", e)
    pt = particles(p, work)
    ass = captions(words, p, work, total)
    esc = ass.replace("\\", "/").replace(":", "\\:")
    fc = (f"[0:v]format=gbrp[b];[1:v]format=gbrp[q];[b][q]blend=all_mode=screen,format=yuv420p,"
          f"ass='{esc}':fontsdir='{fdir}',"
          f"drawbox=x=0:y=ih-8:w='iw*t/{total:.2f}':h=8:color=0x{hi}@0.9:t=fill[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", "-loop", "1", "-framerate", str(FPS), "-i", bg,
                    "-stream_loop", "-1", "-i", pt, "-i", audio, "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
                    "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                    "-maxrate", "2500k", "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", out], check=True)
    return out, None


def thumbnails(p, work, photo_path=None, scene_path=None):
    """A: book left + scene picture behind the words (Arc style). B: words + book + person photo."""
    v = book_vals(p)
    outs = []
    a = p["thumb_a"]
    words_a = f"<span>{html.escape(a[0])}</span><span class='box'>{html.escape(a[1])}</span><span>{html.escape(a[2])}</span>"
    oa = os.path.join(work, "thumb_A.png")
    bgp = scene_path or photo_path
    shot(fill("thumb.html", {**v, "variant": "A has-bg" if bgp else "A", "words": words_a,
                             "photo_div": '<div class="scene"></div>' if bgp else "",
                             "photo": "file://" + os.path.abspath(bgp) if bgp else ""}), oa, 1280, 720, work)
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
