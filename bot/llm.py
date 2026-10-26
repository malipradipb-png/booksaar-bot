"""Groq chat helper with model fallback (each Groq model has its own free daily limit)."""
import json, os, re, time, requests

MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "moonshotai/kimi-k2-instruct", "openai/gpt-oss-20b"]
URL = "https://api.groq.com/openai/v1/chat/completions"


def chat(system, user, as_json=False, max_tokens=4000, temperature=0.8):
    key = os.environ["GROQ_KEY"]
    last = None
    for model in MODELS:
        for attempt in range(3):
            body = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            if as_json:
                body["response_format"] = {"type": "json_object"}
            r = requests.post(URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=180)
            if r.status_code == 429:
                last = f"{model}: rate limit"
                wait = float(r.headers.get("retry-after", "0") or 0)
                if 0 < wait <= 60:
                    time.sleep(wait + 1)
                    continue
                break  # daily limit for this model -> next model
            if r.status_code >= 500:
                last = f"{model}: {r.status_code}"
                time.sleep(5)
                continue
            if r.status_code != 200:
                last = f"{model}: {r.status_code} {r.text[:300]}"
                break
            text = r.json()["choices"][0]["message"]["content"] or ""
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
            if not as_json:
                return text
            try:
                return json.loads(text)
            except ValueError:
                m = re.search(r"\{.*\}", text, re.S)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except ValueError:
                        pass
                last = f"{model}: bad JSON"
    raise RuntimeError("Groq failed: " + str(last))
