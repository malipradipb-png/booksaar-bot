"""Upload the finished video to YouTube and schedule it (needs the channel connected via Telegram /youtube)."""
import hashlib, json, os, re, requests

TOKEN_URL = "https://agr-trend.malipradipb.workers.dev/yt/token"


def clean_tags(tags, limit=450):
    """YouTube rejects the upload ('invalidTags') when tags are too long in total (500 chars, a tag with spaces
    counts 2 extra for quotes) or contain < > characters. Keep only what fits."""
    out, total, seen = [], 0, set()
    for t in tags or []:
        t = re.sub(r'[<>"#,]', " ", str(t))
        t = re.sub(r"\s+", " ", t).strip()
        if not t or len(t) > 60 or t.lower() in seen:
            continue
        cost = len(t) + (2 if " " in t else 0) + 1
        if total + cost > limit:
            break
        out.append(t); seen.add(t.lower()); total += cost
    return out


def enabled():
    return os.environ.get("YT_UPLOAD", "").lower() in ("on", "1", "yes", "true")


def access_token():
    auth = hashlib.sha256(("yt-token:" + os.environ["BOT_TOKEN"]).encode()).hexdigest()[:40]
    r = requests.post(TOKEN_URL, headers={"X-Auth": auth}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube token: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def upload(mp4, title, description, tags, publish_at, thumb=None):
    """publish_at: aware datetime. Returns the video id."""
    tok = access_token()
    h = {"Authorization": f"Bearer {tok}"}
    body = {
        "snippet": {"title": title[:100], "description": description.replace("<", "").replace(">", "")[:4900],
                    "tags": clean_tags(tags),
                    "categoryId": "27", "defaultLanguage": "hi", "defaultAudioLanguage": "hi"},
        "status": {"privacyStatus": "private", "publishAt": publish_at.astimezone().isoformat(),
                   "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    size = os.path.getsize(mp4)
    init = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                         headers={**h, "Content-Type": "application/json; charset=UTF-8",
                                  "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                         data=json.dumps(body), timeout=60)
    if init.status_code == 400 and "invalidTags" in init.text:  # last resort: upload without tags rather than not at all
        print("tags rejected, uploading without tags:", body["snippet"]["tags"])
        body["snippet"]["tags"] = []
        init = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                             headers={**h, "Content-Type": "application/json; charset=UTF-8",
                                      "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                             data=json.dumps(body), timeout=60)
    if not init.ok:
        print("YouTube upload error", init.status_code, init.text[:1500])
    init.raise_for_status()
    loc = init.headers["Location"]
    with open(mp4, "rb") as f:
        r = requests.put(loc, data=f, headers={**h, "Content-Type": "video/mp4", "Content-Length": str(size)}, timeout=3600)
    r.raise_for_status()
    vid = r.json()["id"]
    if thumb:
        try:
            with open(thumb, "rb") as f:
                requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                              headers={**h, "Content-Type": "image/png"}, data=f, timeout=120).raise_for_status()
        except Exception as e:
            print("thumbnail failed", e)
    return vid
