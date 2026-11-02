"""Find each hosted model's real thinking switch with one small question. Paid but tiny (hard cap in code).

Run with API keys loaded:  venv/bin/python -m bench.probe_thinking
Prints, per setting, whether the call worked, tokens written and whether a separate reasoning field came back.
"""
from __future__ import annotations

import json
import os
import sys
import time

from . import lanes as L

Q = ("A fund has 3 holdings. A is worth 4.2M and grew 15%. B is worth 2.5M and fell 8%. C is worth 1.1M and doubled. "
     "What is the total value now, in millions? Reply with only the number.")
CAP_USD = 0.30
spent = 0.0


def fw(lane, extra, label):
    global spent
    c = L.Caller(lane)
    t0 = time.time()
    try:
        r = c.client.chat.completions.create(model=lane["model"], temperature=0, max_tokens=3000, messages=[{"role": "user", "content": Q}], extra_body=extra or None)
        m = r.choices[0].message
        rc = getattr(m, "reasoning_content", None) or (getattr(m, "model_extra", {}) or {}).get("reasoning_content")
        u = r.usage
        spent += L.cost(lane, u.prompt_tokens, u.completion_tokens)
        return {"setting": label, "ok": True, "out_tokens": u.completion_tokens, "reasoning_field": bool(rc), "answer": (m.content or "")[:60], "s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"setting": label, "ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


def vertex(lane, extra, label):
    global spent
    c = L.Caller(lane)
    t0 = time.time()
    try:
        r = c.client.messages.create(model=lane["model"], max_tokens=4000, messages=[{"role": "user", "content": Q}], **extra)
        txt = "".join(b.text for b in r.content if b.type == "text")
        kinds = sorted({b.type for b in r.content})
        spent += L.cost(lane, r.usage.input_tokens, r.usage.output_tokens)
        return {"setting": label, "ok": True, "out_tokens": r.usage.output_tokens, "blocks": kinds, "answer": txt[:60], "s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"setting": label, "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def main() -> int:
    lanes = L.load_lanes()
    out = {}
    for name in ("deepseek41_fw", "gptoss120_fw", "nemotron35_fw"):
        lane = lanes[name]
        out[name] = [fw(lane, {"reasoning_effort": e} if e else None, f"reasoning_effort={e or 'unset'}") for e in ("none", "low", "medium", "high", None)]
    for name, models in (("sonnet5", lanes["sonnet5"]), ("haiku45", lanes["haiku45"])):
        lane = models
        tests = [("thinking disabled", {"thinking": {"type": "disabled"}}), ("thinking enabled 2000", {"thinking": {"type": "enabled", "budget_tokens": 2000}}),
                 ("unset", {}), ("effort=low", {"output_config": {"effort": "low"}}), ("effort=high", {"output_config": {"effort": "high"}})]
        out[name] = [vertex(lane, x, lbl) for lbl, x in tests]
    out["_spent_usd"] = round(spent, 4)
    print(json.dumps(out, indent=1))
    return 0 if spent <= CAP_USD else 1


if __name__ == "__main__":
    raise SystemExit(main())
