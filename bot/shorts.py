"""Cut YouTube Shorts (1080x1920, under 60 s) from the finished long video.

Each Short is one idea from the book: it starts at a chapter start and ends on a sentence end.
Layout: blurred moving background, the 16:9 video (with its karaoke captions) in the middle,
a big Hindi hook on top and a "full video on the channel" line at the bottom.
"""
import html, os, re, subprocess

import render

W, H = 1080, 1920
MIN_LEN, MAX_LEN = 25.0, 55.0


def segments(words, chapters, total, n):
    """Pick n (start, end, chapter title) clips from chapters, skipping the intro and the ending."""
    ends = [i for i, (_, _, w) in enumerate(words) if re.search(r"[।?!.]$", w.strip())]
    body = [(t, title) for t, title in chapters[1:] if title not in ("आखिरी बात", "निष्कर्ष")] or chapters
    if len(body) > n:  # spread the picks over the video
        step = len(body) / n
        body = [body[int(i * step)] for i in range(n)]
    starts = sorted(t for t, _ in chapters) + [total]
    out = []
    for t0, title in body[:n]:
        start = t0 + 0.15
        nxt = next((t for t in starts if t > t0 + 1), total)  # stay inside this chapter
        cands = [words[i][1] for i in ends if MIN_LEN <= words[i][1] - start <= MAX_LEN and words[i][1] <= nxt]
        end = max(cands) if cands else min(start + 50, nxt - 0.3, total - 0.5)
        if end - start >= 15:
            out.append((start, end + 0.25, title))
    return out


def overlay(p, hook, work, out):
    """Transparent PNG with the hook text on top and the call to action at the bottom."""
    from playwright.sync_api import sync_playwright
    th = p.get("theme", {})
    bg1, hi = th.get("bg1", "#121A24"), th.get("hi", "#3CE36A")
    font = "file://" + os.path.abspath(render.FONT_DEV)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Dev;src:url("{font}")}}
html,body{{margin:0;width:{W}px;height:{H}px;background:transparent;font-family:Dev,sans-serif;color:#fff}}
.top{{position:absolute;left:0;right:0;top:0;height:640px;background:linear-gradient(180deg,{bg1} 70%,rgba(0,0,0,0));
 display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 70px;box-sizing:border-box}}
.book{{font-size:46px;opacity:.85;margin-bottom:22px;letter-spacing:.5px}}
.hook{{font-size:96px;line-height:1.15;text-shadow:0 6px 24px rgba(0,0,0,.5)}}
.hook b{{color:{hi};font-weight:inherit}}
.bot{{position:absolute;left:0;right:0;bottom:0;height:560px;background:linear-gradient(0deg,{bg1} 72%,rgba(0,0,0,0));
 display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 70px;box-sizing:border-box}}
.cta{{font-size:60px;background:{hi};color:#111;padding:18px 44px;border-radius:60px}}
.ch{{font-size:44px;margin-top:28px;opacity:.9}}
</style></head><body>
<div class="top"><div class="book">{html.escape(p['book_hi'] or p['book'])}</div><div class="hook">{hook}</div></div>
<div class="bot"><div class="cta">पूरी किताब का सार 👉 चैनल पर</div><div class="ch">@booksaarhindiofficial</div></div>
</body></html>"""
    src = os.path.join(work, os.path.basename(out) + ".html")
    open(src, "w", encoding="utf-8").write(page)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto("file://" + os.path.abspath(src))
        pg.wait_for_timeout(600)
        pg.screenshot(path=out, omit_background=True)
        b.close()


def hook_html(title):
    """Chapter title as the hook, last word highlighted."""
    words = html.escape(title.strip()).split()
    if len(words) > 1:
        return " ".join(words[:-1]) + " <b>" + words[-1] + "</b>"
    return "<b>" + " ".join(words) + "</b>"


def cut(mp4, start, end, png, out):
    d = end - start
    fc = ("[0:v]split[a][b];"
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2,eq=brightness=-0.22[bg];"
          f"[b]scale={W}:-2[fg];[bg][fg]overlay=0:(H-h)/2[v1];[v1][1:v]overlay=0:0,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{d:.2f}", "-i", mp4, "-i", png,
                    "-filter_complex", fc, "-map", "[v]", "-map", "0:a",
                    "-af", f"afade=t=in:d=0.25,afade=t=out:st={max(0.0, d - 0.6):.2f}:d=0.6",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", "30",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)


def make(p, mp4, words, chapters, total, work, n):
    """Returns [(short_mp4, chapter_title)]."""
    os.makedirs(work, exist_ok=True)
    made = []
    for i, (s, e, title) in enumerate(segments(words, chapters, total, n)):
        png = os.path.join(work, f"short{i}.png")
        out = os.path.join(work, f"short{i}.mp4")
        try:
            overlay(p, hook_html(title), work, png)
            cut(mp4, s, e, png, out)
            made.append((out, title))
        except Exception as ex:
            print("short failed", i, ex)
    return made
