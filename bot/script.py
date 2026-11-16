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
Plan a 12-15 minute Hindi summary video. Return JSON: {{"chapters": [{{"title": "short Hindi chapter title", "points": "2-3 English lines: the key ideas, story or example to cover"}}]}}
Give 6 chapters: only the book's 6 most useful, most surprising ideas in a logical order. Do not include an intro or ending chapter, those are written separately.""",
                as_json=True, max_tokens=2000)
    return data["chapters"][:6]


def clean(t):
    t = re.sub(r"[*#_>`\[\]{}\\|]", " ", t)
    t = re.sub(r"^\s*(\d+[.)]|[-•])\s*", "", t, flags=re.M)
    t = re.sub(r"[ \t]+", " ", t)
    return "\n".join(x.strip() for x in t.splitlines() if x.strip())


def write(p, chapters):
    parts = []
    intro = chat(STYLE, f"""Write the opening (about 150 words, it is spoken in the first 45 seconds) for the video on "{p['book']}" by {p['author']}.
The very first sentence must be a strong hook that makes the listener stay: a bold promise, a surprising fact or a sharp question about this problem: {p['angle']}. No slow build-up.
Within the first three sentences say the book name ("{p['book']}" and "{p.get('book_hi', '')}") and the author's name naturally, because YouTube search reads the spoken words.
Say what the listener will get by the end. Then one line asking them to subscribe to "बुक सार हिंदी" and press the bell.
Do not start with greetings like "नमस्ते दोस्तों".""", max_tokens=1500)
    parts.append(("शुरुआत", clean(intro)))
    for i, ch in enumerate(chapters, 1):
        prev = parts[-1][1][-400:]
        body = chat(STYLE, f"""Book: "{p['book']}" by {p['author']}. This is chapter {i} of {len(chapters)}: "{ch['title']}".
Cover: {ch['points']}
Write about 270 words of narration for this chapter. Begin with a smooth one-line link from the previous part, which ended with:
"...{prev}"
Inside the chapter, in this order: the idea in plain words; one concrete Indian example or small story (make it specific, with a name, a place and numbers);
the most common mistake people make when they try this idea; one practical thing the listener can do today.
Add something the book itself does not say: how this works (or does not work) in Indian conditions — family, jobs, money, culture. Speak it as the channel's own view ("हमारी समझ में", "भारत में अक्सर").""", max_tokens=1500)
        parts.append((ch["title"], clean(body)))
    review = chat(STYLE, f"""Write a short honest review section (about 180 words) for the video on "{p['book']}" by {p['author']}, in the channel's own voice.
Say clearly: what is genuinely strong in this book; one or two weak points (outdated examples, too much repetition, ideas that do not fit Indian life, or claims that are not well proven);
who should read the full book and who can skip it; and how it compares with one other well-known book on the same topic.
Be fair and specific. Do not invent facts about the author or the book; if unsure, speak in general terms.""", max_tokens=1500)
    parts.append(("हमारी राय", clean(review)))
    outro = chat(STYLE, f"""Write the ending (about 150 words) for the video on "{p['book']}".
Recap the 3 biggest lessons in story form, give one action for the next 7 days, ask a question for the comments,
and ask them to subscribe to "बुक सार हिंदी" for a new book every day.""", max_tokens=1500)
    parts.append(("आखिरी बात", clean(outro)))
    return parts
