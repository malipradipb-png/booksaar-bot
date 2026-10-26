"""Pexels photo, GitHub release upload, Telegram messages."""
import os, requests

TG = "https://api.telegram.org/bot{}/{}"


def tg(method, data=None, files=None):
    tok, chat = os.environ.get("BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not tok or not chat:
        print("telegram not configured:", method, (data or {}).get("text", "")[:200])
        return None
    d = {"chat_id": chat, **(data or {})}
    r = requests.post(TG.format(tok, method), data=d, files=files, timeout=120)
    if not r.ok:
        print("telegram error", r.status_code, r.text[:300])
    return r


def say(text):
    for i in range(0, len(text), 3900):
        tg("sendMessage", {"text": text[i:i + 3900], "disable_web_page_preview": "true"})


def photo(path, caption=""):
    with open(path, "rb") as f:
        tg("sendPhoto", {"caption": caption[:1000]}, {"photo": f})


def document(path, caption=""):
    with open(path, "rb") as f:
        tg("sendDocument", {"caption": caption[:1000]}, {"document": f})


def pexels(query, out):
    key = os.environ.get("PEXELS_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", params={"query": query, "orientation": "portrait", "per_page": 10},
                         headers={"Authorization": key}, timeout=30).json()
        ph = r.get("photos") or []
        if not ph:
            return None
        url = ph[0]["src"]["large"]
        open(out, "wb").write(requests.get(url, timeout=60).content)
        return out
    except Exception as e:
        print("pexels fail", e)
        return None


def release(tag, name, files, body=""):
    """Attach the files to a GitHub release of this repo; returns {filename: download_url}."""
    repo, tok = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    r = requests.post(f"https://api.github.com/repos/{repo}/releases", headers=h,
                      json={"tag_name": tag, "name": name, "body": body[:20000]}, timeout=60)
    r.raise_for_status()
    up = r.json()["upload_url"].split("{")[0]
    links = {}
    for path in files:
        fn = os.path.basename(path)
        ctype = "video/mp4" if fn.endswith(".mp4") else "image/png" if fn.endswith(".png") else "text/plain"
        with open(path, "rb") as f:
            a = requests.post(up, params={"name": fn}, data=f, timeout=1800,
                              headers={**h, "Content-Type": ctype})
        a.raise_for_status()
        links[fn] = a.json()["browser_download_url"]
    return links
