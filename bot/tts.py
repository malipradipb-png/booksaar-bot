"""Hindi male voice (Microsoft Madhur) with word timings."""
import asyncio, os, re, subprocess

VOICE = os.environ.get("VOICE", "hi-IN-MadhurNeural")
RATE = os.environ.get("VOICE_RATE", "+12%")


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode().strip())


async def _say(text, path):
    import edge_tts
    try:
        com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
    except TypeError:
        com = edge_tts.Communicate(text, VOICE, rate=RATE)
    words = []
    with open(path, "wb") as f:
        async for c in com.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                words.append((c["offset"] / 1e7, (c["offset"] + c["duration"]) / 1e7, c["text"]))
    return words


def say(text, path):
    last = None
    for _ in range(4):
        try:
            w = asyncio.run(_say(text, path))
            if w and os.path.getsize(path) > 1000:
                return w
            last = "no audio"
        except Exception as e:
            last = e
    raise RuntimeError(f"TTS failed: {last}")


def pieces(text, limit=1800):
    """Split on sentence ends so each TTS request stays small."""
    sents = re.split(r"(?<=[।?!])\s+", text.replace("\n", " "))
    out, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > limit and cur:
            out.append(cur.strip()); cur = ""
        cur += " " + s
    if cur.strip():
        out.append(cur.strip())
    return out


def narrate(parts, work):
    """Returns (audio_path, words[(start,end,text)], chapters[(start,title)])."""
    os.makedirs(work, exist_ok=True)
    silence = os.path.join(work, "gap.mp3")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.7",
                    "-c:a", "libmp3lame", "-b:a", "48k", silence], check=True)
    gap = dur(silence)
    files, words, chapters, t = [], [], [], 0.0
    n = 0
    for title, text in parts:
        chapters.append((t, title))
        for piece in pieces(text):
            n += 1
            p = os.path.join(work, f"p{n:03d}.mp3")
            w = say(piece, p)
            words += [(a + t, b + t, x) for a, b, x in w]
            files.append(p)
            t += dur(p)
        files.append(silence)
        t += gap
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(x)}'\n" for x in files)
    out = os.path.join(work, "voice.m4a")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:a", "aac", "-b:a", "96k", out], check=True)
    return out, words, chapters
