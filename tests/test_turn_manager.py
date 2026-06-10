"""Phase 2 of the queue redesign: the client TurnManager state machine.

TurnManager (static/js/turnManager.js) is the single source of truth for chat
turn lifecycle + queue. It's pure logic (no DOM), so we execute it directly in
a JS engine and assert the state transitions. This guards the invariants the
chat UI relies on: idle-enqueue auto-drains, streaming blocks drain, leaving
streaming drains the next item, the draining lock is re-entrancy-safe and never
sticks, events fire, and the queue array is shared by reference with chat.js.
"""
import json
import os

import pytest

try:
    from py_mini_racer import MiniRacer
except Exception:  # pragma: no cover - optional dep
    MiniRacer = None

_TM_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "js", "turnManager.js")

_POLYFILL = """
var __timers=[]; function setTimeout(fn){__timers.push(fn);return __timers.length;}
function clearTimeout(){} function setInterval(){return 0;} function clearInterval(){}
function __flush(){const t=__timers.slice();__timers.length=0;t.forEach(f=>{try{f()}catch(e){}});}
var console={log(){},warn(){},error(){}};
"""

_HARNESS = r"""
JSON.stringify((function(){
  const r=[]; const tm=createTurnManager(); const sent=[];
  tm.setDrainExecutor(i=>sent.push(i.text));
  tm.enqueue({text:'msg1'}); __flush(); r.push(['idle enqueue auto-drains', sent.length===1&&sent[0]==='msg1']);
  tm.setStreaming(true); tm.enqueue({text:'msg2'}); __flush(); r.push(['streaming blocks drain', sent.length===1]);
  tm.setStreaming(false); __flush(); r.push(['unstream auto-drains next', sent.length===2&&sent[1]==='msg2']);
  let calls=0; const t2=createTurnManager(); t2.setDrainExecutor(()=>{calls++;t2.drain();});
  t2.enqueue({text:'a'}); t2.enqueue({text:'b'}); __flush(); r.push(['reentrancy guarded', calls===1]);
  let ev=0; const t3=createTurnManager(); t3.on('queue-changed',()=>ev++);
  t3.enqueue({text:'x'}); __flush(); t3.removeAt(0); r.push(['queue events fire', ev===2]);
  let last=null; const t4=createTurnManager(); t4.on('streaming-changed',v=>last=v);
  t4.setStreaming(true); const a=last===true; t4.setStreaming(false); const b=last===false; r.push(['streaming events fire', a&&b]);
  const t5=createTurnManager(); const q=t5.queue; t5.enqueue({text:'shared'}); r.push(['queue shared by ref', q.length===1&&q[0].text==='shared']);
  const t6=createTurnManager(); t6.setStreaming(true);
  t6.enqueue({text:'first'}); t6.enqueue({text:'second'}); t6.enqueue({text:'third'}); t6.prioritize(2);
  r.push(['prioritize moves to front', t6.queue[0].text==='third']);
  const t7=createTurnManager(); const got=[]; t7.setDrainExecutor(i=>{got.push(i.text); t7.setStreaming(true);});
  t7.enqueue({text:'q1'}); t7.enqueue({text:'q2'}); __flush();
  t7.setStreaming(false); __flush();
  r.push(['sequential drain across turns', got.length===2 && got[0]==='q1' && got[1]==='q2']);
  return r;
})())
"""


@pytest.mark.skipif(MiniRacer is None, reason="py_mini_racer not installed")
def test_turn_manager_state_machine():
    src = open(_TM_PATH, encoding="utf-8").read()
    src = src.replace("export default turnManager;", "").replace("export { createTurnManager };", "")
    ctx = MiniRacer()
    ctx.eval(_POLYFILL)
    ctx.eval(src)
    results = json.loads(ctx.eval(_HARNESS))
    failures = [name for name, ok in results if not ok]
    assert not failures, f"TurnManager invariants failed: {failures}"
