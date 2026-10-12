import json, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open("out/fish_de_library.json", encoding="utf-8"))
BAD_TAGS = {"character-voice","entertainment","social-media","advertisement","announcer","game","anime","cartoon"}
GOOD_TAGS = {"narration","conversational","storytelling","educational","professional","calm","soft","warm","documentary","podcast","audiobook","serious","smooth"}
BAD_TITLE = re.compile(r"hitler|adolf|drachen|kollegah|kaulitz|paluten|sonic|spongebob|homer|mario|pinkie|morty|jarvis|bernd|bahn|ansager|harnack|grauel|ruff|kaiser|rainer|mcqueen|amy|gojo|zkush|jaxxx|kauer|shurjoka|elon|trump|merkel|scholz|obama|biden|rammstein|lindemann|youtube|nachrichten|sprecher|synchron|watermark|e girl|egirl|mädchen|scream", re.I)
CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff]")
def looks_like_person(t):
    w = re.findall(r"[A-Za-zÄÖÜäöüß]+", t or "")
    return len(w) == 2 and all(x[0].isupper() for x in w) and not any(x.lower() in {"german","deutsch","deutscher","deutsche","female","male","voice","stimme","vorlesen","christa","wisdom","father","mother"} for x in w)
cand = []
for r in rows:
    tags = set(r["tags"] or []); t = r["title"] or ""
    if tags & BAD_TAGS or not (tags & GOOD_TAGS): continue
    if CJK.search(t) or BAD_TITLE.search(t) or looks_like_person(t): continue
    if (r["task_count"] or 0) < 150 or (r["like_count"] or 0) < 2: continue
    g = "m" if "male" in tags else "f" if "female" in tags else None
    a = "jung" if "young" in tags else "alt" if "old" in tags else "mittel" if "middle-aged" in tags else None
    if not g or not a: continue
    r["g"], r["a"] = g, a
    cand.append(r)
print(len(cand), "Kandidaten nach Filter")
by = collections.defaultdict(list)
for r in cand: by[(r["g"], r["a"])].append(r)
# pro Gruppe die nach Nutzung besten, dabei Klangfarben-Tags streuen
pick = []
quota = {("m","jung"):6, ("m","mittel"):9, ("m","alt"):9, ("f","jung"):8, ("f","mittel"):8, ("f","alt"):6}
for k, q in quota.items():
    seen_style = collections.Counter(); chosen = []
    for r in sorted(by[k], key=lambda r: -(r["task_count"] or 0)):
        style = tuple(sorted(set(r["tags"] or []) & {"deep","soft","warm","bright","dark","calm","energetic","serious","smooth","breathy","low","high"}))[:2]
        if seen_style[style] >= 2: continue
        seen_style[style] += 1; chosen.append(r)
        if len(chosen) == q: break
    pick += chosen
    print(k, len(by[k]), "->", len(chosen))
json.dump(pick, open("out/fish_candidates.json", "w", encoding="utf-8"), ensure_ascii=False)
for r in pick: print(r["_id"][:6], r["g"], r["a"], "|", (r["title"] or "")[:28], "|", ",".join((r["tags"] or [])[:5]), "|", r["task_count"])
