"""Catch-up: find recent videos (GitHub releases) that never reached YouTube and upload them.
Prints every step and the full YouTube error, so the Actions log shows exactly what went wrong."""
import os, sys, datetime, requests, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youtube, deliver

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
API = "https://www.googleapis.com/youtube/v3/"


def yt_get(tok, path, **params):
    r = requests.get(API + path, params=params, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    if not r.ok:
        print("YouTube API error", path, r.status_code, r.text[:800])
    r.raise_for_status()
    return r.json()


def main():
    tok = youtube.access_token()
    print("token OK")
    ch = yt_get(tok, "channels", part="snippet,contentDetails", mine="true")["items"][0]
    print("channel:", ch["snippet"]["title"])
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt_get(tok, "playlistItems", part="snippet", playlistId=uploads, maxResults=50).get("items", [])
    on_yt = {i["snippet"]["title"].strip() for i in items}
    print("videos on channel:", len(on_yt))

    repo, gh = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    h = {"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"}
    rels = requests.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 6}, headers=h, timeout=60).json()
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
    missing = []
    for rel in rels:  # newest first
        if datetime.datetime.fromisoformat(rel["created_at"].replace("Z", "+00:00")) < cutoff:
            continue
        assets = rel["assets"]
        meta = next((a for a in assets if a["name"].endswith(".txt")), None)
        mp4 = next((a for a in assets if a["name"].endswith(".mp4")), None)
        if not meta or not mp4:
            continue
        txt = requests.get(meta["url"], headers={**h, "Accept": "application/octet-stream"}, timeout=60).text
        title = txt.split("TITLE:\n", 1)[1].split("\n", 1)[0].strip()
        desc = txt.split("DESCRIPTION:\n", 1)[1].split("\n\nTAGS:", 1)[0].strip()
        tags = [t.strip() for t in txt.split("TAGS:\n", 1)[1].split(",") if t.strip()]
        status = "already on YouTube" if title in on_yt else "MISSING"
        print(f"{rel['tag_name']}: {status} | {title}")
        if title not in on_yt:
            missing.append((rel, mp4, next((a for a in assets if a["name"].endswith(".png")), None), title, desc, tags))

    now = datetime.datetime.now(IST)
    for i, (rel, mp4, png, title, desc, tags) in enumerate(missing):
        when = now + datetime.timedelta(minutes=20) + datetime.timedelta(hours=2 * i)
        os.makedirs("work", exist_ok=True)
        fv = os.path.join("work", mp4["name"])
        with requests.get(mp4["url"], headers={**h, "Accept": "application/octet-stream"}, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(fv, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        fp = None
        if png:
            fp = os.path.join("work", png["name"])
            open(fp, "wb").write(requests.get(png["url"], headers={**h, "Accept": "application/octet-stream"}, timeout=120).content)
        print(f"uploading {title} ({os.path.getsize(fv) // 1048576} MB) for {when:%d %b %I:%M %p}")
        try:
            vid = youtube.upload(fv, title, desc, tags, when, fp)
            print("uploaded:", vid)
            deliver.say(f"📺 Chhoota hua video upload ho gaya, {when:%d %b, %I:%M %p} par public hoga:\nhttps://youtu.be/{vid}")
        except requests.HTTPError as e:
            print("UPLOAD FAILED", e.response.status_code, e.response.text[:1500])
            raise
    if not missing:
        print("nothing missing")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
