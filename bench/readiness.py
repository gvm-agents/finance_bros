"""Read-only readiness check: prints PASS / FAIL / SKIP per item for the machine it runs on.

  venv/bin/python -m bench.readiness                       # MacBook, from the repo
  ssh mini '... python - --machine mini' < bench/readiness.py   # Mini, nothing copied there

Changes nothing: no installs, no downloads, no model pulls, no paid calls. The only
network calls are free: Ollama on this machine (one short test prompt per local model),
Fireworks' model list (needs the key; listing is not billed) and a Google sign-in token
for Vertex (no model call). Keys are checked for presence only and never printed.
Stdlib only and Python 3.9-safe, so it can run on a machine that has no project venv yet.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_here = globals().get("__file__") or ""
DEFAULT_REPO = (Path(_here).resolve().parent.parent if _here.endswith("readiness.py")
                else Path.home() / "Developer" / "open-model-eval")
OLLAMA = "http://127.0.0.1:11434"
FIREWORKS_MODELS = "https://api.fireworks.ai/inference/v1/models"
SECRETS_FILE = Path(os.environ.get("EVAL_SECRETS_FILE", Path.home() / ".config" / "open-model-eval" / "secrets.env"))
# Azure key for this project only (never the main secrets files); presence is checked, the value is never read into output.
AZURE_ENV = Path(os.environ.get("EVAL_AZURE_ENV", Path.home() / ".config" / "open-model-eval" / "azure.env"))
# Minimum test items (held-back split) for a task to be scoreable; name_match is a yes/no task, so it needs more.
MIN_TEST = {"name_match": 60}
MIN_TEST_DEFAULT = 30
TASKS = ["formd_extract", "name_match", "sector", "snapshot", "format_table", "longdoc", "adv_extract"]
# Used only when lanes.json is not on this machine (e.g. the Mini before the repo is copied there).
FALLBACK_LOCAL = {"mini": ["gemma4:e2b"], "macbook": ["gemma4:e2b", "gemma4:12b", "gemma4:26b"]}


class Report:
    def __init__(self):
        self.rows = []

    def add(self, item: str, ok, detail: str = "") -> None:
        self.rows.append((item, {True: "PASS", False: "FAIL", None: "SKIP", "info": "INFO"}[ok], detail))

    def print(self, machine: str) -> int:
        w = max(len(r[0]) for r in self.rows)
        print(f"\nReadiness check: {machine} ({platform.node()})\n")
        print(f"{'Item':<{w}}  Result  Detail")
        print(f"{'-' * w}  ------  ------")
        for item, res, detail in self.rows:
            print(f"{item:<{w}}  {res:<6}  {detail}")
        fails = sum(r[1] == "FAIL" for r in self.rows)
        print(f"\n{sum(r[1] == 'PASS' for r in self.rows)} PASS, {fails} FAIL, "
              f"{sum(r[1] == 'SKIP' for r in self.rows)} SKIP (SKIP = not needed on this machine)")
        return 1 if fails else 0


def http_json(url: str, data: dict | None = None, headers: dict | None = None, timeout: float = 10):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def detect_machine() -> str:
    return "mini" if "mini" in platform.node().lower() else "macbook"


def memory_gb() -> float:
    try:
        return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
    except (ValueError, OSError):
        return 0.0


def chip() -> str:
    r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
    return r.stdout.strip() or platform.machine()


def load_lanes(repo: Path) -> dict | None:
    f = repo / "lanes.json"
    return json.loads(f.read_text())["lanes"] if f.exists() else None


FALLBACK_ROLES = {"mini": {"vertex", "fireworks", "ollama"}, "macbook": {"ollama"}}


def runs_here(lanes: dict | None, machine: str, provider: str) -> bool:
    if lanes is None:
        return provider in FALLBACK_ROLES[machine]
    return bool(lanes_here(lanes, machine, provider))


def lanes_here(lanes: dict | None, machine: str, provider: str | None = None) -> dict:
    if lanes is None:
        return {}
    return {k: v for k, v in lanes.items() if v.get("runs_on") == machine and (provider is None or v["provider"] == provider)}


def find_python311() -> str:
    """Any Python 3.11+ already on this machine (for the FAIL detail); empty if none."""
    cands = [str(p) for p in sorted((Path.home() / ".pyenv" / "versions").glob("3.1[1-3]*/bin/python3"))]
    cands += [shutil.which(f"python3.{m}") for m in range(11, 16)]
    return next((c for c in cands if c), "")


def secret_present(name: str) -> tuple[bool, str]:
    """Presence only: environment first, then the local secrets file. The value is never read into output."""
    if os.environ.get(name):
        return True, "environment"
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text().splitlines():
            if re.match(rf"\s*(export\s+)?{name}=\S", line):
                return True, str(SECRETS_FILE).replace(str(Path.home()), "~")
    if name == "AZURE_OPENAI_API_KEY" and AZURE_ENV.exists():
        for line in AZURE_ENV.read_text().splitlines():
            if re.match(rf"\s*(export\s+)?{name}=\S", line):
                return True, str(AZURE_ENV).replace(str(Path.home()), "~")
    return False, ""


def secret_value(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text().splitlines():
            m = re.match(rf"\s*(export\s+)?{name}=(.*)$", line)
            if m:
                return m.group(2).strip().strip("'\"")
    return ""


# ---------------------------------------------------------------- checks

def check_python(rep: Report, repo: Path) -> Path | None:
    venv_py = repo / "venv" / "bin" / "python"
    if not repo.exists():
        rep.add("Repo on this machine", False, f"{repo} not found (copy needed; see approval list)")
        found = find_python311()
        rep.add("Python 3.11+ venv", False, f"no project venv; usable interpreter already here: {found or 'none'}")
        return None
    rep.add("Repo on this machine", True, str(repo).replace(str(Path.home()), "~"))
    if not venv_py.exists():
        rep.add("Python 3.11+ venv", False, f"no venv at {venv_py}; interpreter available: {find_python311() or 'none'}")
        return None
    v = subprocess.run([str(venv_py), "-c", "import sys,anthropic,openai;print('%d.%d.%d'%sys.version_info[:3])"],
                       capture_output=True, text=True)
    ver = v.stdout.strip()
    ok = v.returncode == 0 and tuple(int(x) for x in ver.split(".")[:2]) >= (3, 11)
    rep.add("Python 3.11+ venv", ok, f"Python {ver}, packages installed" if ok else (v.stderr.strip()[-120:] or ver))
    return venv_py if ok else None


def check_tests(rep: Report, repo: Path, venv_py: Path | None, skip: bool) -> None:
    if skip:
        rep.add("Repo tests pass", None, "skipped (--no-tests)")
        return
    if venv_py is None:
        rep.add("Repo tests pass", False, "no working venv")
        return
    r = subprocess.run([str(venv_py), "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=repo,
                       capture_output=True, text=True, timeout=600)
    last = (r.stdout.strip().splitlines() or ["no output"])[-1]
    rep.add("Repo tests pass", r.returncode == 0, last)


def check_corpus(rep: Report, repo: Path) -> None:
    items = repo / "data" / "items"
    for t in TASKS:
        f = items / f"{t}.jsonl"
        if not f.exists():
            rep.add(f"Data: {t}", False, "file missing")
            continue
        rows = [json.loads(l) for l in f.open() if l.strip()]
        test = sum(r.get("split") == "test" for r in rows)
        need = MIN_TEST.get(t, MIN_TEST_DEFAULT)
        extra = ""
        if t == "name_match":
            same = sum(bool(r["key"]["same"]) for r in rows if r.get("split") == "test")
            extra = f"; held back: {same} same / {test - same} different"
        rep.add(f"Data: {t}", test >= need, f"{len(rows)} items, {test} held back for scoring (need {need}){extra}")


def check_ollama(rep: Report, lanes: dict | None, machine: str, prompt_test: bool) -> None:
    exe = shutil.which("ollama") or next((p for p in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama",
                                                       "/Applications/Ollama.app/Contents/Resources/ollama") if Path(p).exists()), "")
    rep.add("Ollama installed", bool(exe), exe or "not installed (approval list)")
    wanted = sorted({v["model"] for v in lanes_here(lanes, machine, "ollama").values()}) if lanes else FALLBACK_LOCAL[machine]
    try:
        tags = http_json(OLLAMA + "/api/tags", timeout=5)
        pulled = {m["name"] for m in tags.get("models", [])}
        rep.add("Ollama running", True, f"{len(pulled)} model(s) on this machine")
    except (urllib.error.URLError, OSError, ValueError):
        rep.add("Ollama running", False, "no answer at 127.0.0.1:11434")
        for m in wanted:
            rep.add(f"Local model {m}", False, "Ollama not running")
        return
    mem = memory_gb()
    for m in wanted:
        if m not in pulled and f"{m}:latest" not in pulled:
            rep.add(f"Local model {m}", False, "not pulled yet")
            continue
        if not prompt_test:
            rep.add(f"Local model {m}", True, "pulled (test prompt skipped)")
            continue
        try:
            r = http_json(OLLAMA + "/api/generate", {"model": m, "prompt": "Reply with exactly one word: OK",
                                                     "stream": False, "think": False, "options": {"num_predict": 20}},
                          timeout=600)
            text = r.get("response", "").strip()
            secs = r.get("total_duration", 0) / 1e9
            rep.add(f"Local model {m}", "OK" in text.upper(), f"answered {text[:20]!r} in {secs:.1f}s (machine has {mem:.0f} GB)")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            rep.add(f"Local model {m}", False, f"test prompt failed: {str(exc)[:80]}")


def check_fireworks(rep: Report, lanes: dict | None, machine: str, online: bool) -> None:
    fw = {k: v for k, v in (lanes or {}).items() if v["provider"] == "fireworks"}
    present, where = secret_present("FIREWORKS_API_KEY")
    if not runs_here(lanes, machine, "fireworks"):
        # The key belongs on the Mini only; finding it here is itself a failure.
        rep.add("FIREWORKS_API_KEY absent here", not present,
                "correct: the key lives on the Mini only" if not present else f"found in {where}: remove it from this machine")
        rep.add("Fireworks model IDs", None, "Fireworks lanes run on the Mini")
        return
    rep.add("FIREWORKS_API_KEY present", present, f"found in {where} (value not shown)" if present else "not set yet (owner's step)")
    unconfirmed = [k for k, v in fw.items() if "CONFIRM" in json.dumps({x: v.get(x) for x in ("model", "deployment")})]
    listed: set | None = None
    if online and present:
        try:
            d = http_json(FIREWORKS_MODELS, headers={"Authorization": "Bearer " + secret_value("FIREWORKS_API_KEY")}, timeout=20)
            listed = {m.get("id") for m in d.get("data", [])}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            rep.add("Fireworks key works", False, f"model list call failed: {str(exc)[:80]}")
        else:
            rep.add("Fireworks key works", True, f"model list returned {len(listed)} serverless models (free call)")
    if lanes is None:
        rep.add("Fireworks model IDs", False, "lanes.json not on this machine (repo copy needed)")
    for k, v in fw.items():
        if k in unconfirmed:
            rep.add(f"Fireworks ID {k}", False, v.get("confirm_note", "marked CONFIRM in lanes.json"))
        elif listed is None:
            rep.add(f"Fireworks ID {k}", False if present and online else None,
                    f"{v['model']}: checked on public model page; live list not checked" + ("" if present else " (no key yet)"))
        else:
            rep.add(f"Fireworks ID {k}", v["model"] in listed, v["model"] + (" listed" if v["model"] in listed else " NOT in live list"))


def check_azure(rep: Report, lanes: dict | None, machine: str) -> None:
    az = {k: v for k, v in (lanes or {}).items() if v["provider"] == "azure"}
    if not az or not runs_here(lanes, machine, "azure"):
        rep.add("Azure lanes", None, "Azure lanes run on the Mini")
        return
    present, where = secret_present("AZURE_OPENAI_API_KEY")
    rep.add("AZURE_OPENAI_API_KEY present", present, f"found in {where} (value not shown)" if present else "not set yet (owner's step)")
    for k, v in az.items():
        bad = "CONFIRM" in json.dumps({x: v.get(x) for x in ("model", "deployment")})
        rep.add(f"Azure deployment {k}", not bad, v.get("confirm_note", "marked CONFIRM in lanes.json") if bad else f"{v['model']}: no CONFIRM marker (live answer checked by a test call)")


def check_vertex(rep: Report, lanes: dict | None, machine: str, online: bool, venv_py: Path | None) -> None:
    if not runs_here(lanes, machine, "vertex"):
        rep.add("Vertex sign-in (Claude lanes)", None, "Claude lanes run on the Mini")
        return
    sa_ok, _ = secret_present("VERTEX_LLM_SA_JSON")
    proj_ok, _ = secret_present("VERTEX_LLM_PROJECT")
    sa_path = Path(os.path.expanduser(secret_value("VERTEX_LLM_SA_JSON"))) if sa_ok else None
    if not (sa_ok and proj_ok and sa_path and sa_path.exists()):
        rep.add("Vertex sign-in (Claude lanes)", False, "VERTEX_LLM_SA_JSON / VERTEX_LLM_PROJECT not both set, or key file missing")
        return
    if not online:
        rep.add("Vertex sign-in (Claude lanes)", True, "robot key file and project present (token not tested)")
        return
    py = str(venv_py) if venv_py else sys.executable
    code = ("import sys,google.auth.transport.requests as t;from google.oauth2 import service_account as s;"
            "c=s.Credentials.from_service_account_file(sys.argv[1],scopes=['https://www.googleapis.com/auth/cloud-platform']);"
            "c.refresh(t.Request());print('token ok')")
    r = subprocess.run([py, "-c", code, str(sa_path)], capture_output=True, text=True, timeout=60)
    ok = r.returncode == 0 and "token ok" in r.stdout
    rep.add("Vertex sign-in (Claude lanes)", ok,
            "Vertex service account signs in (no model call)" if ok else (r.stderr.strip().splitlines() or ["failed"])[-1][:100])


def check_spend(rep: Report, repo: Path) -> None:
    f = repo / "spend_cap.json"
    if not f.exists():
        rep.add("Spending cap", False, "spend_cap.json missing")
        return
    cap = json.loads(f.read_text())
    spent = 0.0
    for calls in (repo / "results" / "runs").glob("*/calls.jsonl"):
        if calls.parent.name.endswith("-rescored"):  # same calls scored again, no new spend
            continue
        if (calls.parent / "SUPERSEDED_BY").exists():  # a later run copied these calls and added to them; count only the later run
            continue
        spent += sum(json.loads(l).get("usd", 0) for l in calls.open() if l.strip())
    spent += sum(x.get("usd", 0) for x in cap.get("other_spend", []))
    confirmed = cap.get("fireworks_limit_confirmed")
    detail = f"spent so far ${spent:.2f} of ${cap['total_usd']:.0f}; Fireworks account limit " + (
        f"confirmed {confirmed}" if confirmed else "not confirmed yet (owner sets it in the Fireworks console)")
    rep.add("Spending cap", bool(confirmed) and spent <= cap["total_usd"], detail)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="readiness", description="Read-only PASS/FAIL readiness check for the bake-off.")
    ap.add_argument("--machine", choices=["auto", "macbook", "mini"], default="auto", help="which machine's role to check")
    ap.add_argument("--repo", type=Path, default=DEFAULT_REPO, help="path to this repo on this machine")
    ap.add_argument("--no-tests", action="store_true", help="do not run the repo's automatic checks")
    ap.add_argument("--offline", action="store_true", help="no network at all (skip test prompts, Fireworks list, Vertex token)")
    a = ap.parse_args(argv)
    machine = detect_machine() if a.machine == "auto" else a.machine
    repo = a.repo.expanduser()
    rep = Report()
    free_gb = shutil.disk_usage(str(Path.home())).free / 1e9
    rep.add("Machine", "info", f"{chip()}, {memory_gb():.0f} GB memory, {free_gb:.0f} GB free disk, macOS {platform.mac_ver()[0]}")
    lanes = load_lanes(repo)
    venv_py = check_python(rep, repo)
    if repo.exists():
        check_tests(rep, repo, venv_py, a.no_tests)
        check_corpus(rep, repo)
    else:
        rep.add("Repo tests pass", False, "repo not on this machine")
        rep.add("Data corpus", False, "repo not on this machine")
    check_ollama(rep, lanes, machine, not a.offline)
    check_fireworks(rep, lanes, machine, not a.offline)
    check_azure(rep, lanes, machine)
    check_vertex(rep, lanes, machine, not a.offline, venv_py)
    if repo.exists():
        check_spend(rep, repo)
    else:
        rep.add("Spending cap", None, "tracked in the MacBook repo")
    return rep.print(machine)


if __name__ == "__main__":
    sys.exit(main())
