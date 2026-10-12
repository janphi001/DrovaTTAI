import json, sys, os, wave, struct, math, subprocess, concurrent.futures as cf, importlib.util, html, pathlib
sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(".").resolve()
sys.path.insert(0, str(ROOT / "generator/workers/_common"))
spec = importlib.util.spec_from_file_location("fishworker", ROOT / "generator/workers/fish/worker.py")
fw = importlib.util.module_from_spec(spec); spec.loader.exec_module(fw)
cfg = fw.load()
KEEP = {"c9d13d","179999","578878","cb55f2","37bab8","6761f7","49720e","eb9576"}
cands = [r for r in json.load(open("out/fish_candidates2.json", encoding="utf-8")) if r["_id"][:6] in KEEP]
LINES = {"neutral": "Die Händler am Nordtor sagen, der Winter komme früh in diesem Jahr. Ich traue dem Frieden nicht, aber ein warmes Feuer ist ein warmes Feuer.",
         "zornig": "[angry] Raus aus meinem Haus, und lass dich hier nie wieder blicken!"}
out = pathlib.Path("out/fish_voices2"); out.mkdir(parents=True, exist_ok=True)
old = pathlib.Path("out/fish_voices")
def job(r, kind):
    p = out / f"{r['_id'][:8]}-{kind}.wav"
    if p.exists() and p.stat().st_size > 1000: return
    try: fw.synth(cfg, {"text": LINES[kind], "out_path": str(p), "voice": r["_id"]})
    except Exception as e: print("FEHLER", r["_id"][:6], kind, type(e).__name__, str(e)[:80].replace(cfg["key"], "***"), flush=True)
with cf.ThreadPoolExecutor(3) as ex: list(ex.map(lambda a: job(*a), [(r, k) for r in cands for k in LINES]))
# Varianten: (Basis-ID-Präfix, Name, Tonhöhe gesamt, Formant, Tempo)
VAR = [("9e3f0ea9","Jugendlicher",1.20,1.10,1.00),("7ef3eae2","Knabe",1.30,1.18,1.03),("88b185f9","Mädchen",1.30,1.15,1.03),
       ("87bebc5a","Alte Frau",0.88,0.97,0.92),("b59d1164","Alte Frau rau",0.90,1.00,0.90),("783f5c7c","Riese",0.75,0.85,0.93),
       ("c2342039","Zwerg",0.95,1.12,1.00),("d83fade7","Schurke hell",1.20,1.00,1.00)]
meta0 = {m["id"][:8]: m for m in json.load(open("out/fish_voices/meta.json", encoding="utf-8"))}
variants = []
for base, name, pitch, formant, tempo in VAR:
    vid = f"var-{base}-{name.lower().replace(' ', '-')}"
    for kind in LINES:
        src = old / f"{base}-{kind}.wav"; dst = out / f"{vid}-{kind}.wav"
        sr = 44100
        af = f"asetrate={int(sr*formant)},aresample={sr},rubberband=pitch={pitch/formant:.4f}:tempo={tempo/formant:.4f}:formant=preserved"
        r = subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(src),"-af",af,"-ac","1","-c:a","pcm_s16le",str(dst)],capture_output=True,text=True)
        if r.returncode: print("ffmpeg-Fehler", vid, r.stderr[:200])
    variants.append({"id": vid, "name": f"VARIANTE {name} (aus {meta0[base]['name'][:20]})", "g": meta0[base]["g"], "a": "variante", "tags": [f"Ton x{pitch}", f"Formant x{formant}", f"Tempo x{tempo}"], "src": "Variante", "base": meta0[base]["id"], "recipe": [pitch, formant, tempo]})
def analyse(path):
    try:
        with wave.open(str(path), "rb") as w:
            n, r, ch = w.getnframes(), w.getframerate(), w.getnchannels(); raw = w.readframes(n)
        s = struct.unpack("<%dh" % (len(raw)//2), raw)[::ch]
    except Exception: return None
    if not s: return None
    peak = max(abs(x) for x in s) / 32768; rms = math.sqrt(sum(x*x for x in s) / len(s)) / 32768
    step = max(1, r // 8000); d = s[::step]; sr = r / step; f0s = []
    fl = int(sr * 0.04); hop = int(sr * 0.02); lo, hi = int(sr / 400), int(sr / 60)
    for st in range(0, len(d) - fl - hi, hop):
        fr = d[st:st+fl+hi]; e = sum(x*x for x in fr[:fl])
        if e < (0.01 * 32768) ** 2 * fl: continue
        best, bl = 0, 0
        for lag in range(lo, hi):
            c = sum(fr[i]*fr[i+lag] for i in range(0, fl, 2))
            if c > best: best, bl = c, lag
        if best > 0.45 * e / 2 and bl: f0s.append(sr / bl)
    f0s.sort(); return {"dur": len(s) / r, "peak": peak, "rms_db": 20 * math.log10(rms + 1e-9), "f0": f0s[len(f0s)//2] if f0s else None}
voices = [{"id": r["_id"], "name": r["title"].strip(), "g": r["g"], "a": r["a"], "tags": (r["tags"] or [])[:6], "src": "Bibliothek", "gap": r["gap"]} for r in cands] + variants
for v in voices: v["an"] = {k: analyse(out / f"{v['id'][:8] if v['src']=='Bibliothek' else v['id']}-{k}.wav") for k in LINES}
json.dump(voices, open(out / "meta.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(voices), "Einträge;", sum(1 for v in voices if v["an"]["neutral"]), "analysiert")
for v in voices: print(v["id"][:12], v["name"][:34], "F0", round(v["an"]["neutral"]["f0"]) if v["an"]["neutral"] and v["an"]["neutral"]["f0"] else None, "Dauer", round(v["an"]["neutral"]["dur"],1) if v["an"]["neutral"] else None)
