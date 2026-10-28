"""'Book on the left' audiobook style (like the reference channel the owner picked):

VIDEO     one moody background photo for the whole video, a big 3D hardcover on the left (spine showing),
          2-line white captions on the right with the spoken word in green, and white audio bars at the
          bottom right that move with the voice.
THUMBNAIL warm golden light-burst background with bokeh, the same 3D book on the left with a yellow
          swoosh under it and a red arrow pointing at it, and three big lines on the right:
          white  /  black on a yellow brush stroke  /  bright green.

The cover art is our own (a Pexels photo + the title), never the publisher's cover."""
import html, os, re, subprocess
import render
from render import W, H, FPS, FONTS, CAP_FONT, shot, ts

THEME_FALLBACK = "man silhouette sunrise mountains"


# ---------------------------------------------------------------- pictures
def theme_photo(p, work):
    """One cinematic landscape photo that fits the book's idea; used on the cover and as the video background."""
    q = ""
    try:
        from llm import chat
        d = chat("You pick one stock photo for a book-summary video. Reply with JSON only.",
                 f'Book: "{p["book"]}" by {p["author"]}. Idea: {p.get("angle", "")}\n'
                 'Give a 3-5 word English Pexels search for ONE moody, cinematic, symbolic photo that shows the '
                 'book\'s core idea (e.g. "man silhouette sunrise mountains", "lonely man city night rain", '
                 '"stairs light success"). No text, no logos. Return {"q": "..."}',
                 as_json=True, max_tokens=200, temperature=0.6)
        q = str(d.get("q") or "").strip()
    except Exception as e:
        print("theme query failed", e)
        words = re.findall(r"[A-Za-z]{4,}", p["book"])
        q = " ".join(words[:2]) if words else ""
    import scenes
    pics = scenes.Pics(work)
    out = os.path.join(work, "theme.jpg")
    for query in [q, p.get("person_query", ""), THEME_FALLBACK]:
        if query and pics.pexels(query, out):           # only if a PEXELS_KEY secret exists
            return out
    for query in [q, " ".join(q.split()[-2:]), "sunrise mountains"]:
        if query and openverse(query, out):             # free, no key (copyright-free CC0 photos)
            return out
    return painted(p, out)                               # never fails: our own drawn scene


def openverse(q, out):
    """Copyright-free (CC0 / public domain) landscape photo from Openverse. No key needed."""
    import requests
    try:
        r = requests.get("https://api.openverse.org/v1/images/", timeout=25,
                         params={"q": q, "license": "cc0,pdm", "category": "photograph", "aspect_ratio": "wide",
                                 "page_size": 10, "mature": "false"})
        for x in (r.json().get("results") or []):
            if (x.get("width") or 0) < 1200:
                continue
            img = requests.get(x["url"], timeout=40)
            if img.ok and len(img.content) > 50000:
                open(out, "wb").write(img.content)
                from PIL import Image
                Image.open(out).convert("RGB").save(out, "JPEG", quality=92)   # check it really is an image
                return out
    except Exception as e:
        print("openverse fail", q, e)
    return None


PALETTES = [  # sky top, sky middle, horizon glow, sun, far hills, near hills
    ("#0b1d3a", "#3d4f8a", "#f6a04d", "#ffe9b0", "#2a3150", "#0c0f1c"),
    ("#120c2e", "#5a2d6e", "#ff8a5c", "#ffd9a0", "#2e1f45", "#0d0816"),
    ("#06232e", "#1f5e6e", "#f2c46b", "#fff1c2", "#163c47", "#061218"),
    ("#1a0f0a", "#6b2f1a", "#ffb347", "#fff0b8", "#3b1d12", "#120805"),
    ("#0a1626", "#24466b", "#e8a87c", "#ffe3c4", "#1d2f45", "#070c14"),
]


