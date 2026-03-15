#!/usr/bin/env python3
"""Analyze Forge proxy logs and generate a diagnostic report."""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Log loading
# ---------------------------------------------------------------------------

def parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp from log entry."""
    # Handle both with and without microseconds
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {ts!r}")


def load_logs(log_dir: str, since: str | None = None) -> list[dict]:
    """Load all JSON log files from log_dir, optionally filtered by timestamp."""
    since_dt: datetime | None = None
    if since:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                since_dt = datetime.strptime(since, fmt)
                break
            except ValueError:
                continue
        if since_dt is None:
            print(f"Error: cannot parse --since value: {since!r}", file=sys.stderr)
            print("Expected format: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'", file=sys.stderr)
            sys.exit(1)

    log_path = Path(log_dir)
    if not log_path.exists():
        print(f"Error: directory not found: {log_dir}", file=sys.stderr)
        sys.exit(1)

    entries: list[dict] = []
    for json_file in sorted(log_path.glob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Must have timestamp field to be a valid log entry
        if "timestamp" not in data:
            continue

        try:
            ts = parse_timestamp(data["timestamp"])
        except ValueError:
            continue

        if since_dt and ts < since_dt:
            continue

        entries.append(data)

    # Sort by timestamp, then sequence number
    entries.sort(key=lambda e: (e.get("timestamp", ""), e.get("sequence", 0)))
    return entries


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

TOKEN_BUCKETS = [
    (0, 8_000, "0-8k"),
    (8_000, 16_000, "8k-16k"),
    (16_000, 24_000, "16k-24k"),
    (24_000, 32_000, "24k-32k"),
    (32_000, float("inf"), "32k+"),
]


def bucket_label(tokens: int) -> str:
    for lo, hi, label in TOKEN_BUCKETS:
        if lo <= tokens < hi:
            return label
    return "32k+"


def analyze(logs: list[dict]) -> dict:
    """Compute all metrics from the loaded log entries."""
    if not logs:
        return {}

    total = len(logs)
    successes = sum(1 for e in logs if e.get("success"))
    repairs = sum(1 for e in logs if e.get("was_repaired"))
    empty_errors = sum(1 for e in logs if e.get("error") == "empty response")
    timeouts = sum(1 for e in logs if e.get("error") == "timeout")

    # Token stats — prefer actual prompt_tokens, fall back to approx_input_tokens
    input_token_counts: list[int] = []
    for e in logs:
        usage = e.get("response", {}).get("usage", {})
        pt = usage.get("prompt_tokens")
        if pt is not None:
            input_token_counts.append(int(pt))
        else:
            approx = e.get("request", {}).get("approx_input_tokens")
            if approx is not None:
                input_token_counts.append(int(approx))

    avg_input_tokens = int(sum(input_token_counts) / len(input_token_counts)) if input_token_counts else 0
    max_input_tokens = max(input_token_counts, default=0)

    # Context budget buckets
    bucket_total: dict[str, int] = defaultdict(int)
    bucket_success: dict[str, int] = defaultdict(int)
    for e, tokens in zip(logs, input_token_counts):
        label = bucket_label(tokens)
        bucket_total[label] += 1
        if e.get("success"):
            bucket_success[label] += 1

    # Context degradation detection: find first bucket where success rate drops below 80%
    degradation_threshold = 0.8
    degradation_bucket: str | None = None
    for _, _, label in TOKEN_BUCKETS:
        if bucket_total.get(label, 0) >= 3:  # only flag if enough samples
            rate = bucket_success.get(label, 0) / bucket_total[label]
            if rate < degradation_threshold:
                degradation_bucket = label
                break

    # Tool call analysis
    tool_calls: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "success": 0, "failure": 0})
    for e in logs:
        resp_tool_calls = e.get("response", {}).get("tool_calls", [])
        if not resp_tool_calls:
            continue
        success = e.get("success", False)
        for tc in resp_tool_calls:
            name = tc.get("name", "unknown")
            tool_calls[name]["calls"] += 1
            if success:
                tool_calls[name]["success"] += 1
            else:
                tool_calls[name]["failure"] += 1

    # Identify low-success-rate tools (threshold: < 70%, min 3 calls)
    low_success_tools = [
        name for name, stats in tool_calls.items()
        if stats["calls"] >= 3 and stats["success"] / stats["calls"] < 0.70
    ]

    # Error timeline — entries with errors or failures
    error_entries: list[dict] = []
    for e in logs:
        error = e.get("error")
        if error or not e.get("success"):
            ts_str = e.get("timestamp", "")
            try:
                ts_dt = parse_timestamp(ts_str)
                ts_display = ts_dt.strftime("%H:%M:%S")
            except ValueError:
                ts_display = ts_str[:19]

            usage = e.get("response", {}).get("usage", {})
            tokens = usage.get("prompt_tokens") or e.get("request", {}).get("approx_input_tokens", 0)

            error_label = error or "failed"
            detail = ""
            if error == "empty response":
                detail = "No content or tool_calls in response"
            elif error == "timeout":
                detail = "Upstream request timed out"
            elif e.get("was_repaired"):
                detail = "JSON repaired successfully"
            else:
                finish_reason = e.get("response", {}).get("finish_reason")
                if finish_reason:
                    detail = f"finish_reason={finish_reason}"

            error_entries.append({
                "sequence": e.get("sequence", "?"),
                "time": ts_display,
                "tokens": tokens,
                "error": error_label,
                "detail": detail,
            })

    # Period
    first_ts = logs[0].get("timestamp", "")
    last_ts = logs[-1].get("timestamp", "")
    try:
        period_start = parse_timestamp(first_ts).strftime("%Y-%m-%d %H:%M:%S")
        period_end = parse_timestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        period_start = first_ts
        period_end = last_ts

    # Model (use most common)
    model_counts: dict[str, int] = defaultdict(int)
    for e in logs:
        m = e.get("model", "unknown")
        if m:
            model_counts[m] += 1
    model = max(model_counts, key=lambda k: model_counts[k]) if model_counts else "unknown"

    return {
        "period_start": period_start,
        "period_end": period_end,
        "total": total,
        "model": model,
        "successes": successes,
        "repairs": repairs,
        "empty_errors": empty_errors,
        "timeouts": timeouts,
        "avg_input_tokens": avg_input_tokens,
        "max_input_tokens": max_input_tokens,
        "bucket_total": dict(bucket_total),
        "bucket_success": dict(bucket_success),
        "degradation_bucket": degradation_bucket,
        "tool_calls": dict(tool_calls),
        "low_success_tools": low_success_tools,
        "error_entries": error_entries,
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def pct(num: int, denom: int) -> str:
    if denom == 0:
        return "n/a"
    return f"{num / denom * 100:.1f}%"


def fmt_tokens(n: int) -> str:
    if n >= 1_000:
        return f"{n:,}"
    return str(n)


def format_report(analysis: dict) -> str:
    if not analysis:
        return "# Forge Log Analysis Report\n\nNo data to analyze.\n"

    total = analysis["total"]
    successes = analysis["successes"]
    repairs = analysis["repairs"]
    empty_errors = analysis["empty_errors"]
    timeouts = analysis["timeouts"]

    lines: list[str] = []

    # Header
    lines.append("# Forge Log Analysis Report")
    lines.append("")
    lines.append(f"**Period**: {analysis['period_start']} — {analysis['period_end']}")
    lines.append(f"**Total requests**: {total}")
    lines.append(f"**Model**: {analysis['model']}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Success rate | {successes}/{total} ({pct(successes, total)}) |")
    lines.append(f"| JSON repairs | {repairs}/{total} ({pct(repairs, total)}) |")
    lines.append(f"| Empty responses | {empty_errors}/{total} ({pct(empty_errors, total)}) |")
    lines.append(f"| Timeouts | {timeouts}/{total} ({pct(timeouts, total)}) |")
    lines.append(f"| Avg input tokens | {fmt_tokens(analysis['avg_input_tokens'])} |")
    lines.append(f"| Max input tokens | {fmt_tokens(analysis['max_input_tokens'])} |")
    lines.append("")

    # Context budget analysis
    lines.append("## Context Budget Analysis")
    lines.append("")
    lines.append("| Token Range | Requests | Success Rate |")
    lines.append("|-------------|----------|-------------|")

    bucket_total = analysis["bucket_total"]
    bucket_success = analysis["bucket_success"]
    for _, _, label in TOKEN_BUCKETS:
        n = bucket_total.get(label, 0)
        if n == 0:
            continue
        s = bucket_success.get(label, 0)
        lines.append(f"| {label} | {n} | {pct(s, n)} |")

    lines.append("")
    degradation_bucket = analysis["degradation_bucket"]
    if degradation_bucket:
        lines.append(
            f"**Degradation detected at {degradation_bucket} tokens** — "
            f"success rate drops below 80% threshold."
        )
    else:
        lines.append("No significant degradation detected across token ranges.")
    lines.append("")

    # Tool call analysis
    tool_calls = analysis["tool_calls"]
    if tool_calls:
        lines.append("## Tool Call Analysis")
        lines.append("")
        lines.append("| Tool | Calls | Success | Failure | Success Rate |")
        lines.append("|------|-------|---------|---------|-------------|")
        for name, stats in sorted(tool_calls.items(), key=lambda x: -x[1]["calls"]):
            c = stats["calls"]
            s = stats["success"]
            f = stats["failure"]
            lines.append(f"| {name} | {c} | {s} | {f} | {pct(s, c)} |")
        lines.append("")

        low_success_tools = analysis["low_success_tools"]
        if low_success_tools:
            for tool in low_success_tools:
                stats = tool_calls[tool]
                rate = pct(stats["success"], stats["calls"])
                lines.append(f"**{tool} has low success rate ({rate})** — model struggles with this tool.")
            lines.append("")
    else:
        lines.append("## Tool Call Analysis")
        lines.append("")
        lines.append("No tool calls recorded in this period.")
        lines.append("")

    # Error timeline
    error_entries = analysis["error_entries"]
    if error_entries:
        lines.append("## Error Timeline")
        lines.append("")
        lines.append("| # | Time | Tokens | Error | Detail |")
        lines.append("|---|------|--------|-------|--------|")
        for entry in error_entries:
            seq = entry["sequence"]
            time = entry["time"]
            tokens = fmt_tokens(entry["tokens"]) if entry["tokens"] else "n/a"
            error = entry["error"]
            detail = entry["detail"] or "-"
            lines.append(f"| {seq} | {time} | {tokens} | {error} | {detail} |")
        lines.append("")
    else:
        lines.append("## Error Timeline")
        lines.append("")
        lines.append("No errors recorded in this period.")
        lines.append("")

    # Recommendations block
    lines.append("## Recommendations for LLM")
    lines.append("")
    lines.append("Copy-paste this report into your LLM with this prompt:")
    lines.append("")
    lines.append("---")
    lines.append("Here is a Forge proxy log analysis from our GPT-OSS coding agent.")
    lines.append("Please analyze the failure patterns and suggest:")
    lines.append("1. What is the effective context window for this model?")
    lines.append("2. Which tools should be simplified or removed?")
    lines.append("3. What system prompt changes would improve success rate?")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Forge proxy logs")
    parser.add_argument("log_dir", help="Directory containing .json log files")
    parser.add_argument(
        "--since",
        help="Only analyze logs since this timestamp (e.g. '2026-03-16 05:00:00')",
    )
    parser.add_argument(
        "--output", "-o",
        help="Write report to file instead of stdout",
    )
    args = parser.parse_args()

    logs = load_logs(args.log_dir, args.since)
    if not logs:
        print("No log files found.")
        return

    analysis = analyze(logs)
    report = format_report(analysis)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
