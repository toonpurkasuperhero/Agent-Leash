"""CLI: python -m evaluation.run [--llm]"""
from __future__ import annotations

import argparse
import json

from agentleash import config

from .harness import run_eval


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AgentLeash evaluation suite")
    parser.add_argument("--llm", action="store_true", help="use Claude for task scoping and explanations")
    args = parser.parse_args()

    result = run_eval(use_llm=args.llm)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = config.DATA_DIR / "eval_results.json"
    out.write_text(json.dumps(result, indent=1))

    print(f"\n{'Setup':<22}{'Attack success':>16}{'Benign completed':>18}{'Needed approval':>17}{'p50 latency':>13}")
    for r in result["setups"].values():
        lat = f"{r['latency_p50_ms']:.2f} ms" if r["latency_p50_ms"] is not None else "—"
        print(f"{r['label']:<22}{r['attacks_succeeded']:>8}/{r['attacks_total']:<7}"
              f"{r['benign_completed']:>10}/{r['benign_total']:<7}{r['benign_approval_rate']:>16.0%}{lat:>13}")
    print(f"\nPer-scenario results written to {out}")


if __name__ == "__main__":
    main()
