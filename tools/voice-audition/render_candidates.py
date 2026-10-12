import json, sys, os, wave, struct, math, concurrent.futures as cf, importlib.util, html, pathlib
sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(".").resolve()
spec = importlib.util.spec_from_file_location("fishworker", ROOT / "generator/workers/fish/worker.py")
sys.path.insert(0, str(ROOT / "generator/workers/_common"))
fw = importlib.util.module_from_spec(spec); spec.loader.exec_module(fw)
cfg = fw.load()
DROP = {"86e338","3c60d4","13e1a9","5d5738","b229b5","16fa98","76fe19","397829","daa4eb","5875c5"}
cands = [r for r in json.load(open("out/fish_candidates.json", encoding="utf-8")) if r["_id"][:6] not in DROP]
import yaml
official = yaml.safe_load(open("casting/fish_voices.yaml", encoding="utf-8"))["voices"]
voices = [{"id": v["id"], "name": "OFFIZIELL " + v["label"], "g": v["gender"], "a": "-", "tags": ["official", v["region"]], "src": "offiziell"} for v in official.values()]
voices += [{"id": r["_id"], "name": r["title"].strip(), "g": r["g"], "a": r["a"], "tags": (r["tags"] or [])[:6], "src": "Bibliothek"} for r in cands]
LINES = {
  "neutral": "Die Händler am Nordtor sagen, der Winter komme früh in diesem Jahr. Ich traue dem Frieden nicht, aber ein warmes Feuer ist ein warmes Feuer.",
  "zornig": "[angry] Raus aus meinem Haus, und lass dich hier nie wieder blicken!",
}
out = pathlib.Path("out/fish_voices"); out.mkdir(parents=True, exist_ok=True)
def job(v, kind):
    p = out / f"{v['id'][:8]}-{kind}.wav"
    if p.exists() and p.stat().st_size > 1000: return v["id"], kind, "cache", None
    try:
        rate, dur = fw.synth(cfg, {"text": LINES[kind], "out_path": str(p), "voice": v["id"]})
        return v["id"], kind, "ok", dur
    except Exception as e:
        return v["id"], kind, "FEHLER " + type(e).__name__ + ": " + str(e)[:80].replace(cfg["key"], "***"), None
res = {}
with cf.ThreadPoolExecutor(3) as ex:
    futs = [ex.submit(job, v, k) for v in voices for k in LINES]
    for i, f in enumerate(cf.as_completed(futs)):
        vid, kind, st, dur = f.result(); res[(vid, kind)] = st
        if st.startswith("FEHLER"): print(vid[:6], kind, st, flush=True)
        if (i + 1) % 20 == 0: print("fertig", i + 1, "von", len(futs), flush=True)
def analyse(path):
    try:
        with wave.open(str(path), "rb") as w:
            n, r, ch = w.getnframes(), w.getframerate(), w.getnchannels(); raw = w.readframes(n)
        s = struct.unpack("<%dh" % (len(raw)//2), raw)[::ch]
    except Exception: return None
    if not s: return None
    peak = max(abs(x) for x in s) / 32768; rms = math.sqrt(sum(x*x for x in s) / len(s)) / 32768
    # F0 per Frame (Autokorrelation, 60-400 Hz) auf 8 kHz heruntergetastet
    step = max(1, r // 8000); d = s[::step]; sr = r / step; f0s = []
    fl = int(sr * 0.04); hop = int(sr * 0.02)
    lo, hi = int(sr / 400), int(sr / 60)
    for st in range(0, len(d) - fl - hi, hop):
        fr = d[st:st+fl+hi]
        e = sum(x*x for x in fr[:fl])
        if e < (0.01 * 32768) ** 2 * fl: continue
        best, bl = 0, 0
        for lag in range(lo, hi):
            c = sum(fr[i]*fr[i+lag] for i in range(0, fl, 2))
            if c > best: best, bl = c, lag
        if best > 0.45 * e / 2 * 1.0 and bl: f0s.append(sr / bl)
    f0s.sort(); f0 = f0s[len(f0s)//2] if f0s else None
    return {"dur": len(s) / r, "peak": peak, "rms_db": 20 * math.log10(rms + 1e-9), "f0": f0}
meta = []
for v in voices:
    a = {k: analyse(out / f"{v['id'][:8]}-{k}.wav") for k in LINES}
    meta.append({**v, "an": a, "st": {k: res.get((v["id"], k)) for k in LINES}})
json.dump(meta, open(out / "meta.json", "w", encoding="utf-8"), ensure_ascii=False)
print("Analyse fertig,", sum(1 for m in meta if m["an"]["neutral"]), "von", len(meta), "neutral analysierbar")
