"""Write the long Hindi narration, chapter by chapter."""
import re
from llm import chat

STYLE = """You write narration for "Book Saar Hindi", a Hindi audiobook-summary YouTube channel. Rules:
- Write in simple spoken Hindi (Devanagari script), the way a warm, confident Indian narrator talks to one listener. Address the listener as "आप".
- Explain the book's ideas IN YOUR OWN WORDS with fresh Indian examples (office, family, shop, Mumbai local, cricket, exams, small business).
  Never copy sentences from the book. Short quotes of at most one line are allowed, with the author named.
- Short sentences. Every sentence ends with "।", "?" or "!". No lists, no headings, no emojis, no markdown, no English letters
  except the book title and author name. Write numbers as Hindi words. Write English terms in Devanagari (जैसे "सिस्टम", "माइंडसेट").
- Speak naturally: small stories, questions to the listener, "सोचिए", "याद रखिए". It must feel human, not robotic."""


def outline(p):
    data = chat(STYLE, f"""Book: {p['book']} by {p['author']}. Video promise: {p['angle']}
Plan a 45-50 minute Hindi summary video. Return JSON: {{"chapters": [{{"title": "short Hindi chapter title", "points": "2-3 English lines: the key ideas, story or example to cover"}}]}}
Give 9 chapters: the book's most useful ideas in a logical order. Do not include an intro or ending chapter, those are written separately.""",
                as_json=True, max_tokens=2000)
    return data["chapters"][:10]


def clean(t):
    t = re.sub(r"[*#_>`\[\]{}\\|]", " ", t)
    t = re.sub(r"^\s*(\d+[.)]|[-•])\s*", "", t, flags=re.M)
    t = re.sub(r"[ \t]+", " ", t)
    return "\n".join(x.strip() for x in t.splitlines() if x.strip())


def write(p, chapters):
    parts = []
    intro = chat(STYLE, f"""Write the opening (about 350 words) for the video on "{p['book']}" by {p['author']}.
Start with a strong hook: a question or a short relatable story about this problem: {p['angle']}.
Say what the listener will get by the end. Then one line asking them to subscribe to "बुक सार हिंदी" and press the bell.
Do not start with greetings like "नमस्ते दोस्तों".""", max_tokens=1500)
    parts.append(("शुरुआत", clean(intro)))
    for i, ch in enumerate(chapters, 1):
        prev = parts[-1][1][-400:]
        body = chat(STYLE, f"""Book: "{p['book']}" by {p['author']}. This is chapter {i} of {len(chapters)}: "{ch['title']}".
Cover: {ch['points']}
Write about 750 words of narration for this chapter. Begin with a smooth one-line link from the previous part, which ended with:
"...{prev}"
Include one concrete Indian example or story and one practical thing the listener can do today.""", max_tokens=3500)
        parts.append((ch["title"], clean(body)))
    outro = chat(STYLE, f"""Write the ending (about 300 words) for the video on "{p['book']}".
Recap the 3 biggest lessons in story form, give one action for the next 7 days, ask a question for the comments,
and ask them to subscribe to "बुक सार हिंदी" for a new book every day.""", max_tokens=1500)
    parts.append(("आखिरी बात", clean(outro)))
    return parts
