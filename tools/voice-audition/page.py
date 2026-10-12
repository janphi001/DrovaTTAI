import json, html, sys, pathlib, statistics
sys.stdout.reconfigure(encoding="utf-8")
out = pathlib.Path("out/fish_voices")
meta = json.load(open(out / "meta.json", encoding="utf-8"))
def f0(m):
    a = m["an"]["neutral"]; return a["f0"] if a and a["f0"] else None
rows = []
flags = {}
for m in meta:
    a, z = m["an"]["neutral"], m["an"]["zornig"]
    fl = []
    if not a or not z: fl.append("Analyse fehlt")
    else:
        if a["peak"] > 0.99 or z["peak"] > 0.99: fl.append("Übersteuert")
        if a["dur"] < 4 or a["dur"] > 14: fl.append(f"Dauer {a['dur']:.1f}s auffällig")
        if a["rms_db"] < -32: fl.append("sehr leise")
    flags[m["id"]] = fl
group = lambda m: (m["src"] != "offiziell", m["g"], {"jung": 0, "mittel": 1, "alt": 2}.get(m["a"], 3))
meta.sort(key=lambda m: (group(m), f0(m) or 0))
h = ["<!doctype html><meta charset=utf-8><title>Fish-Stimmen: Auswahl</title><style>body{font:15px system-ui;max-width:980px;margin:20px auto;padding:0 12px;background:#14161a;color:#e6e6e6}"
     "h2{margin:28px 0 6px;border-bottom:1px solid #333}.v{display:grid;grid-template-columns:28px 1fr;gap:6px 10px;padding:10px 0;border-bottom:1px solid #262a31}"
     ".v.ok{background:#16251a}.v.no{opacity:.45}small{color:#9aa}.fl{color:#fb7}audio{height:32px;vertical-align:middle}button{margin:0 4px}textarea{width:100%;height:80px;background:#0e1013;color:#ddd}</style>"
     "<h1>Fish-Stimmen: Auswahl</h1><p>Je Stimme zwei erfundene Testzeilen (neutral, zornig). <b>✔</b> = behalten, <b>✘</b> = raus; Notiz optional. Die Auswahl bleibt im Browser gespeichert; unten „Auswahl anzeigen“ und den Text an Claude schicken.</p>"]
cur = None
for m in meta:
    g = {"m": "männlich", "f": "weiblich"}.get(m["g"], m["g"]); a = m["a"]
    title = "Offizielle Fish-Stimmen (Vergleich)" if m["src"] == "offiziell" else f"Bibliothek: {g}, {a}"
    if title != cur: h.append(f"<h2>{html.escape(title)}</h2>"); cur = title
    n, z = m["an"]["neutral"], m["an"]["zornig"]
    stats = f"F0 {n['f0']:.0f} Hz · {n['dur']:.1f} s · {n['rms_db']:.0f} dBFS" if n and n["f0"] else "–"
    fl = "".join(f" <span class=fl>⚠ {html.escape(x)}</span>" for x in flags[m["id"]])
    sid = m["id"][:8]
    h.append(f"<div class=v id=v{sid} data-id={m['id']} data-name='{html.escape(m['name'])}'><div><button onclick=\"mark('{sid}',1)\">✔</button><br><button onclick=\"mark('{sid}',-1)\">✘</button></div>"
             f"<div><b>{html.escape(m['name'])}</b> <small>{sid} · {g} {a} · {html.escape(', '.join(m['tags']))} · {stats}</small>{fl}<br>"
             f"<audio controls preload=none src='{sid}-neutral.wav'></audio> <audio controls preload=none src='{sid}-zornig.wav'></audio>"
             f"<br><input placeholder='Notiz (z. B. alter Schmied, Händlerin)' style='width:70%' oninput=\"note('{sid}',this.value)\" id=n{sid}></div></div>")
h.append("<h2>Auswahl</h2><button onclick=show()>Auswahl anzeigen</button><textarea id=res></textarea>"
         "<script>const NL=String.fromCharCode(10);const K='fishsel';let S={};try{S=JSON.parse(localStorage[K]||'{}')}catch(e){}"
         "function save(){try{localStorage[K]=JSON.stringify(S)}catch(e){}}"
         "function paint(i){const e=document.getElementById('v'+i);if(!e)return;e.className='v'+(S[i]&&S[i].s>0?' ok':S[i]&&S[i].s<0?' no':'');}"
         "function mark(i,s){S[i]=S[i]||{};S[i].s=S[i].s===s?0:s;save();paint(i)}"
         "function note(i,t){S[i]=S[i]||{};S[i].n=t;save()}"
         "for(const i in S){paint(i);const n=document.getElementById('n'+i);if(n&&S[i].n)n.value=S[i].n}"
         "function show(){const L=[];document.querySelectorAll('.v').forEach(e=>{const i=e.id.slice(1),s=S[i];if(s&&s.s>0)L.push(e.dataset.id+' | '+e.dataset.name+' | '+(s.n||''))});"
         "const R=[];document.querySelectorAll('.v').forEach(e=>{const i=e.id.slice(1),s=S[i];if(s&&s.s<0)R.push(i)});document.getElementById('res').value='BEHALTEN:'+NL+L.join(NL)+NL+'RAUS: '+R.join(' ')}</script>")
open(out / "index.html", "w", encoding="utf-8").write("\n".join(h))
print("Seite:", (out / "index.html").resolve())
fl = {k: v for k, v in flags.items() if v}
print("Auffälligkeiten:", len(fl))
for m in meta:
    if flags[m["id"]]: print(m["id"][:6], m["name"][:24], flags[m["id"]])
import collections
print("F0-Bereiche (Hz) pro Gruppe:")
grp = collections.defaultdict(list)
for m in meta:
    if f0(m): grp[(m["src"], m["g"])].append(round(f0(m)))
for k, v in grp.items(): print(k, sorted(v))
