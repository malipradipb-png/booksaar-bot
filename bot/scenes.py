"""Scene-by-scene video (Audio Books Arc style): a new full-screen picture every ~12 seconds that matches
what the narrator is saying, with a slow zoom, plus the 3D book at the start.

Pictures come from Pexels (PEXELS_KEY, already set). If a POLLINATIONS_KEY secret is added later, AI-made
story pictures are tried first and Pexels is the backup."""
import os, re, subprocess, time, urllib.parse, requests
from llm import chat

SCENE_SEC = float(os.environ.get("SCENE_SEC", "12"))
INTRO_SEC = 8.0
W, H, FPS = 1920, 1080, 24


def split(words, total):
    """Cut the timeline into scenes of about SCENE_SEC, ending on a sentence end when possible.
    Returns [(start, end, text)]."""
    out, start, buf = [], INTRO_SEC, []
    for a, b, w in words:
        if a < INTRO_SEC:
            continue
        buf.append(w)
        long_enough = b - start >= SCENE_SEC
        if (long_enough and re.search(r"[।?!]$", w)) or b - start >= SCENE_SEC * 1.8:
            out.append([start, b, " ".join(buf)])
            start, buf = b, []
    if buf or not out:
        out.append([start, total, " ".join(buf)])
    out[-1][1] = total
    return [tuple(x) for x in out]


def queries(p, scenes):
    """One English stock-photo search + one AI picture prompt per scene, written by the LLM in batches."""
    res = []
    for i in range(0, len(scenes), 30):
        batch = scenes[i:i + 30]
        lines = "\n".join(f"{n}. {t[:260]}" for n, (_, _, t) in enumerate(batch, 1))
        try:
            data = chat("You pick visuals for a Hindi book-summary YouTube video. Reply with JSON only.",
                        f"""Book: "{p['book']}" by {p['author']}.
Below are {len(batch)} narration pieces (Hindi). For EACH piece give a picture that shows what is being said,
like a movie scene: Indian people, real places (office, home, street, shop, classroom, nature), emotions.
Never show text, logos or the book cover. Keep it varied: do not repeat the same scene twice in a row.
Return {{"scenes": [{{"q": "3-5 word English stock photo search, e.g. 'indian man stressed office'",
"ai": "one English sentence describing a cinematic realistic scene with Indian characters"}}]}} with exactly {len(batch)} items in order.

{lines}""", as_json=True, max_tokens=4000, temperature=0.7)
            got = data.get("scenes", [])
        except Exception as e:
            print("scene queries failed", e)
            got = []
        for n in range(len(batch)):
            g = got[n] if n < len(got) and isinstance(got[n], dict) else {}
            res.append((str(g.get("q") or p.get("person_query") or "indian man thinking"),
                        str(g.get("ai") or g.get("q") or "a thoughtful Indian man, cinematic light")))
    return res


class Pics:
    def __init__(self, work):
        self.dir = os.path.join(work, "scenes")
        os.makedirs(self.dir, exist_ok=True)
        self.used, self.cache = set(), {}
        self.pexels_key = os.environ.get("PEXELS_KEY")
        self.ai_key = os.environ.get("POLLINATIONS_KEY")
        self.ai_off = not self.ai_key

    def ai(self, prompt, out, seed):
        if self.ai_off:
            return None
        full = (prompt + ", cinematic realistic digital painting, warm dramatic light, 16:9, no text, no watermark")
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(full)
        for _ in range(3):
            try:
                r = requests.get(url, params={"width": W, "height": H, "nologo": "true", "seed": seed, "model": "flux"},
                                 headers={"Authorization": f"Bearer {self.ai_key}"}, timeout=120)
                if r.ok and r.headers.get("content-type", "").startswith("image") and len(r.content) > 20000:
                    open(out, "wb").write(r.content)
                    return out
                print("ai image", r.status_code, r.text[:150] if not r.ok else "")
                if r.status_code in (401, 402, 403):
                    self.ai_off = True
                    return None
            except Exception as e:
                print("ai image fail", e)
            time.sleep(8)
        return None

    def pexels(self, q, out):
        if not self.pexels_key:
            return None
        try:
            if q not in self.cache:
                r = requests.get("https://api.pexels.com/v1/search", timeout=30, headers={"Authorization": self.pexels_key},
                                 params={"query": q, "orientation": "landscape", "per_page": 15, "size": "large"})
                if r.status_code == 429:
                    time.sleep(30)
                    return None
                self.cache[q] = r.json().get("photos") or []
            for ph in self.cache[q]:
                if ph["id"] in self.used:
                    continue
                self.used.add(ph["id"])
                img = requests.get(ph["src"].get("large2x") or ph["src"]["original"], timeout=60).content
                open(out, "wb").write(img)
                return out
        except Exception as e:
            print("pexels scene fail", q, e)
        return None

    def get(self, i, q, prompt):
        out = os.path.join(self.dir, f"s{i:04d}.jpg")
        return (self.ai(prompt, out, 1000 + i) or self.pexels(q, out)
                or self.pexels(" ".join(q.split()[:2]), out) or self.pexels("indian people", out))


def clip(src, n, out, i, still=False):
    """Fill the screen with the picture for n frames and slowly zoom (direction alternates)."""
    n = max(1, int(n))
    if still:
        vf = f"scale={W}:{H},format=yuv420p"
    else:
        # slow camera pan across a slightly enlarged picture (cheap, smooth); direction changes every scene
        d = n / FPS
        mx, my = ["0", f"(iw-ow)*t/{d:.3f}"], ["0", f"(ih-oh)*t/{d:.3f}"]
        x = [mx[1], f"(iw-ow)*(1-t/{d:.3f})", "(iw-ow)/2", f"(iw-ow)*t/{d:.3f}"][i % 4]
        y = ["(ih-oh)/2", "(ih-oh)/2", my[1], f"(ih-oh)*(1-t/{d:.3f})"][i % 4]
        vf = (f"scale={int(W * 1.12)}:{int(H * 1.12)}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H}:x='{x}':y='{y}',eq=brightness=-0.03:saturation=1.08,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", src, "-vf", vf,
                    "-frames:v", str(n), "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                    "-pix_fmt", "yuv420p", out], check=True)
    return out


def build(p, words, total, book_png, work):
    """Returns a silent MP4 of all scenes (exact length = total). Raises if pictures cannot be found."""
    sc = split(words, total)
    qs = queries(p, sc)
    pics = Pics(work)
    cdir = os.path.join(work, "clips")
    os.makedirs(cdir, exist_ok=True)
    fr = lambda t: int(round(t * FPS))  # frame counts from absolute times, so the picture never drifts from the voice
    clips = [clip(book_png, fr(sc[0][0]), os.path.join(cdir, "c0000.mp4"), 0, still=True)]
    last, found = book_png, 0
    for i, ((a, b, _), (q, prompt)) in enumerate(zip(sc, qs), 1):
        img = pics.get(i, q, prompt)
        if img:
            found += 1
            last = img
        clips.append(clip(img or last, fr(b) - fr(a), os.path.join(cdir, f"c{i:04d}.mp4"), i))
        if i % 20 == 0:
            print(f"scenes {i}/{len(sc)} (pictures found {found})")
    if found < len(sc) * 0.5:
        raise RuntimeError(f"only {found}/{len(sc)} scene pictures found")
    lst = os.path.join(cdir, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    out = os.path.join(work, "scenes.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    first = os.path.join(pics.dir, "s0001.jpg")
    return out, (first if os.path.exists(first) else None)
