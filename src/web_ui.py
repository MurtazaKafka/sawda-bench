"""Local web UI for the two human tasks: seed-item entry and Gate A validation.

Stdlib only. Serves one page on :8017 with two tabs:
  1. Seeds — situation-prompt cards + a form; saves to drafts/tranche1_seed.jsonl
  2. Validate — one item at a time from items/items.jsonl, inline edits,
     approve/reject/lang_code, saved to disk on every action.

Run: python src/web_ui.py
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "drafts" / "tranche1_seed.jsonl"
ITEMS = ROOT / "items" / "items.jsonl"
RESULTS = ROOT / "results"
PLAN = RESULTS / "judging_plan.json"
TRANSLATIONS = RESULTS / "translations.jsonl"
JUDGMENTS = RESULTS / "human_judgments.jsonl"
PORT = int(os.environ.get("PORT", 8017))


def read_jsonl(path):
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def upsert(path, item):
    rows = read_jsonl(path)
    for i, r in enumerate(rows):
        if r["id"] == item["id"]:
            rows[i] = item
            break
    else:
        rows.append(item)
    write_jsonl(path, rows)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(PAGE.encode(), "text/html")
        elif self.path == "/api/state":
            self._send({"seeds": read_jsonl(SEEDS),
                        "items": read_jsonl(ITEMS)})
        elif self.path == "/api/judge/state":
            self._send(judge_state())
        else:
            self.send_error(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n)) if n else {}
        if self.path == "/api/seed/save":
            item = payload["item"]
            if not item.get("id"):
                used = {r["id"] for r in read_jsonl(SEEDS)}
                k = 1
                while f"seed-{k:02d}" in used:
                    k += 1
                item["id"] = f"seed-{k:02d}"
            item.setdefault("tranche", "seed")
            item.setdefault("validated", False)
            item.setdefault("validator_note", "")
            upsert(SEEDS, item)
            self._send({"ok": True, "id": item["id"]})
        elif self.path == "/api/seed/delete":
            rows = [r for r in read_jsonl(SEEDS) if r["id"] != payload["id"]]
            write_jsonl(SEEDS, rows)
            self._send({"ok": True})
        elif self.path == "/api/item/update":
            upsert(ITEMS, payload["item"])
            self._send({"ok": True})
        elif self.path == "/api/judge/save":
            self._send(judge_save(payload))
        else:
            self.send_error(404)


def judge_state():
    """Judging plan + next blind pair. System identity never leaves here."""
    if not TRANSLATIONS.exists():
        return {"total": 0, "done": 0, "next": None,
                "msg": "No translations yet — Phase 3 must finish first."}
    if not PLAN.exists():
        import judge_ui
        from config import SYSTEMS
        have = {r["system"] for r in read_jsonl(TRANSLATIONS)}
        if have != set(SYSTEMS):
            return {"total": 0, "done": 0, "next": None,
                    "msg": "Phase 3 still running — waiting on: " +
                           ", ".join(sorted(set(SYSTEMS) - have))}
        judge_ui.build_plan()
    order = [tuple(p) for p in json.loads(PLAN.read_text())["order"]]
    done = {(r["item_id"], r["system"]) for r in read_jsonl(JUDGMENTS)}
    items = {it["id"]: it for it in read_jsonl(ITEMS)}
    trans = {(r["item_id"], r["system"]): r for r in read_jsonl(TRANSLATIONS)}
    nxt = None
    for idx, pair in enumerate(order):
        if pair not in done:
            it = items[pair[0]]
            nxt = {"idx": idx, "direction": it["direction"],
                   "source": it["utterance_src"], "context": it["context"],
                   "candidate": trans[pair]["output"]}
            break
    return {"total": len(order), "done": len(done), "next": nxt}


def judge_save(payload):
    order = [tuple(p) for p in json.loads(PLAN.read_text())["order"]]
    item_id, system = order[payload["idx"]]
    done = {(r["item_id"], r["system"]) for r in read_jsonl(JUDGMENTS)}
    if (item_id, system) in done:
        return {"ok": False, "err": "already judged"}
    rec = {"item_id": item_id, "system": system,
           "intent": int(payload["intent"]),
           "appropriateness": int(payload["appropriateness"]),
           "note": payload.get("note", "").strip(),
           "flags": payload.get("flags", []), "judge": "human"}
    JUDGMENTS.parent.mkdir(exist_ok=True)
    with JUDGMENTS.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True}


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sawda — item studio</title>
<style>
:root{
  --bg:#f6f3ee; --card:#fffdf9; --ink:#26221c; --mut:#8a8172;
  --line:#e4ddd0; --acc:#8c4a2f; --acc2:#3d5a48; --bad:#a03535;
  --chip:#efe9de; --ok:#3d5a48;
  font-size:15px;
}
*{box-sizing:border-box}
body{margin:0;font-family:ui-sans-serif,-apple-system,"Segoe UI",sans-serif;
  background:var(--bg);color:var(--ink)}
header{display:flex;align-items:baseline;gap:16px;padding:14px 22px;
  border-bottom:1px solid var(--line);background:var(--card)}
header h1{font-size:1.05rem;margin:0;letter-spacing:.02em}
header .sub{color:var(--mut);font-size:.85rem}
nav{margin-left:auto;display:flex;gap:6px}
nav button{border:1px solid var(--line);background:var(--chip);padding:7px 14px;
  border-radius:20px;cursor:pointer;font:inherit;color:var(--ink)}
nav button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
main{max-width:1200px;margin:0 auto;padding:18px 22px}
.progress{display:flex;align-items:center;gap:10px;margin:4px 0 16px;
  color:var(--mut);font-size:.9rem}
.bar{flex:1;height:6px;background:var(--chip);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--acc2);transition:width .3s}
.cols{display:grid;grid-template-columns:330px 1fr;gap:20px}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
.prompts{display:flex;flex-direction:column;gap:8px;max-height:78vh;
  overflow-y:auto;padding-right:4px}
.pcard{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:10px 12px;cursor:pointer;transition:border-color .15s}
.pcard:hover{border-color:var(--acc)}
.pcard.sel{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}
.pcard b{display:block;font-size:.92rem}
.pcard span{color:var(--mut);font-size:.82rem;line-height:1.35;display:block;
  margin-top:3px}
.pcard .tag{display:inline-block;margin-top:6px;font-size:.7rem;
  background:var(--chip);border-radius:8px;padding:2px 8px;color:var(--acc)}
form,.vcard{background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:18px 20px}
label{display:block;font-size:.78rem;color:var(--mut);margin:12px 0 4px;
  text-transform:uppercase;letter-spacing:.06em}
input,textarea,select{width:100%;font:inherit;color:var(--ink);
  background:#fff;border:1px solid var(--line);border-radius:8px;
  padding:8px 10px}
textarea{resize:vertical;min-height:54px}
textarea.fa{direction:rtl;font-size:1.1rem;line-height:1.8}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.hint{background:#f4efe4;border:1px dashed var(--line);border-radius:8px;
  padding:10px 12px;font-size:.88rem;color:#5c5344;margin-bottom:6px}
.btns{display:flex;gap:10px;margin-top:16px;align-items:center}
button.primary{background:var(--acc);color:#fff;border:none;padding:9px 20px;
  border-radius:8px;font:inherit;cursor:pointer}
button.ok{background:var(--ok);color:#fff;border:none;padding:9px 20px;
  border-radius:8px;font:inherit;cursor:pointer}
button.warn{background:none;border:1px solid var(--bad);color:var(--bad);
  padding:9px 16px;border-radius:8px;font:inherit;cursor:pointer}
button.ghost{background:none;border:1px solid var(--line);color:var(--ink);
  padding:9px 14px;border-radius:8px;font:inherit;cursor:pointer}
.saved{margin-top:20px}
.srow{display:flex;gap:10px;align-items:center;background:var(--card);
  border:1px solid var(--line);border-radius:8px;padding:8px 12px;
  margin-bottom:6px;font-size:.9rem}
.srow .fa{direction:rtl;flex:1;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.srow small{color:var(--mut)}
.srow button{border:none;background:none;color:var(--acc);cursor:pointer}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;font-size:.78rem}
.meta span{background:var(--chip);padding:3px 10px;border-radius:9px;
  color:#6b6252}
.toast{position:fixed;bottom:18px;right:18px;background:var(--ink);color:#fff;
  padding:10px 16px;border-radius:8px;opacity:0;transition:opacity .3s;
  font-size:.9rem;pointer-events:none}
.toast.show{opacity:.94}
.navrow{display:flex;gap:8px;align-items:center;margin-bottom:12px}
.navrow .spacer{flex:1}
.pill{font-size:.78rem;padding:3px 10px;border-radius:9px}
.pill.v{background:#e4ecd9;color:var(--ok)} .pill.r{background:#f3dede;color:var(--bad)}
.pill.p{background:var(--chip);color:var(--mut)}
kbd{background:var(--chip);border-radius:4px;padding:1px 6px;font-size:.75rem}
.keys{color:var(--mut);font-size:.8rem;margin-top:10px}
</style>
</head>
<body>
<header>
  <h1>Sawda · item studio</h1>
  <span class="sub">immediate-feedback loop for the human-in-the-loop</span>
  <nav>
    <button id="tab-seed" class="on" onclick="show('seed')">1 · Seed items</button>
    <button id="tab-val" onclick="show('val')">2 · Validate (Gate A)</button>
    <button id="tab-judge" onclick="show('judge')">3 · Judge (Gate B)</button>
  </nav>
</header>
<main>
  <section id="seed">
    <div class="progress"><span id="seedcount"></span>
      <div class="bar"><i id="seedbar"></i></div><span>goal 8–12</span></div>
    <div class="cols">
      <div class="prompts" id="prompts"></div>
      <div>
        <form id="f" onsubmit="saveSeed(event)">
          <div class="hint" id="hint">Pick a situation card on the left, or just start typing.
            Rough is fine — everything is editable at Gate A.</div>
          <div class="row3">
            <div><label>direction</label>
              <select id="direction" onchange="dirs()">
                <option value="fa2en">fa2en (Dari/Farsi → English)</option>
                <option value="en2fa">en2fa (English → Dari/Farsi)</option>
              </select></div>
            <div><label>failure class</label>
              <select id="failure_class">
                <option>ritual_refusal_literal</option>
                <option>intent_inversion</option>
                <option>indirect_refusal_as_assent</option>
                <option>obligation_face_deleted</option>
                <option>register_violation</option>
              </select></div>
            <div><label>register</label>
              <select id="lang_code">
                <option value="prs_Arab">Dari (prs_Arab)</option>
                <option value="pes_Arab">Farsi (pes_Arab)</option>
              </select></div>
          </div>
          <label>utterance (source language)</label>
          <textarea id="utterance_src" class="fa" required
            placeholder="عین کلماتی که گفته می‌شود…"></textarea>
          <label>context — who is speaking to whom, relationship, live situation (1–2 sentences)</label>
          <textarea id="context" required placeholder="Speaker … Listener … Situation …"></textarea>
          <div class="row">
            <div><label>literal render (what a flat translation says)</label>
              <textarea id="literal_render" required></textarea></div>
            <div><label>intent render (what should land for the reader)</label>
              <textarea id="intent_render" required></textarea></div>
          </div>
          <label>pragmatic note — what is at risk, one sentence</label>
          <input id="pragmatic_note" required
            placeholder="If read literally, …">
          <label>phenomenon (optional name, e.g. taarof re-offer, namak-gir)</label>
          <input id="phenomenon">
          <div class="btns">
            <button class="primary" type="submit" id="savebtn">Save seed</button>
            <button class="ghost" type="button" onclick="clearForm()">Clear</button>
            <span id="editing" style="color:var(--mut);font-size:.85rem"></span>
          </div>
        </form>
        <div class="saved" id="saved"></div>
      </div>
    </div>
  </section>

  <section id="val" style="display:none">
    <div class="progress"><span id="valcount"></span>
      <div class="bar"><i id="valbar"></i></div><span>need ≥55 approved</span></div>
    <div class="navrow">
      <button class="ghost" onclick="step(-1)">← prev</button>
      <button class="ghost" onclick="step(1)">next →</button>
      <span id="vpos" style="color:var(--mut);font-size:.85rem"></span>
      <div class="spacer"></div>
      <label style="display:inline;margin:0;text-transform:none;letter-spacing:0">
        <input type="checkbox" id="onlypending" checked onchange="renderVal()"
        style="width:auto"> only pending</label>
    </div>
    <div class="vcard" id="vcard">No items yet — items/items.jsonl appears after
      seeds are merged (src/generate.py).</div>
    <div class="keys">keys: <kbd>a</kbd> approve · <kbd>x</kbd> reject ·
      <kbd>d</kbd> Dari register · <kbd>f</kbd> Farsi register ·
      <kbd>←</kbd><kbd>→</kbd> navigate — edits in the fields are saved with
      the decision</div>
  </section>

  <section id="judge" style="display:none">
    <div class="progress"><span id="jcount"></span>
      <div class="bar"><i id="jbar"></i></div><span id="jtotal"></span></div>
    <div class="vcard" id="jcard">Loading…</div>
    <div class="keys">System identity is hidden and order is randomized.
      keys: <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> intent ·
      <kbd>q</kbd>…<kbd>u</kbd> appropriateness 1–7 · <kbd>Enter</kbd> submit</div>
  </section>
</main>
<div class="toast" id="toast"></div>
<script>
const FC = ["ritual_refusal_literal","intent_inversion",
  "indirect_refusal_as_assent","obligation_face_deleted","register_violation"];
const PROMPTS = [
 ["«قابل ندارد» at the till","A seller waves away payment at the end of a sale. What exact words — and what happens if the buyer walks out without paying?","ritual_refusal_literal","fa2en","taarof: ritual waiver of payment"],
 ["Tea refused, tea wanted","First business visit; the guest turns down tea or food the first time. How many offers before acceptance, and what words?","ritual_refusal_literal","fa2en","taarof: first refusal & re-offer"],
 ["Money between relatives","Repayment, wages, or a loan inside the family business, deflected with a formula. Who must insist, and how hard?","ritual_refusal_literal","fa2en","kin taarof over money"],
 ["The promise that wasn't","An «ان‌شاءالله ببینیم…» that everyone present knew meant no — but a written translation would read as maybe/yes.","indirect_refusal_as_assent","fa2en","inshallah-deferral"],
 ["Walking away politely","How does a customer end a failed bargain without ever saying no? What does the seller actually conclude?","indirect_refusal_as_assent","fa2en","polite exit formula"],
 ["“My work is nothing”","A craftsman or cook presents their best work as unworthy or trifling. What's the exact self-deprecation?","intent_inversion","fa2en","shekasteh-nafsi"],
 ["“Whatever you say” mid-bargain","Deference that concedes face, not price. Where did you hear it and what did both sides understand?","intent_inversion","fa2en","deference formula in bargaining"],
 ["Shame before a creditor","A debtor promising payment with a shame/face formula that makes the promise binding. What were the words?","obligation_face_deleted","fa2en","ru-siyahi / sharmandegi"],
 ["Bound by salt","Thanks that created a standing obligation (نمک‌گیر, حق به گردن…). What favor triggered it?","obligation_face_deleted","fa2en","namak-gir / haq"],
 ["Objecting to an elder","A junior raising a real objection to a senior's business decision, wrapped in petition language. What was really being said?","register_violation","fa2en","arz / deference to elders"],
 ["The blunt foreign email","An English message (invoice chase, complaint, deadline) that needed rewriting before it reached an elder partner. What was the original line?","register_violation","en2fa","dunning without face loss"],
 ["“Let's grab tea sometime!”","English ritual friendliness that would read as a real invitation or promise in Dari. Any line from a call or trade fair.","intent_inversion","en2fa","reverse taarof"],
 ["A real no, not taarof","An English refusal (gift, discount, request) that must NOT be heard as a ritual first no. How should it be marked as final?","ritual_refusal_literal","en2fa","refusal that must land as final"],
 ["Hawala & ledger courtesies","Formulas from money transfer, credit ledgers, weighing, or IOUs that outsiders misread (امانت, حواله, قرض حسنه…).","obligation_face_deleted","fa2en","bazaar credit formulas"]
];
let state={seeds:[],items:[]}, editingId=null, vIndex=0;

function $(id){return document.getElementById(id)}
function toast(m){const t=$("toast");t.textContent=m;t.classList.add("show");
  setTimeout(()=>t.classList.remove("show"),1400)}
function show(tab){
  for(const t of ["seed","val","judge"]){
    $(t).style.display=tab===t?"":"none";
    $("tab-"+t).classList.toggle("on",tab===t);
  }
  if(tab==="val")renderVal();
  if(tab==="judge")loadJudge();
}
function dirs(){
  const fa=$("direction").value==="fa2en";
  $("utterance_src").classList.toggle("fa",fa);
  $("literal_render").classList.toggle("fa",!fa);
  $("intent_render").classList.toggle("fa",!fa);
}
function renderPrompts(){
  $("prompts").innerHTML=PROMPTS.map((p,i)=>
   `<div class="pcard" id="pc${i}" onclick="pick(${i})"><b>${p[0]}</b>
    <span>${p[1]}</span><span class="tag">${p[2]} · ${p[3]}</span></div>`).join("");
}
function pick(i){
  const p=PROMPTS[i];
  document.querySelectorAll(".pcard").forEach(c=>c.classList.remove("sel"));
  $("pc"+i).classList.add("sel");
  $("hint").textContent=p[1];
  $("failure_class").value=p[2];
  $("direction").value=p[3];
  $("phenomenon").value=p[4];
  dirs();
  $("utterance_src").focus();
}
async function refresh(){
  state=await (await fetch("/api/state")).json();
  const n=state.seeds.length;
  $("seedcount").textContent=n+" seed"+(n===1?"":"s");
  $("seedbar").style.width=Math.min(100,n/12*100)+"%";
  $("saved").innerHTML=state.seeds.map(s=>
   `<div class="srow"><small>${s.id}</small>
    <span class="${s.direction==='fa2en'?'fa':''}" style="flex:1">${s.utterance_src}</span>
    <small>${s.failure_class}</small>
    <button onclick='editSeed(${JSON.stringify(s.id)})'>edit</button>
    <button onclick='delSeed(${JSON.stringify(s.id)})'>delete</button></div>`).join("");
}
function formItem(){
  return {id:editingId, direction:$("direction").value,
    utterance_src:$("utterance_src").value.trim(),
    context:$("context").value.trim(),
    literal_render:$("literal_render").value.trim(),
    intent_render:$("intent_render").value.trim(),
    pragmatic_note:$("pragmatic_note").value.trim(),
    failure_class:$("failure_class").value,
    lang_code:$("lang_code").value,
    phenomenon:$("phenomenon").value.trim(),
    tranche:"seed",validated:false,validator_note:""};
}
async function saveSeed(e){
  e.preventDefault();
  const r=await fetch("/api/seed/save",{method:"POST",
    body:JSON.stringify({item:formItem()})});
  const d=await r.json();
  toast("saved "+d.id);
  clearForm();refresh();
}
function clearForm(){
  editingId=null;$("editing").textContent="";$("savebtn").textContent="Save seed";
  ["utterance_src","context","literal_render","intent_render",
   "pragmatic_note","phenomenon"].forEach(k=>$(k).value="");
}
function editSeed(id){
  const s=state.seeds.find(x=>x.id===id);if(!s)return;
  editingId=id;$("editing").textContent="editing "+id;
  $("savebtn").textContent="Update "+id;
  for(const k of ["direction","failure_class","utterance_src","context",
    "literal_render","intent_render","pragmatic_note"])$(k).value=s[k]||"";
  $("lang_code").value=s.lang_code||"prs_Arab";
  $("phenomenon").value=s.phenomenon||"";
  dirs();window.scrollTo({top:0,behavior:"smooth"});
}
async function delSeed(id){
  if(!confirm("Delete "+id+"?"))return;
  await fetch("/api/seed/delete",{method:"POST",body:JSON.stringify({id})});
  refresh();
}
/* ---------- validation tab ---------- */
function valList(){
  return $("onlypending").checked
    ? state.items.filter(i=>!i.validated&&!i.rejected):state.items;
}
function renderVal(){
  const items=state.items;
  const ok=items.filter(i=>i.validated).length,
        rej=items.filter(i=>i.rejected).length;
  $("valcount").textContent=`${ok} approved · ${rej} rejected · ${items.length-ok-rej} pending`;
  $("valbar").style.width=Math.min(100,ok/55*100)+"%";
  const list=valList();
  if(!list.length){$("vcard").innerHTML=
    items.length?"Nothing pending — uncheck “only pending” to revisit.":
    "No items yet — items/items.jsonl appears after seeds are merged.";
    $("vpos").textContent="";return}
  if(vIndex>=list.length)vIndex=0;if(vIndex<0)vIndex=list.length-1;
  const it=list[vIndex];
  $("vpos").textContent=`${vIndex+1} / ${list.length} · ${it.id}`;
  const fa=it.direction==="fa2en";
  const status=it.validated?'<span class="pill v">approved</span>':
    it.rejected?'<span class="pill r">rejected</span>':
    '<span class="pill p">pending</span>';
  $("vcard").innerHTML=`
   <div class="meta"><span>${it.id}</span><span>${it.direction}</span>
     <span>${it.tranche}</span>
     <span>${it.phenomenon||""}</span>${status}</div>
   <div class="row3">
     <div><label>failure class</label><select id="v_failure_class">
       ${FC.map(f=>`<option ${f===it.failure_class?"selected":""}>${f}</option>`).join("")}
     </select></div>
     <div><label>register / lang_code</label><select id="v_lang_code">
       <option value="prs_Arab" ${it.lang_code!=="pes_Arab"?"selected":""}>Dari (prs_Arab)</option>
       <option value="pes_Arab" ${it.lang_code==="pes_Arab"?"selected":""}>Farsi (pes_Arab)</option>
     </select></div>
     <div><label>direction</label><select id="v_direction">
       <option ${it.direction==="fa2en"?"selected":""}>fa2en</option>
       <option ${it.direction==="en2fa"?"selected":""}>en2fa</option>
     </select></div>
   </div>
   <label>utterance</label>
   <textarea id="v_utterance_src" class="${fa?"fa":""}">${esc(it.utterance_src)}</textarea>
   <label>context</label>
   <textarea id="v_context">${esc(it.context)}</textarea>
   <div class="row">
     <div><label>literal render</label>
       <textarea id="v_literal_render" class="${fa?"":"fa"}">${esc(it.literal_render)}</textarea></div>
     <div><label>intent render</label>
       <textarea id="v_intent_render" class="${fa?"":"fa"}">${esc(it.intent_render)}</textarea></div>
   </div>
   <label>pragmatic note</label>
   <input id="v_pragmatic_note" value="${esc(it.pragmatic_note)}">
   ${it.draft_flag?`<div class="hint">⚑ drafter's flag: ${esc(it.draft_flag)}</div>`:""}
   <label>validator note</label>
   <input id="v_validator_note" value="${esc(it.validator_note||"")}">
   <div class="btns">
     <button class="ok" onclick="decide(true)">Approve (a)</button>
     <button class="warn" onclick="decide(false)">Reject (x)</button>
   </div>`;
}
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/"/g,"&quot;")}
function step(d){vIndex+=d;renderVal()}
async function decide(approve){
  const list=valList();const it={...list[vIndex]};
  for(const k of ["failure_class","lang_code","direction","utterance_src",
    "context","literal_render","intent_render","pragmatic_note",
    "validator_note"])it[k]=$("v_"+k).value.trim?$("v_"+k).value.trim():$("v_"+k).value;
  it.validated=approve;it.rejected=!approve;
  if(!approve&&!it.validator_note)
    it.validator_note=prompt("reject reason?")||"";
  await fetch("/api/item/update",{method:"POST",body:JSON.stringify({item:it})});
  const i=state.items.findIndex(x=>x.id===it.id);state.items[i]=it;
  toast((approve?"approved ":"rejected ")+it.id);
  renderVal();
}
/* ---------- judge tab ---------- */
let J=null, jIntent=0, jApprop=0;
async function loadJudge(){
  J=await (await fetch("/api/judge/state")).json();
  jIntent=0;jApprop=0;
  $("jcount").textContent=J.done+" judged";
  $("jtotal").textContent="of "+J.total;
  $("jbar").style.width=J.total?Math.min(100,J.done/J.total*100)+"%":"0";
  if(!J.total){$("jcard").innerHTML=J.msg||"No judging plan yet.";return}
  if(!J.next){$("jcard").innerHTML=
    "<b>All "+J.total+" judgments collected — Gate B complete.</b> "+
    "Tell Claude to continue with Phase 5.";return}
  const n=J.next, faSrc=n.direction==="fa2en";
  $("jcard").innerHTML=`
   <div class="meta"><span>#${J.done+1} / ${J.total}</span>
     <span>${n.direction}</span><span>system hidden</span></div>
   <label>source</label>
   <div class="hint ${faSrc?'fa':''}" style="font-size:${faSrc?'1.15rem':'1rem'};
     ${faSrc?'direction:rtl;line-height:1.9':''}">${esc(n.source)}</div>
   <label>context</label>
   <div class="hint">${esc(n.context)}</div>
   <label>candidate translation</label>
   <div class="hint ${faSrc?'':'fa'}" style="font-size:${faSrc?'1rem':'1.15rem'};
     ${faSrc?'':'direction:rtl;line-height:1.9'}">${esc(n.candidate)}</div>
   <label>intent</label>
   <div class="btns" id="jint">
     <button class="ghost" onclick="setInt(3)">3 · preserved</button>
     <button class="ghost" onclick="setInt(2)">2 · degraded</button>
     <button class="ghost" onclick="setInt(1)">1 · inverted / deleted</button>
   </div>
   <label>appropriateness (1 = badly wrong register … 7 = exactly right)</label>
   <div class="btns" id="japp">${[1,2,3,4,5,6,7].map(k=>
     `<button class="ghost" onclick="setApp(${k})">${k}</button>`).join("")}
   </div>
   <label>quick flags (optional)</label>
   <div class="btns" style="margin-top:2px">
     <label style="display:inline;text-transform:none;letter-spacing:0;margin:0">
       <input type="checkbox" id="jf_iranian" style="width:auto"> Iranian register/dialect (not Dari)</label>
     <label style="display:inline;text-transform:none;letter-spacing:0;margin:0">
       <input type="checkbox" id="jf_syntax" style="width:auto"> broken syntax / garbled</label>
     <label style="display:inline;text-transform:none;letter-spacing:0;margin:0">
       <input type="checkbox" id="jf_wronglang" style="width:auto"> wrong language / untranslated</label>
   </div>
   <label>note (optional)</label>
   <input id="jnote">
   <div class="btns">
     <button class="primary" onclick="submitJudge()">Submit & next (Enter)</button>
   </div>`;
}
function mark(divId,val,offset){
  [...$(divId).children].forEach((b,i)=>{
    b.style.background=(i===offset)?"var(--acc2)":"";
    b.style.color=(i===offset)?"#fff":"";});
}
function setInt(v){jIntent=v;mark("jint",v,3-v)}
function setApp(v){jApprop=v;mark("japp",v,v-1)}
async function submitJudge(){
  if(!jIntent||!jApprop){toast("pick intent and appropriateness");return}
  const flags=[["jf_iranian","iranian_register"],["jf_syntax","broken_syntax"],
    ["jf_wronglang","wrong_language"]].filter(f=>$(f[0]).checked).map(f=>f[1]);
  const r=await fetch("/api/judge/save",{method:"POST",body:JSON.stringify(
    {idx:J.next.idx,intent:jIntent,appropriateness:jApprop,
     note:$("jnote").value,flags})});
  const d=await r.json();
  if(!d.ok){toast(d.err);return}
  loadJudge();
}
document.addEventListener("keydown",e=>{
  if($("judge").style.display!=="none"){
    if(document.activeElement.tagName==="INPUT"){
      if(e.key==="Enter")submitJudge();
      return;
    }
    const app={"q":1,"w":2,"e":3,"r":4,"t":5,"y":6,"u":7};
    if(["1","2","3"].includes(e.key))setInt(+e.key);
    else if(app[e.key])setApp(app[e.key]);
    else if(e.key==="Enter")submitJudge();
    return;
  }
  if($("val").style.display==="none")return;
  if(["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName))return;
  if(e.key==="a")decide(true);else if(e.key==="x")decide(false);
  else if(e.key==="ArrowRight")step(1);else if(e.key==="ArrowLeft")step(-1);
  else if(e.key==="d"){$("v_lang_code").value="prs_Arab";toast("Dari register")}
  else if(e.key==="f"){$("v_lang_code").value="pes_Arab";toast("Farsi register")}
});
renderPrompts();dirs();refresh();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"Sawda item studio on http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
