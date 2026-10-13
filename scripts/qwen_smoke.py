"""Run the complete three-persona flow against a live local llama.cpp/Qwen server."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import create_app
from backend.llm import LLMClient
from backend.schemas import Session


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def api_json(response: httpx.Response, stage: str) -> dict:
    if not response.is_success:
        raise RuntimeError(f"{stage} failed ({response.status_code}): {response.text[:2000]}")
    return response.json()


def run(args: argparse.Namespace) -> None:
    os.environ["LLM_MODE"] = "qwen"
    os.environ["LLM_BASE_URL"] = args.base_url
    os.environ["LLM_MODEL"] = args.model
    os.environ["LLM_TIMEOUT"] = str(args.timeout)
    os.environ["CONTEXT_SIZE"] = str(args.context)

    out = Path(args.out)
    evidence = out.with_name("qwen_verification.json")
    started = datetime.now(timezone.utc)
    timer = time.perf_counter()
    server_root = args.base_url.removesuffix("/v1")
    with httpx.Client(timeout=30, trust_env=False) as probe:
        server_health = probe.get(server_root + "/health").json()
        server_models = probe.get(args.base_url + "/models").json()

    version = "UNKNOWN"
    if args.server_exe:
        try:
            completed = subprocess.run(
                [args.server_exe, "--version"], capture_output=True, text=True, timeout=30, check=False
            )
            version = (completed.stdout + completed.stderr).strip()
        except (OSError, subprocess.SubprocessError):
            pass

    with tempfile.TemporaryDirectory() as tmp:
        llm = LLMClient("qwen", base_url=args.base_url, context_size=args.context)
        api = TestClient(create_app(str(Path(tmp) / "qwen-smoke.sqlite3"), llm))
        idea = json.loads(Path(args.idea).read_text(encoding="utf-8"))

        if args.resume:
            session=json.loads(Path(args.resume).read_text(encoding='utf-8'))
            api.app.state.store.put(Session.model_validate(session))
            print(f"Resuming {len(session['transcript'])} saved utterances",flush=True)
        else:
            print("[1/3] Qwen target hypotheses", flush=True)
            session = api_json(api.post("/api/sessions", json=idea), "target generation")
            save(out.with_name("qwen_stage_1_targets.json"), session)
            print("[2/3] Qwen persona cards + independent validation", flush=True)
            selected = [target["id"] for target in session["targets"][:3]]
            session = api_json(api.post(f"/api/sessions/{session['id']}/select", json={"target_ids": selected}),"persona generation/validation")
            save(out.with_name("qwen_stage_2_personas.json"), session)

        print("[3/3] Qwen private → group → private interview + report", flush=True)
        response=api.post(f"/api/sessions/{session['id']}/run", json={})
        if not response.is_success:
            save(out,api_json(api.get(f"/api/sessions/{session['id']}"),'save failure'))
        session = api_json(response, "interview/report")
        save(out, session)

    elapsed = time.perf_counter() - timer
    usage = session["usage"]
    buckets=[usage,usage['selection'],usage['interview']]+usage.get('failed_interview_attempts',[])
    total_calls=sum(b['calls'] for b in buckets)
    total_prompt=sum(b['prompt_tokens'] for b in buckets)
    total_completion=sum(b['completion_tokens'] for b in buckets)
    result = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started.isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "elapsed_scope":'resume invocation only' if args.resume else 'full successful invocation',
        "resumed_from":args.resume,
        "total_recorded_model_latency_s":round(sum(b['latency_s'] for b in buckets),3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "llama_cpp_version": version,
        "server_health": server_health,
        "server_models": server_models,
        "model_alias": args.model,
        "model_path": args.model_path or "UNKNOWN",
        "model_sha256": args.model_sha256 or "UNKNOWN",
        "context_size": args.context,
        "result_file": str(out),
        "status": session["status"],
        "persona_count": len(session["cards"]),
        "validation_issue_counts": [len(item["issues"]) for item in session["validations"]],
        "utterance_count": len(session["transcript"]),
        "group_utterance_count": sum(row["phase"] == "group" for row in session["transcript"]),
        "report_sections": list(session["report"]["sections"]),
        "llm_call_count_total": total_calls,
        "llm_prompt_tokens_total": total_prompt,
        "llm_completion_tokens_total": total_completion,
        "llm_usage": usage,
    }
    save(evidence, result)
    if result["status"] != "COMPLETE" or result["persona_count"] != 3:
        raise RuntimeError("Qwen flow did not complete with three personas")
    print(json.dumps({k:v for k,v in result.items() if k not in ('llm_usage','server_models')}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--idea", default=str(ROOT / "examples" / "idea.json"))
    parser.add_argument('--resume',help='Saved FAILED/PRE/GROUP/POST/REPORT result JSON; preserve completed turns')
    parser.add_argument("--out", default=str(ROOT / "examples" / "qwen_e2e_result.json"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="persona-qwen")
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--server-exe")
    parser.add_argument("--model-path")
    parser.add_argument("--model-sha256")
    run(parser.parse_args())
