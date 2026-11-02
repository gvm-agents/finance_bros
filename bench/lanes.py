"""Call one model in one place and return text, token counts and time.

Providers:
  vertex     Claude through a Google Vertex project: a service account
             (VERTEX_LLM_SA_JSON + VERTEX_LLM_PROJECT), else VERTEX_PROJECT + Google login
  fireworks  Fireworks serverless, OpenAI-style API (FIREWORKS_API_KEY)
  azure      OpenAI models on an Azure resource (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT)
  fw_decide  a Fireworks decision model (Rune): one read, typed questions, probabilities, input tokens only
  ollama     Ollama at OLLAMA_URL, by default this machine at 127.0.0.1:11434 (no key; nothing leaves the machine)
  fake       canned replies, for tests only
Claude no longer accepts temperature settings, so open models run at their
own defaults too, except temperature 0 where the provider allows it (noted in the report).
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

LANES_FILE = Path(__file__).resolve().parent.parent / "lanes.json"
MAX_RETRIES = 6  # refused calls are retried this many times before they count as an error
RETRY_WAIT = 2.0  # seconds before the first retry; doubles each time, at most 30
REASONING_HEADROOM = 4000  # tokens allowed for thinking before the answer (thinking models)


@dataclass
class Reply:
    text: str
    tokens_in: int
    tokens_out: int
    seconds: float
    error: str = ""
    retries: int = 0


def load_lanes(path: Path = LANES_FILE) -> dict[str, dict]:
    """A value written env:NAME is filled from that environment variable; left empty, the lane counts as switched off."""
    lanes = json.loads(path.read_text(encoding="utf-8"))["lanes"]
    for lane in lanes.values():
        for k in ("model", "deployment"):
            if str(lane.get(k, "")).startswith("env:"):
                lane[k] = os.environ.get(lane[k][4:]) or "CONFIRM"
    return lanes


def cost(lane: dict, tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1e6 * lane["price_in"] + tokens_out / 1e6 * lane["price_out"]


class Caller:
    def __init__(self, lane: dict, fake_answers: dict | None = None):
        self.lane, self.fake = lane, fake_answers
        p = lane["provider"]
        if p != "fake" and "CONFIRM" in f"{lane['model']} {lane.get('deployment', '')}":
            raise ValueError(f"model ID or deployment not confirmed yet: {lane['model']} {lane.get('deployment', '')}")
        if p == "vertex":
            from anthropic import AnthropicVertex
            sa = os.environ.get("VERTEX_LLM_SA_JSON")
            project = os.environ.get("VERTEX_LLM_PROJECT") if sa else os.environ.get("VERTEX_PROJECT")
            if not project:
                raise ValueError("set VERTEX_LLM_SA_JSON + VERTEX_LLM_PROJECT (Mini) or VERTEX_PROJECT for Claude lanes")
            creds = None
            if sa:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(
                    os.path.expanduser(sa), scopes=["https://www.googleapis.com/auth/cloud-platform"])
            region = os.environ.get("VERTEX_LLM_REGION") or os.environ.get("VERTEX_REGION", "global")
            self.client = AnthropicVertex(project_id=project, region=region, credentials=creds)
        elif p == "fw_decide":
            if not os.environ.get("FIREWORKS_API_KEY"):
                raise ValueError("set FIREWORKS_API_KEY for Fireworks lanes")
        elif p in ("fireworks", "ollama"):
            from openai import OpenAI
            if p == "fireworks":
                key = os.environ.get("FIREWORKS_API_KEY")
                if not key:
                    raise ValueError("set FIREWORKS_API_KEY for Fireworks lanes")
                self.client = OpenAI(base_url="https://api.fireworks.ai/inference/v1", api_key=key)
            else:
                self.client = OpenAI(base_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434") + "/v1", api_key="ollama", timeout=60, max_retries=0)
        elif p == "azure":
            from openai import AzureOpenAI
            key = os.environ.get("AZURE_OPENAI_API_KEY")
            if not key:
                raise ValueError("set AZURE_OPENAI_API_KEY for Azure lanes")
            self.client = AzureOpenAI(api_key=key, api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                                      azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"])
        elif p != "fake":
            raise ValueError(f"unknown provider {p}")

    def __call__(self, prompt: str, max_out: int, item_id: str = "") -> Reply:
        """Call once; on a rate-limit refusal wait and try again, doubling the wait. Every refusal is counted on the reply."""
        retries = 0
        while True:
            r = self._once(prompt, max_out, item_id)
            if not ("RateLimit" in r.error or " 429" in r.error) or retries >= MAX_RETRIES:
                r.retries = retries
                return r
            retries += 1
            time.sleep(min(RETRY_WAIT * 2 ** (retries - 1), 30) * (1 + random.random() / 2))

    def _decide(self, prompt: str, t0: float) -> Reply:
        """Prompt must be JSON: {"input": text, "questions": [...]}. The reply text is the answers as JSON, the same shape a scorer can parse."""
        import urllib.error
        import urllib.request
        body = json.loads(prompt)
        req = urllib.request.Request("https://api.fireworks.ai/inference/v1/decisions", data=json.dumps({"model": self.lane["model"], **body}).encode(),
                                     headers={"Authorization": "Bearer " + os.environ["FIREWORKS_API_KEY"], "Content-Type": "application/json", "User-Agent": "open-model-eval"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            return Reply("", 0, 0, time.time() - t0, f"HTTPError 429 RateLimit" if e.code == 429 else f"HTTPError {e.code}: {e.read()[:300].decode('utf8', 'replace')}")
        return Reply(json.dumps(d["answers"]), d["usage"].get("input_tokens", 0), 0, time.time() - t0)

    def _once(self, prompt: str, max_out: int, item_id: str = "") -> Reply:
        p, t0 = self.lane["provider"], time.time()
        try:
            if p == "fake":
                text = (self.fake or {}).get(item_id, "{}")
                return Reply(text, len(prompt) // 4, len(text) // 4, 0.01)
            if p == "fw_decide":
                return self._decide(prompt, t0)
            if p == "vertex":
                extra = {"output_config": {"effort": self.lane["effort"]}} if self.lane.get("effort") else {}
                if self.lane.get("thinking"):  # e.g. {"type": "disabled"} or {"type": "enabled", "budget_tokens": 3000}
                    extra["thinking"] = self.lane["thinking"]
                r = self.client.messages.create(
                    model=self.lane["model"], max_tokens=max_out + self.lane.get("headroom", REASONING_HEADROOM),
                    messages=[{"role": "user", "content": prompt}], **extra)
                if r.stop_reason == "refusal":
                    return Reply("", r.usage.input_tokens, r.usage.output_tokens, time.time() - t0, "refusal")
                text = "".join(b.text for b in r.content if b.type == "text")
                return Reply(text, r.usage.input_tokens, r.usage.output_tokens, time.time() - t0)
            if p == "azure":  # GPT-5 models take no temperature and use max_completion_tokens
                r = self.client.chat.completions.create(model=self.lane["model"], max_completion_tokens=max_out + self.lane.get("headroom", REASONING_HEADROOM),
                                                        messages=[{"role": "user", "content": prompt}], reasoning_effort=self.lane.get("reasoning", "low"))
                u = r.usage
                return Reply(r.choices[0].message.content or "", u.prompt_tokens or 0, u.completion_tokens or 0, time.time() - t0)
            extra = {"reasoning_effort": self.lane.get("reasoning", "low")} if "gpt-oss" in self.lane["model"] or self.lane.get("reasoning") else {}
            model = self.lane["model"] + (f"#{self.lane['deployment']}" if self.lane.get("deployment") else "")
            r = self.client.chat.completions.create(
                model=model, temperature=0, max_tokens=max_out + self.lane.get("headroom", REASONING_HEADROOM),
                messages=[{"role": "user", "content": prompt}], extra_body=extra or None)
            u = r.usage
            return Reply(r.choices[0].message.content or "", getattr(u, "prompt_tokens", 0) or 0,
                         getattr(u, "completion_tokens", 0) or 0, time.time() - t0)
        except Exception as exc:  # noqa: BLE001 - one failed call is recorded, never fatal
            return Reply("", 0, 0, time.time() - t0, f"{type(exc).__name__}: {str(exc)[:300]}")
