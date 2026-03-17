#!/usr/bin/env python3
"""Automated benchmark runner for Roominos CLI migration quality."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCENARIOS = {
    "scenario_01_insurance": {"name": "Insurance Contract", "type": "proc", "files": 3, "lines": 800},
    "scenario_02_payroll": {"name": "Payroll System", "type": "mixed", "files": 4, "lines": 1000},
    "scenario_03_inventory": {"name": "Inventory Batch", "type": "c_only", "files": 3, "lines": 600},
    "scenario_04_loan": {"name": "Loan Assessment", "type": "proc", "files": 5, "lines": 1200},
    "scenario_05_audit": {"name": "Audit Log", "type": "mixed", "files": 3, "lines": 700},
}


def run_scenario(scenario_dir, output_dir, model, api_base, api_key, runs=3):
    """Run migration on a scenario multiple times and collect stats."""
    results = []

    # Find main source file (largest .pc or .c file)
    source_files = sorted(
        [f for f in Path(scenario_dir).rglob("*.pc")] + [f for f in Path(scenario_dir).rglob("*.c")],
        key=lambda f: f.stat().st_size, reverse=True
    )
    if not source_files:
        return results

    main_source = str(source_files[0])

    for run in range(runs):
        run_output = os.path.join(output_dir, f"run_{run+1}")
        if os.path.exists(run_output):
            shutil.rmtree(run_output)

        # Copy memory from previous run if exists
        if run > 0:
            prev_mem = os.path.join(output_dir, f"run_{run}", ".roominos", "memory.json")
            if os.path.exists(prev_mem):
                os.makedirs(os.path.join(run_output, ".roominos"), exist_ok=True)
                shutil.copy(prev_mem, os.path.join(run_output, ".roominos", "memory.json"))

        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "roominos.cli", "migrate",
                 "--source", main_source,
                 "--output", run_output,
                 "--model", model,
                 "--api-base", api_base,
                 "--api-key", api_key,
                 "--max-tokens", "4000"],
                capture_output=True, text=True, timeout=600,
                cwd=os.path.dirname(os.path.dirname(scenario_dir))  # project root
            )
            elapsed = time.time() - start

            # Parse score from output
            score = 0
            for line in result.stdout.split('\n'):
                if 'PASS' in line and '%' in line:
                    import re
                    m = re.search(r'(\d+)%', line)
                    if m:
                        score = int(m.group(1))
                elif 'FAIL' in line and '%' in line:
                    import re
                    m = re.search(r'(\d+)%', line)
                    if m:
                        score = int(m.group(1))

            # Count files
            files_created = len(list(Path(run_output).rglob("*.java"))) + len(list(Path(run_output).rglob("*.xml"))) + len(list(Path(run_output).rglob("*.yml")))

            results.append({
                "run": run + 1,
                "score": score,
                "files": files_created,
                "time": round(elapsed, 1),
                "success": score >= 75
            })
            print(f"  Run {run+1}: {score}% ({files_created} files, {elapsed:.0f}s)")
        except subprocess.TimeoutExpired:
            results.append({"run": run + 1, "score": 0, "files": 0, "time": 600, "success": False})
            print(f"  Run {run+1}: TIMEOUT")
        except Exception as e:
            results.append({"run": run + 1, "score": 0, "files": 0, "time": 0, "success": False})
            print(f"  Run {run+1}: ERROR - {e}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Roominos Benchmark Runner")
    parser.add_argument("--model", default=os.environ.get("ROOMINOS_MODEL", "openai/gpt-oss-20b"))
    parser.add_argument("--api-base", default=os.environ.get("ROOMINOS_API_BASE", "https://openrouter.ai/api/v1"))
    parser.add_argument("--api-key", default=os.environ.get("ROOMINOS_API_KEY", ""))
    parser.add_argument("--runs", type=int, default=3, help="Runs per scenario")
    parser.add_argument("--scenarios", nargs="*", help="Specific scenarios to run")
    parser.add_argument("--output", default="/tmp/roominos-benchmark")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: Set ROOMINOS_API_KEY")
        sys.exit(1)

    benchmark_dir = Path(__file__).parent
    all_results = {}

    scenarios = args.scenarios or list(SCENARIOS.keys())

    print("=" * 60)
    print("  Roominos Benchmark")
    print("=" * 60)
    print(f"  Model: {args.model}")
    print(f"  Runs per scenario: {args.runs}")
    print(f"  Scenarios: {len(scenarios)}")
    print("=" * 60)

    for scenario_name in scenarios:
        if scenario_name not in SCENARIOS:
            print(f"Unknown scenario: {scenario_name}")
            continue

        info = SCENARIOS[scenario_name]
        scenario_dir = benchmark_dir / scenario_name
        if not scenario_dir.exists():
            print(f"Scenario dir not found: {scenario_dir}")
            continue

        print(f"\n{'='*40}")
        print(f"  {info['name']} ({info['type']}, {info['lines']} lines)")
        print(f"{'='*40}")

        output = os.path.join(args.output, scenario_name)
        results = run_scenario(str(scenario_dir), output, args.model, args.api_base, args.api_key, runs=args.runs)
        all_results[scenario_name] = results

    # Summary report
    print(f"\n{'='*60}")
    print("  BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"| {'Scenario':<25} | {'Avg Score':>9} | {'Best':>5} | {'Avg Files':>9} | {'Avg Time':>8} |")
    print(f"|{'-'*27}|{'-'*11}|{'-'*7}|{'-'*11}|{'-'*10}|")

    for name, results in all_results.items():
        if not results:
            continue
        info = SCENARIOS[name]
        avg_score = sum(r["score"] for r in results) / len(results)
        best_score = max(r["score"] for r in results)
        avg_files = sum(r["files"] for r in results) / len(results)
        avg_time = sum(r["time"] for r in results) / len(results)
        print(f"| {info['name']:<25} | {avg_score:>8.1f}% | {best_score:>4}% | {avg_files:>9.1f} | {avg_time:>7.0f}s |")

    # Save results
    report_path = os.path.join(args.output, "benchmark_results.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {report_path}")


if __name__ == "__main__":
    main()
