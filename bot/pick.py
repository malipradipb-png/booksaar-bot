"""Pick today's book from market signals and plan the whole video package."""
import json, re, requests
from llm import chat

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Accept-Language": "en-IN,en;q=0.9"}

AMAZON = ["https://www.amazon.in/gp/bestsellers/books/1318158031",   # self-help
          "https://www.amazon.in/gp/bestsellers/books/1318068031",   # business & economics
          "https://www.amazon.in/gp/bestsellers/books/1318073031"]   # health, family, personal dev
CHANNELS = ["@AudiobooksArc", "@BookSummaryClub", "@BookPointHindi"]


def amazon_titles():
    out = []
    for u in AMAZON:
        try:
            h = requests.get(u, headers=UA, timeout=25).text
            for alt in re.findall(r'<img alt="([^"]{4,140})" src="https://images-[^"]+"', h):
                alt = re.sub(r"\s+", " ", alt).strip()
                if alt not in out:
                    out.append(alt)
        except Exception as e:
            print("amazon fail", u, e)
    return out[:60]


def channel_hits():
    """Recent titles + views from competing Hindi book-summary channels."""
    rows = []
    for ch in CHANNELS:
        try:
            h = requests.get(f"https://www.youtube.com/{ch}/videos", headers=UA, timeout=25).text
            for m in re.finditer(r'"lockupViewModel".{0,4000}?"content":"([^"]{8,200})".{0,600}?"content":"([\d.,]+[KkMmLl]?) ?(?:views)?"', h):
                rows.append(f"{m.group(1)} — {m.group(2)} views")
        except Exception as e:
            print("yt fail", ch, e)
    return rows[:60]


SYSTEM = """You are the content head of the Hindi YouTube channel "Book Saar Hindi" (बुक सार हिंदी), which posts long
(45-55 minute) Hindi book summaries in the style of the channel Audio Books Arc: one screen with the book on the left,
big Hindi captions on the right, a clear Indian male Hindi voice. Your job is to pick ONE book that will get the most
views today and plan its package. Reply with JSON only."""


def plan(done, forced=None):
    amz = amazon_titles()
    hits = channel_hits()
    user = f"""Books already made on this channel (never repeat these or close variants):
{json.dumps(done, ensure_ascii=False)}

Amazon India bestsellers right now (self-help / business / personal development):
{json.dumps(amz, ensure_ascii=False)}

Recent videos on competing Hindi book-summary channels with their views (high views = hot topic):
{json.dumps(hits, ensure_ascii=False)}

{"The owner has asked for this book: " + forced if forced else "Choose the single best book for today: a real, well-known non-fiction book (self-help, psychology, money, habits, communication, mindset) that Indian viewers are searching for now. Prefer topics that are getting high views on competing channels, but pick a book that is not already on our list."}

Return JSON with exactly these keys:
{{
 "book": "English book title", "author": "author name", "book_hi": "book title in Hindi script",
 "angle": "the emotional promise of the video in one Hindi line",
 "title": "YouTube title, under 95 characters: Hindi hook first, then '| <Book> Book Summary in Hindi | <Author>'",
 "tags": ["15 to 20 search tags, mixed Hindi and English"],
 "hashtags": ["#BookSummary", "3 more"],
 "cover_tag": "2-4 word Hindi tagline printed on top of the book",
 "cover_sub": "4-7 word Hindi subtitle printed on the book",
 "theme": {{"bg1": "dark hex for the screen background, matching the mood of this book", "bg2": "lighter hex for the glow behind the captions",
   "cover1": "light hex for the book cover", "cover2": "slightly darker hex for the cover gradient", "ink": "dark hex for text on the cover",
   "hi": "bright hex used to highlight the spoken word (green like #3CE36A unless the background is green, then yellow)",
   "dust": "r,g,b of the floating light particles", "thumb_bg": "a CSS linear-gradient for the thumbnail background"}},
 "thumb_a": ["line 1 (2-3 Hindi words)", "line 2: ONE punchy word or number to put in a yellow box", "line 3 (2-3 Hindi words)"],
 "thumb_b": ["line 1 (2-3 Hindi words)", "line 2: 1-2 words in a red brush stroke", "line 3 (2-3 Hindi words)"],
 "person_query": "English Pexels search for a real person photo with a strong emotion that fits the hook, e.g. 'shocked indian man'",
 "why": "one Hindi line: why this book will do well today"
}}"""
    return fix(chat(SYSTEM, user, as_json=True, max_tokens=2500, temperature=0.9))


DEFAULT_THEME = {"bg1": "#121A24", "bg2": "#2B4A63", "cover1": "#F7F2E8", "cover2": "#E9DFCC", "ink": "#1E2B38",
                 "hi": "#3CE36A", "dust": "255,214,140", "thumb_bg": ""}


def _hex(v, d):
    v = str(v or "").strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", v):
        return "#" + v.lstrip("#")
    return d


def fix(p):
    """Make the AI's plan safe to use whatever shape it came back in."""
    t = p.get("theme") if isinstance(p.get("theme"), dict) else {}
    th = {}
    for k in ("bg1", "bg2", "cover1", "cover2", "ink", "hi"):
        th[k] = _hex(t.get(k), DEFAULT_THEME[k])
    dust = t.get("dust", DEFAULT_THEME["dust"])
    nums = re.findall(r"\d+", ",".join(map(str, dust)) if isinstance(dust, (list, tuple)) else str(dust))
    th["dust"] = ",".join(str(min(255, int(x))) for x in nums[:3]) if len(nums) >= 3 else DEFAULT_THEME["dust"]
    tb = str(t.get("thumb_bg") or "")
    th["thumb_bg"] = tb if tb.startswith(("linear-gradient", "radial-gradient", "#")) and "<" not in tb and ";" not in tb else ""
    p["theme"] = th
    for k, dflt in (("thumb_a", ["रोज़ सुनें", "1 किताब", "बदल देगी"]), ("thumb_b", ["ये किताब", "ज़िंदगी", "बदल देगी"])):
        v = p.get(k)
        v = [str(x) for x in v] if isinstance(v, list) else [str(v or "")]
        p[k] = v[:3] if len(v) >= 3 else (v + ["", "", ""])[:3] if v and v[0] else dflt
    for k in ("tags", "hashtags"):
        v = p.get(k)
        p[k] = [str(x) for x in v] if isinstance(v, list) else [x.strip() for x in str(v or "").split(",") if x.strip()]
    for k in ("book", "author", "title"):
        if not p.get(k):
            raise RuntimeError("AI plan missing " + k)
    p.setdefault("book_hi", p["book"]); p.setdefault("angle", ""); p.setdefault("cover_tag", ""); p.setdefault("cover_sub", "")
    return p
