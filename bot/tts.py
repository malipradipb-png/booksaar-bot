"""Hindi male voice (Microsoft Madhur) with word timings, tuned to sound calmer and more natural."""
import asyncio, os, re, subprocess

VOICE = os.environ.get("VOICE", "hi-IN-MadhurNeural")
RATE = os.environ.get("VOICE_RATE", "+2%")     # +12% sounded rushed and robotic
PITCH = os.environ.get("VOICE_PITCH", "-2Hz")  # slightly deeper, warmer
# light studio polish: cut rumble, add warmth, gentle compression, broadcast loudness
POLISH = ("highpass=f=80,lowpass=f=11000,"                      # remove rumble and hiss
          "equalizer=f=140:t=q:w=1:g=1.5,"                       # a little body
          "equalizer=f=320:t=q:w=1.2:g=-3,"                      # cut the boxy/muddy range
          "equalizer=f=3800:t=q:w=1.4:g=3.5,"                    # presence: words sound clear
          "equalizer=f=7200:t=q:w=2:g=-2,"                       # soften harsh 's' sounds
          "acompressor=threshold=-21dB:ratio=2.5:attack=6:release=160,"
          "loudnorm=I=-20:TP=-3:LRA=9")   # owner found -15 LUFS too loud


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode().strip())


async def _say(text, path):
    import edge_tts
    try:
        com = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, boundary="WordBoundary")
    except TypeError:
        com = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
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


def pieces(text, limit=700):
    """Split on sentence ends into short paragraphs; a short breath between them sounds more human."""
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
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.8",
                    "-c:a", "libmp3lame", "-b:a", "48k", silence], check=True)
    breath = os.path.join(work, "breath.mp3")  # short pause between paragraphs inside a chapter
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.35",
                    "-c:a", "libmp3lame", "-b:a", "48k", breath], check=True)
    gap, bgap = dur(silence), dur(breath)
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
            files.append(breath)
            t += bgap
        files.append(silence)
        t += gap
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(x)}'\n" for x in files)
    out = os.path.join(work, "voice.m4a")
    raw = os.path.join(work, "voice_raw.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, raw], check=True)
    try:  # polish keeps the same length, so word timings stay in sync
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", POLISH, "-ar", "44100",
                        "-c:a", "aac", "-b:a", "128k", out], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-c:a", "aac", "-b:a", "128k", out], check=True)
    return out, words, chapters
