"""Generic starter for YOUR idea. It runs as-is (a planner -> critic graph with a red-flag hook); make it yours.

    python -m agent.app "your user's message"

Same spine as the HeatSafe Shift example (kit/examples/heatsafe), with the domain left for you. Add blocks
from `ss blocks` as DESIGN.md says:
- EDIT ME 1: GOAL and the planner/critic rules below.
- EDIT ME 2: RED_FLAGS: phrases that must stop the agents and get a human (pharmacist, teacher, officer).
- EDIT ME 3: agent/data/guidance.json: the only sources the agent may cite, each with a URL and date.
- EDIT ME 4: Answer fields in agent/plan.py.
IDEA.md says who it is for; DESIGN.md says which Strands blocks it uses and what is measured.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from strands import Agent
from strands.hooks import BeforeNodeCallEvent, HookProvider, HookRegistry
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from . import tools
from .plan import Answer, Critique

MODEL_ID = os.environ.get("SHIP_MODEL", "us.amazon.nova-2-lite-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
logging.getLogger("strands").setLevel(logging.CRITICAL)

GOAL = "Explain the user's question in plain {lang} (en = English, ta = Tamil script) using only the cited guidance."  # EDIT ME 1
# EDIT ME 2: a phrase list misses wording it has not seen. Add every miss `ss measure` finds, in every language,
# or put Strands Decider in front (`ss block decider`) and act only above a threshold you calibrated.
RED_FLAGS = ["double", "extra dose", "overdose", "stop taking", "change my dose", "suicide", "chest pain",
             "இரட்டிப்பு", "அதிக மாத்திரை"]
HANDOFF = {"en": "This needs a qualified person. Please contact them now; this assistant will not answer it.",
           "ta": "இதற்கு தகுதியான நபரின் உதவி தேவை. உடனே அவரைத் தொடர்பு கொள்ளுங்கள்; இந்த உதவியாளர் இதற்கு பதில் அளிக்காது."}
PLANNER = GOAL + " Call lookup_guidance first. Cite only ids it returns. Short sentences. Fix every problem a critic lists."
CRITIC = ("Reply ok=false with one line per problem if the answer is not in {lang}, cites an id not in {ids}, "
          "gives advice the guidance does not support, or is empty. Otherwise ok=true.")


class RedFlagGate(HookProvider):
    def __init__(self):
        self.tripped = []

    def register_hooks(self, registry: HookRegistry, **_):
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event: BeforeNodeCallEvent):
        text = str(event.invocation_state.get("user_text", "")).lower()
        hits = [p for p in RED_FLAGS if p in text]
        if hits:
            self.tripped = hits
            event.cancel_node = "red flag: " + ", ".join(hits)


def _model():
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)


def build_graph(lang, gate):
    planner = Agent(model=_model(), name="planner", system_prompt=PLANNER.format(lang=lang), tools=[tools.lookup_guidance],
                    structured_output_model=Answer, callback_handler=None)
    critic = Agent(model=_model(), name="critic", system_prompt=CRITIC.format(lang=lang, ids=sorted(tools.guidance_ids())),
                   structured_output_model=Critique, callback_handler=None)

    def again(state):
        r = state.results.get("critic")
        v = getattr(r.result, "structured_output", None) if r else None
        n = sum(1 for x in state.execution_order if x.node_id == "planner")
        if v is not None:
            print(f"[critic] pass {n}: " + ("PASS" if v.ok else "REVISE - " + "; ".join(v.problems)[:200]), flush=True)
        return bool(v is not None and not v.ok and n < 2)

    b = GraphBuilder()
    b.add_node(planner, "planner")
    b.add_node(critic, "critic")
    b.add_edge("planner", "critic")
    b.add_edge("critic", "planner", condition=again)
    b.set_entry_point("planner")
    b.set_max_node_executions(4)
    b.reset_on_revisit(True)
    b.set_hook_providers([gate])
    return b.build()


def run(case: dict) -> dict:
    t0 = time.time()
    lang = case.get("lang") or tools.language_of(case["text"])
    gate = RedFlagGate()
    meta = {"path": "agent", "passes": 0}
    try:
        res = build_graph(lang, gate)(f"User ({lang}): {case['text']}", invocation_state={"user_text": case["text"]})
    except RuntimeError:
        if not gate.tripped:
            raise
        res = None
    if gate.tripped:
        print(f"[safety] RED FLAG ({', '.join(gate.tripped)}) -> HAND OFF, agents cancelled", flush=True)
        ans = Answer(language=lang, answer=HANDOFF[lang], steps=[], escalation=HANDOFF[lang], citations=[])
        meta["path"] = "handoff"
    else:
        ans = res.results["planner"].result.structured_output
        if ans is None:
            raise RuntimeError("planner returned no structured answer")
        meta["passes"] = sum(1 for n in res.execution_order if n.node_id == "planner")
    meta["latency_ms"] = int((time.time() - t0) * 1000)
    print(f"[plan] {meta['path']} | {meta['latency_ms']} ms", flush=True)
    return {"plan": ans.model_dump(), "meta": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agent.app")
    ap.add_argument("text")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = run({"text": a.text})
    print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else "\n" + out["plan"]["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