def painted(p, out, w=1920, h=1280):
    """Draw a cinematic scene: glowing sunrise, layered hills, birds and a person with raised arms."""
    import hashlib, math, random
    from PIL import Image, ImageDraw, ImageFilter
    seed = int(hashlib.md5(p["book"].encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    top, mid, glow, sun, far, near = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in PALETTES[seed % len(PALETTES)]]
    hz = int(h * 0.62)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    mix = lambda a, b, t: tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    for y in range(h):
        t = y / hz
        c = mix(top, mid, min(t * 1.4, 1)) if t < 0.7 else mix(mid, glow, min((t - 0.7) / 0.3, 1))
        d.line([(0, y), (w, y)], fill=c)
    px = int(w * rnd.choice([0.40, 0.58]))            # person stays inside the cover crop
    sx, sy = int(w * (0.60 if px < w / 2 else 0.42)), int(hz - h * 0.06)
    halo = Image.new("L", (w, h), 0)
    ImageDraw.Draw(halo).ellipse([sx - 420, sy - 420, sx + 420, sy + 420], fill=170)
    im.paste(Image.new("RGB", (w, h), glow), (0, 0), halo.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(im)
    d.ellipse([sx - 95, sy - 95, sx + 95, sy + 95], fill=sun)
    for k in range(18):                                     # soft light rays
        a = k / 18 * math.pi * 2 + rnd.random() * 0.1
        ray = Image.new("L", (w, h), 0)
        ImageDraw.Draw(ray).polygon([(sx, sy), (sx + math.cos(a) * 1600, sy + math.sin(a) * 1600),
                                     (sx + math.cos(a + 0.05) * 1600, sy + math.sin(a + 0.05) * 1600)], fill=40)
        im.paste(Image.new("RGB", (w, h), sun), (0, 0), ray.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)

    def ridge(base, amp, color, step):
        pts, y = [(0, h)], base
        for x in range(0, w + step, step):
            y = max(base - amp, min(base + amp // 3, y + rnd.randint(-amp // 3, amp // 3)))
            pts.append((x, y))
        pts.append((w, h))
        d.polygon(pts, fill=color)
    ridge(hz - 40, 140, mix(far, glow, 0.25), 90)
    ridge(hz + 40, 110, far, 70)
    # near hill where the person stands
    hill = [(0, h)] + [(x, int(h * 0.80 - 120 * math.exp(-((x - px) / 420) ** 2))) for x in range(0, w + 40, 40)] + [(w, h)]
    d.polygon(hill, fill=near)
    top_y = int(h * 0.80 - 120)
    s = 1.0
    body = near
    d.ellipse([px - 22 * s, top_y - 250 * s, px + 22 * s, top_y - 205 * s], fill=body)                     # head
    d.polygon([(px - 34, top_y - 200), (px + 34, top_y - 200), (px + 26, top_y - 95), (px - 26, top_y - 95)], fill=body)
    d.line([(px - 30, top_y - 190), (px - 95, top_y - 300)], fill=body, width=22)                          # raised arms
    d.line([(px + 30, top_y - 190), (px + 95, top_y - 300)], fill=body, width=22)
    d.line([(px - 14, top_y - 100), (px - 30, top_y + 5)], fill=body, width=26)                            # legs
    d.line([(px + 14, top_y - 100), (px + 30, top_y + 5)], fill=body, width=26)
    for _ in range(rnd.randint(9, 16)):                                                                     # birds
        bx, by, bs = rnd.randint(int(w * .3), int(w * .95)), rnd.randint(int(h * .12), int(h * .45)), rnd.randint(10, 24)
        d.line([(bx - bs, by - bs // 2), (bx, by), (bx + bs, by - bs // 2)], fill=mix(top, near, .7), width=4)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    im.save(out, "JPEG", quality=92)
    return out


# ---------------------------------------------------------------- 3D book (spine on the left)
BOOK_CSS = """
.bk{position:absolute;width:var(--w);height:var(--h);perspective:2600px;z-index:3}
.bk:after{content:"";position:absolute;left:-4%;right:0;bottom:-4.5%;height:8%;border-radius:50%;
 background:radial-gradient(closest-side,rgba(0,0,0,.75),transparent);filter:blur(8px);z-index:-1}
.bkin{position:relative;width:100%;height:100%;transform-style:preserve-3d;transform:rotateY(var(--ry,33deg))}
.bk .f{position:absolute;top:0;left:0;backface-visibility:hidden;box-sizing:border-box}
.bk .front{width:100%;height:100%;transform:translateZ(calc(var(--d)/2));overflow:hidden;border-radius:2px 8px 8px 2px;
 background:#0d1b2a var(--art) center 62%/cover no-repeat;color:#fff;display:flex;flex-direction:column;align-items:center;
 justify-content:space-between;padding:calc(var(--w)*.09) calc(var(--w)*.07) calc(var(--w)*.07);text-align:center}
.bk .front:before{content:"";position:absolute;inset:0;
 background:linear-gradient(180deg,rgba(6,16,30,.92) 0%,rgba(6,16,30,.55) 30%,rgba(6,16,30,0) 52%,rgba(6,16,30,0) 78%,rgba(6,16,30,.7) 100%)}
.bk .front:after{content:"";position:absolute;inset:0;pointer-events:none;
 background:linear-gradient(100deg,rgba(255,255,255,.28),rgba(255,255,255,0) 30%),linear-gradient(90deg,rgba(0,0,0,.45),rgba(0,0,0,0) 7%)}
.bk .t{position:relative;font-family:Serif,serif;font-size:calc(var(--w)*.17);line-height:1.02;letter-spacing:.01em;
 text-transform:uppercase;background:linear-gradient(180deg,#d8fff7 0%,#5fe0d0 55%,#2aa9a0 100%);-webkit-background-clip:text;
 background-clip:text;color:transparent;filter:drop-shadow(0 3px 6px rgba(0,0,0,.8))}
.bk .a{position:relative;font-family:Serif,serif;font-size:calc(var(--w)*.06);letter-spacing:.2em;text-transform:uppercase;
 color:#e8f6f4;text-shadow:0 2px 6px #000}
.bk .spine{width:var(--d);height:100%;left:calc(var(--d)/-2);transform:rotateY(-90deg);
 background:linear-gradient(90deg,#08121e,#1a2c40 45%,#0b1724);display:flex;align-items:center;justify-content:center;overflow:hidden}
.bk .spine span{writing-mode:vertical-rl;font-family:Serif,serif;font-size:calc(var(--d)*.42);color:#5fe0d0;
 text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}
.bk .pages{width:var(--d);height:calc(100% - 10px);top:5px;left:calc(var(--w) - var(--d)/2);transform:rotateY(90deg);
 background:repeating-linear-gradient(90deg,#fbf7ee 0 2px,#ddd4c2 2px 3px)}
.bk .back{width:100%;height:100%;transform:rotateY(180deg) translateZ(calc(var(--d)/2));background:#0b1724}
"""

FIT = """<script>
function fitAll(){
 document.querySelectorAll('.bk .front').forEach(function(f){var t=f.querySelector('.t'),s=parseFloat(getComputedStyle(t).fontSize);
  while((t.scrollWidth>t.clientWidth+1||f.scrollHeight>f.clientHeight+1)&&s>14){s-=1;t.style.fontSize=s+'px';}});
 document.querySelectorAll('.fitline').forEach(function(e){var s=parseFloat(getComputedStyle(e).fontSize),max=e.parentNode.clientWidth;
  while(e.offsetWidth>max&&s>30){s-=2;e.style.fontSize=s+'px';}});
}
document.fonts.ready.then(fitAll);
</script>"""


def book(p, art):
    title = html.escape(p["book"])
    short = html.escape(re.split(r"[:(]", p["book"])[0].strip())
    style = f"--art:url('file://{os.path.abspath(art)}');" if art else "--art:radial-gradient(circle at 50% 60%,#ffd27a,#1b3550 60%);"
    return (f'<div class="bk" style="{style}"><div class="bkin"><div class="f back"></div><div class="f pages"></div>'
            f'<div class="f spine"><span>{short}</span></div>'
            f'<div class="f front"><div class="t">{title}</div><div class="a">{html.escape(p["author"])}</div></div></div></div>')


def fonts():
    return (f'@font-face{{font-family:Dev;src:url("file://{render.FONT_DEV}")}}'
            f'@font-face{{font-family:Thumb;src:url("file://{render.FONT_THUMB}");font-weight:400 800}}'
            f'@font-face{{font-family:Serif;src:url("file://{render.FONT_SERIF}")}}')


# ---------------------------------------------------------------- video
def frame(p, art, work):
    bg = f"url('file://{os.path.abspath(art)}') center/cover" if art else "radial-gradient(120% 90% at 70% 40%,#3a2a18,#0b0d12 70%)"
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts()}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#000}}
.bg{{position:absolute;inset:0;background:{bg};filter:brightness(.62) saturate(1.05)}}
.sh{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.55),rgba(0,0,0,.15) 38%,rgba(0,0,0,.25) 70%,rgba(0,0,0,.55)),
 radial-gradient(130% 100% at 60% 45%,rgba(0,0,0,0) 55%,rgba(0,0,0,.6))}}
{BOOK_CSS}
.bk{{--w:600px;--h:900px;--d:84px;left:70px;top:90px}}
</style></head><body><div class="bg"></div><div class="sh"></div>{book(p, art)}{FIT}</body></html>"""
    out = os.path.join(work, "arc_bg.png")
    shot(page, out, W, H, work)
    return out


def captions(words, work, total, hi="&H001FE052&"):
    """2-line white captions on the right half, current word green."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{CAP_FONT},104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,4,4,7,790,60,350,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    groups = render.lines(words, max_words=8, max_chars=44)
    ev = []
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0][0] if gi + 1 < len(groups) else total
        g_end = min(nxt, g[-1][1] + 1.2)
        clean = [re.sub(r"[{}\\]", "", x[2]) for x in g]
        cut = (len(clean) + 1) // 2 if len(" ".join(clean)) > 22 else len(clean)
        for wi, w in enumerate(g):
            start, end = w[0], (g[wi + 1][0] if wi + 1 < len(g) else g_end)
            if end <= start:
                continue
            parts = [(f"{{\\c{hi}}}{c}{{\\c&H00FFFFFF&}}" if i == wi else c) for i, c in enumerate(clean)]
            txt = " ".join(parts[:cut]) + ("\\N" + " ".join(parts[cut:]) if cut < len(parts) else "")
            ev.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{txt}")
    path = os.path.join(work, "cap_arc.ass")
    open(path, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
    return path


def video(p, audio, words, work, out, total):
    art = theme_photo(p, work)
    bg = frame(p, art, work)
    ass = captions(words, work, total)
    esc = ass.replace("\\", "/").replace(":", "\\:")
    fdir = FONTS.replace(":", "\\:")
    # audio bars: frequency bars -> keep 3 of every 4 columns (gaps) -> mirror -> scale up crisp
    fc = (f"[1:a]aformat=channel_layouts=mono,showfreqs=s=120x40:mode=bar:ascale=cbrt:fscale=log:win_size=256:averaging=2:"
          f"colors=white,format=rgba,geq=r='255':g='255':b='255':a='if(lt(mod(X\\,2)\\,1)\\,alpha(X\\,Y)\\,0)',"
          f"split[u][d];[d]vflip[dd];[u][dd]vstack,scale=1080:180:flags=neighbor[bars];"
          f"[0:v][bars]overlay=x=790:y=850:format=auto,ass='{esc}':fontsdir='{fdir}',format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", "-loop", "1", "-framerate", str(FPS), "-i", bg, "-i", audio,
                    "-filter_complex", fc, "-map", "[v]", "-map", "1:a", "-t", f"{total:.2f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-maxrate", "3000k", "-bufsize", "6000k",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out], check=True)
    return out, art


# ---------------------------------------------------------------- thumbnail
def thumb(p, lines, art, out, work, brush="#FFD21F"):
    l1, l2, l3 = (html.escape(x) for x in lines)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts()}
html,body{{margin:0;width:1280px;height:720px;overflow:hidden}}
body{{position:relative;background:
 radial-gradient(60% 75% at 68% 30%,rgba(255,214,110,.95) 0%,rgba(244,160,40,.85) 16%,rgba(160,80,10,.75) 38%,rgba(40,18,4,.95) 70%,#0c0603 100%)}}
.rays{{position:absolute;inset:-20%;background:repeating-conic-gradient(from 0deg at 68% 30%,rgba(255,230,160,.10) 0deg 4deg,rgba(255,230,160,0) 4deg 11deg);
 -webkit-mask-image:radial-gradient(55% 60% at 60% 35%,#000,transparent);mask-image:radial-gradient(55% 60% at 60% 35%,#000,transparent)}}
.bo{{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(255,200,120,.55),rgba(255,170,60,0) 70%);filter:blur(2px)}}
.sw{{position:absolute;left:-160px;bottom:-205px;width:760px;height:280px;border-radius:50%;border-top:34px solid #FFC400;
 transform:rotate(-8deg);filter:drop-shadow(0 4px 8px rgba(0,0,0,.5));z-index:2}}
{BOOK_CSS}
.bk{{--w:400px;--h:600px;--d:60px;left:52px;top:56px}}
.arrow{{position:absolute;left:350px;top:505px;width:250px;height:200px;z-index:4;filter:drop-shadow(0 4px 6px rgba(0,0,0,.6))}}
.txt{{position:absolute;left:480px;right:28px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:4px;z-index:5;
 font-family:Thumb,Dev,sans-serif;font-weight:800;line-height:1.12}}
.row{{width:100%;display:flex;justify-content:center}}
.fitline{{display:inline-block;white-space:nowrap}}
.l1{{font-size:150px;color:#fff;text-shadow:0 0 2px #000,0 6px 0 rgba(0,0,0,.55),0 10px 24px rgba(0,0,0,.7)}}
.l2{{font-size:138px;color:#111;padding:0 46px 6px;background:{brush};
 clip-path:polygon(3% 14%,10% 4%,30% 9%,55% 2%,80% 8%,97% 3%,100% 30%,96% 52%,100% 78%,93% 97%,65% 92%,40% 99%,15% 93%,2% 98%,5% 70%,0 45%);
 filter:drop-shadow(0 6px 10px rgba(0,0,0,.5))}}
.l3{{font-size:150px;color:#7BFF1F;-webkit-text-stroke:7px #000;paint-order:stroke fill;text-shadow:0 8px 18px rgba(0,0,0,.7)}}
</style></head><body>
<div class="rays"></div>
<div class="bo" style="left:820px;top:520px;width:110px;height:110px"></div><div class="bo" style="left:1120px;top:420px;width:70px;height:70px"></div>
<div class="bo" style="left:640px;top:80px;width:60px;height:60px"></div><div class="bo" style="left:1180px;top:600px;width:120px;height:120px"></div>
<div class="sw"></div>
{book(p, art)}
<svg class="arrow" viewBox="0 0 250 200"><path d="M235 150 C 190 195, 110 190, 60 120" fill="none" stroke="#E5141B" stroke-width="22" stroke-linecap="round"/>
<path d="M20 70 L 95 92 L 45 150 Z" fill="#E5141B"/></svg>
<div class="txt"><div class="row"><span class="fitline l1">{l1}</span></div><div class="row"><span class="fitline l2">{l2}</span></div>
<div class="row"><span class="fitline l3">{l3}</span></div></div>
{FIT}</body></html>"""
    shot(page, out, 1280, 720, work)
    return out


def thumbnails(p, work, art):
    a = os.path.join(work, "thumb_A.png")
    b = os.path.join(work, "thumb_B.png")
    thumb(p, p["thumb_a"], art, a, work)
    thumb(p, p["thumb_b"], art, b, work, brush="#FFD21F")
    return [a, b]
