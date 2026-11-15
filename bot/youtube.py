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
    """Preferred: refresh token stored as GitHub secrets (no extra server needed).
    Fallback: the old Cloudflare worker that kept the token (agr-trend)."""
    rt, cid, sec = (os.environ.get(k, "").strip() for k in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"))
    if rt and cid and sec:
        r = requests.post("https://oauth2.googleapis.com/token", timeout=30,
                          data={"client_id": cid, "client_secret": sec, "refresh_token": rt, "grant_type": "refresh_token"})
        if r.status_code != 200:
            raise RuntimeError(f"YouTube token (Google): {r.status_code} {r.text[:300]}")
        return r.json()["access_token"]
    missing = [k for k, v in (("YT_REFRESH_TOKEN", rt), ("YT_CLIENT_ID", cid), ("YT_CLIENT_SECRET", sec)) if not v]
    raise RuntimeError("YouTube secrets missing in GitHub: " + ", ".join(missing) +
                       " (repo Settings > Secrets and variables > Actions). The old agr-trend worker no longer exists.")


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


def scheduled_times():
    """publishAt times of the channel's videos that are still waiting to go public."""
    import datetime
    tok = access_token()
    h = {"Authorization": f"Bearer {tok}"}
    api = "https://www.googleapis.com/youtube/v3/"
    ch = requests.get(api + "channels", params={"part": "contentDetails", "mine": "true"}, headers=h, timeout=60)
    ch.raise_for_status()
    up = ch.json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = requests.get(api + "playlistItems", params={"part": "contentDetails", "playlistId": up, "maxResults": 50},
                         headers=h, timeout=60)
    items.raise_for_status()
    ids = [i["contentDetails"]["videoId"] for i in items.json().get("items", [])]
    if not ids:
        return []
    v = requests.get(api + "videos", params={"part": "status", "id": ",".join(ids)}, headers=h, timeout=60)
    v.raise_for_status()
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    for it in v.json().get("items", []):
        pa = it["status"].get("publishAt")
        if pa:
            t = datetime.datetime.fromisoformat(pa.replace("Z", "+00:00"))
            if t > now:
                out.append(t)
    return out
