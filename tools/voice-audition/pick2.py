import json, re, sys, collections, yaml
sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open("out/fish_de_library.json", encoding="utf-8"))
pool = yaml.safe_load(open("casting/fish_voices.yaml", encoding="utf-8"))["voices"]
have = {v["id"] for v in pool.values()}
seen = {m["id"] for m in json.load(open("out/fish_voices/meta.json", encoding="utf-8"))}
BAD_TITLE = re.compile(r"hitler|adolf|drachen|kollegah|kaulitz|paluten|sonic|spongebob|homer|mario|pinkie|morty|jarvis|bernd|bahn|ansager|harnack|grauel|ruff|kaiser|rainer|mcqueen|amy|gojo|zkush|jaxxx|kauer|shurjoka|elon|trump|merkel|merz|scholz|obama|biden|rammstein|lindemann|youtube|nachrichten|synchron|watermark|e girl|egirl|scream|capcut|tiktok|halmich|whistledown|yeager|naruto|goku|vegeta|batman|joker|yoda|vader|gollum|shrek|peppa|bibi|benjamin|pumuckl|mickey|donald|minion|siri|alexa", re.I)
CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]")
def person(t):
    w = re.findall(r"[A-Za-zÄÖÜäöüß]+", t or "")
    return len(w) == 2 and all(x[0].isupper() for x in w) and not any(x.lower() in {"german","deutsch","deutscher","deutsche","female","male","voice","stimme","old","story","father","mother","girl","boy","man","woman"} for x in w)
c = []
for r in rows:
    t = (r["title"] or "").strip(); tags = set(r["tags"] or [])
    if r["_id"] in have or r["_id"] in seen: continue
    if CJK.search(t) or BAD_TITLE.search(t) or person(t) or not t: continue
    if (r["task_count"] or 0) < 60: continue
    g = "m" if "male" in tags else "f" if "female" in tags else "?"
    a = "jung" if "young" in tags else "alt" if "old" in tags else "mittel" if "middle-aged" in tags else "?"
    r["g"], r["a"] = g, a; r["tagset"] = tags; c.append(r)
print(len(c), "übrige Kandidaten")
want = [
 ("Junge Männer", lambda r: r["g"]=="m" and r["a"]=="jung", 7),
 ("Männer rau/tief/dunkel", lambda r: r["g"]=="m" and r["tagset"]&{"raspy","rough","gravelly","gruff","dark","low","husky","gritty"}, 6),
 ("Alte Frauen", lambda r: r["g"]=="f" and r["a"]=="alt", 6),
 ("Frauen tief/rau/dunkel", lambda r: r["g"]=="f" and r["tagset"]&{"raspy","rough","husky","dark","low","deep","gritty"}, 4),
 ("Kinder/Jugendliche", lambda r: r["tagset"]&{"child","kid","teen","boy","girl","childlike","youthful"} or re.search(r"kind|child|boy|girl|junge|mädchen|kid", r["title"], re.I), 4),
 ("Männer hell/hoch", lambda r: r["g"]=="m" and r["tagset"]&{"high","bright","light","nasal"}, 4),
 ("Charakterstimmen (Zwerg/Hexe/Ork o. ä.)", lambda r: r["tagset"]&{"character-voice"} and not r["tagset"]&{"cartoon","anime"}, 6),
]
pick, ids = [], set()
for name, f, q in want:
    k = 0
    for r in sorted((x for x in c if f(x) and x["_id"] not in ids), key=lambda r: -(r["task_count"] or 0)):
        pick.append({k: v for k, v in r.items() if k != "tagset"} | {"gap": name}); ids.add(r["_id"]); k += 1
        if k == q: break
    print(name, "->", k)
json.dump(pick, open("out/fish_candidates2.json", "w", encoding="utf-8"), ensure_ascii=False)
for r in pick: print(r["_id"][:6], r["gap"][:12], "|", r["title"][:28], "|", ",".join((r["tags"] or [])[:5]), "|", r["task_count"])
