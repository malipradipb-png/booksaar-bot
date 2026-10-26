"""One run = one finished video. Called twice a day by GitHub Actions."""
import datetime, json, os, re, sys, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deliver, pick, render, script, tts, youtube

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DONE = os.path.join(ROOT, "data", "done.json")
WORK = os.path.join(ROOT, "work")
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
SLOTS = os.environ.get("POST_TIMES", "05:15,18:15").split(",")


def mmss(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def next_slot(now):
    for s in SLOTS:
        hh, mm = map(int, s.split(":"))
        t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if t > now + datetime.timedelta(minutes=30):
            return t
    hh, mm = map(int, SLOTS[0].split(":"))
    return (now + datetime.timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0)


def description(p, chapters):
    stamps = "\n".join(f"{mmss(t)} {title}" for t, title in chapters)
    return (f"{p['angle']}\n\nइस वीडियो में {p['author']} की किताब \"{p['book']}\" ({p['book_hi']}) का पूरा सार आसान हिंदी में।\n\n"
            f"⏱️ Chapters\n{stamps}\n\nरोज़ एक नई किताब के लिए बुक सार हिंदी को सब्सक्राइब करें और बेल आइकन दबाएँ।\n\n"
            f"यह वीडियो किताब का स्वतंत्र सार और समीक्षा है, केवल शिक्षा के उद्देश्य से। मूल किताब ज़रूर पढ़ें।\n\n"
            + " ".join(p.get("hashtags", [])))


def run():
    os.makedirs(WORK, exist_ok=True)
    done = json.load(open(DONE, encoding="utf-8"))
    forced = os.environ.get("FORCE_BOOK", "").strip() or None
    now = datetime.datetime.now(IST)
    when = next_slot(now)

    p = pick.plan(done, forced)
    try:
        p = pick.seo(p)
    except Exception as e:
        print("seo step skipped", e)
    deliver.say(f"🎬 आज की किताब: {p['book']} ({p['author']})\n{p.get('why', '')}\nवीडियो बन रहा है, लगभग 40-60 मिनट लगेंगे।")
    json.dump(p, open(os.path.join(WORK, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    chapters = script.outline(p)
    parts = script.write(p, chapters)
    full = "\n\n".join(f"[{t}]\n{x}" for t, x in parts)
    open(os.path.join(WORK, "script.txt"), "w", encoding="utf-8").write(full)
    words_n = sum(len(x.split()) for _, x in parts)

    audio, words, chaps = tts.narrate(parts, os.path.join(WORK, "audio"))
    name = f"{now:%Y-%m-%d}-{slug(p['book'])}"
    mp4 = os.path.join(WORK, name + ".mp4")
    render.video(p, audio, words, WORK, mp4)

    photo = deliver.pexels(p.get("person_query", "thinking indian man"), os.path.join(WORK, "person.jpg"))
    thumbs = render.thumbnails(p, WORK, photo)

    desc = description(p, chaps)
    meta = os.path.join(WORK, name + ".txt")
    open(meta, "w", encoding="utf-8").write(f"TITLE:\n{p['title']}\n\nDESCRIPTION:\n{desc}\n\nTAGS:\n{', '.join(p['tags'])}\n")
    links = deliver.release(name, f"{p['book']} — {when:%d %b %I:%M %p}", [mp4] + thumbs + [meta], body=p["title"])

    length = mmss(tts.dur(audio))
    deliver.say(f"✅ वीडियो तैयार: {p['book']}\nलंबाई: {length} | शब्द: {words_n}\n"
                f"पोस्ट करें: {when:%d %b, %I:%M %p}\n\n📥 वीडियो डाउनलोड:\n{links[os.path.basename(mp4)]}")
    for i, t in enumerate(thumbs):
        deliver.photo(t, f"थंबनेल {'AB'[i]}")
    deliver.say(f"TITLE:\n{p['title']}")
    deliver.say(f"DESCRIPTION:\n{desc}")
    deliver.say(f"TAGS:\n{', '.join(p['tags'])}")

    if youtube.enabled():
        try:
            vid = youtube.upload(mp4, p["title"], desc, p["tags"], when, thumbs[0])
            deliver.say(f"📺 YouTube par upload ho gaya aur {when:%d %b, %I:%M %p} par apne aap public hoga:\nhttps://youtu.be/{vid}")
        except Exception as e:
            deliver.say(f"⚠️ YouTube upload nahi hua ({str(e)[:300]}). Upar ke link se khud upload kar dein.")

    done.append(p["book"])
    json.dump(done, open(DONE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        err = traceback.format_exc()
        print(err)
        deliver.say("❌ आज का वीडियो नहीं बन पाया। अगली बार अपने आप फिर कोशिश होगी।\n\n" + err[-1500:])
        sys.exit(1)
