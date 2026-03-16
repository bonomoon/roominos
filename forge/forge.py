"""
Forge: Intelligent proxy between Roo Code and GPT-OSS.

Fixes unreliable tool calling responses from GPT-OSS by simplifying
tool schemas, repairing malformed JSON, and retrying on failure.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("forge")


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_request(method: str, path: str, tool_count: int) -> None:
    logger.info(f"[{_ts()}] → {method} {path} (tools: {tool_count})")


def log_response(status: int, detail: str) -> None:
    logger.info(f"[{_ts()}] ← {status} ({detail})")


# ---------------------------------------------------------------------------
# Configuration (populated at startup)
# ---------------------------------------------------------------------------

class Config:
    target: str = "http://localhost:11434/v1"
    port: int = 8080
    user_email: str = ""
    timeout: int = 60
    max_tools: int = 8
    log_dir: str = ""  # empty = no file logging


config = Config()

# ---------------------------------------------------------------------------
# Request/Response file logging
# ---------------------------------------------------------------------------

_request_counter = 0
_session_start: datetime | None = None


def _generate_diagnosis(success: bool, was_repaired: bool, finish_reason: str | None, error: str | None, approx_input_tokens: int) -> str:
    """Auto-generate a diagnosis line based on response characteristics."""
    if error == "empty response" or not success:
        return "⚠ Model returned empty response. Likely cause: context too large or model capacity exceeded."
    if was_repaired:
        return "🔧 JSON was repaired. Original response had malformed tool call arguments."
    if finish_reason == "length":
        return "⚠ Response truncated due to max_tokens. Consider increasing max_tokens."
    return "✅ Normal response."


def _build_markdown_report(
    seq: int,
    timestamp: datetime,
    model: str,
    messages: list,
    tools_sent: int,
    tool_names_sent: list[str],
    approx_input_tokens: int,
    resp_detail: dict,
    usage: dict,
    finish_reason: str | None,
    was_repaired: bool,
    attempt: int,
    max_retries: int,
    success: bool,
    error: str | None,
) -> str:
    """Build a human-readable markdown report for a request/response pair."""
    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    model_short = model.split("/")[-1] if "/" in model else model

    # Context budget line
    max_context = 32000
    budget_pct = approx_input_tokens / max_context * 100
    budget_status = "✅ OK" if budget_pct < 80 else "⚠ HIGH"
    budget_line = f"{approx_input_tokens:,} / {max_context:,} ({budget_pct:.1f}%) {budget_status}"

    # Tool names list
    tools_label = f"{tools_sent} ({', '.join(tool_names_sent)})" if tool_names_sent else str(tools_sent)

    # Last user message
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    if isinstance(last_user, list):
        # Content may be a list of content blocks
        last_user = " ".join(
            block.get("text", "") for block in last_user if isinstance(block, dict)
        )
    last_user_preview = str(last_user)[:500]

    # System message preview
    system_preview = ""
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, str) and content:
                system_preview = content[:500]
                break

    # Response status
    status_icon = "✅ Success" if success else "❌ Failed"

    # Tool calls section
    tool_calls_section = ""
    if resp_detail.get("tool_calls"):
        tool_calls_json = json.dumps(
            [{"name": tc["name"], "arguments": tc["arguments"]} for tc in resp_detail["tool_calls"]],
            ensure_ascii=False,
            indent=2,
        )
        tool_calls_section = f"\n### Tool Calls\n```json\n{tool_calls_json}\n```\n"

    # Content section
    content_section = ""
    if resp_detail.get("content_preview"):
        content_section = f"\n### Content (if text response)\n```\n{resp_detail['content_preview']}\n```\n"

    # Token usage
    prompt_tokens = usage.get("prompt_tokens", "—")
    completion_tokens = usage.get("completion_tokens", "—")
    total_tokens = usage.get("total_tokens", "—")

    # Diagnosis
    diagnosis = _generate_diagnosis(success, was_repaired, finish_reason, error, approx_input_tokens)

    repaired_str = "Yes" if was_repaired else "No"
    finish_str = finish_reason or "—"

    lines = [
        f"# Forge Log #{seq} — [{ts_str}]",
        "",
        "## Request",
        f"- **Model**: {model}",
        f"- **Message count**: {len(messages)}",
        f"- **Tools sent**: {tools_label}",
        f"- **Approx input tokens**: {approx_input_tokens:,}",
        f"- **Context budget**: {budget_line}",
        "",
        "### Last User Message",
        "```",
        last_user_preview,
        "```",
        "",
    ]

    if system_preview:
        lines += [
            "### System Messages (compressed)",
            system_preview,
            "",
        ]

    lines += [
        "## Response",
        f"- **Status**: {status_icon}",
        f"- **Finish reason**: {finish_str}",
        f"- **Was repaired**: {repaired_str}",
        f"- **Attempt**: {attempt + 1}/{max_retries + 1}",
        tool_calls_section.rstrip(),
        content_section.rstrip(),
        "",
        "### Token Usage",
        f"- Prompt: {prompt_tokens}",
        f"- Completion: {completion_tokens}",
        f"- Total: {total_tokens}",
        "",
        "## Diagnosis",
        diagnosis,
    ]

    return "\n".join(line for line in lines if line is not None)


def _append_session_summary(
    log_dir: str,
    seq: int,
    timestamp: datetime,
    model: str,
    total_tokens: int | str,
    tool_calls: list | None,
    content_preview: str | None,
    success: bool,
    was_repaired: bool,
    error: str | None,
) -> None:
    """Append one row to the session summary markdown table."""
    global _session_start

    summary_path = os.path.join(log_dir, "SESSION_SUMMARY.md")
    time_str = timestamp.strftime("%H:%M:%S")
    model_short = model.split("/")[-1] if "/" in model else model

    # Determine what the response was
    if tool_calls:
        response_type = tool_calls[0]["name"] if tool_calls else "(tool)"
    elif content_preview:
        response_type = "(content)"
    else:
        response_type = "(empty)"

    tokens_str = f"{total_tokens:,}" if isinstance(total_tokens, int) else str(total_tokens)
    status_str = "✅" if success else "❌"
    repaired_str = "Yes" if was_repaired else "No"

    note = ""
    if error == "empty response":
        note = "Context over budget"
    elif was_repaired:
        note = "JSON repaired"

    row = f"| {seq} | {time_str} | {model_short} | {tokens_str} | {response_type} | {status_str} | {repaired_str} | {note} |"

    # Create file with header if it doesn't exist
    if not os.path.exists(summary_path):
        start_str = _session_start.strftime("%Y-%m-%d %H:%M:%S") if _session_start else time_str
        header = (
            f"# Forge Session Summary\n\n"
            f"Started: {start_str}\n\n"
            "| # | Time | Model | Tokens | Tool/Content | Status | Repaired | Note |\n"
            "|---|------|-------|--------|-------------|--------|----------|------|\n"
        )
        with open(summary_path, "w") as f:
            f.write(header)

    with open(summary_path, "a") as f:
        f.write(row + "\n")


def log_to_file(req_body: dict, resp_body: dict, attempt: int, was_repaired: bool, error: str | None = None) -> str | None:
    """Save request + response pair to a JSON file and a markdown report for analysis."""
    if not config.log_dir:
        return None

    global _request_counter, _session_start
    _request_counter += 1
    if _session_start is None:
        _session_start = datetime.now()

    os.makedirs(config.log_dir, exist_ok=True)
    now = datetime.now()
    stem = f"{now.strftime('%Y%m%d_%H%M%S')}_{_request_counter:04d}"
    json_path = os.path.join(config.log_dir, f"{stem}.json")
    md_path = os.path.join(config.log_dir, f"{stem}.md")

    # Extract key info for analysis
    messages = req_body.get("messages", [])
    tools_sent = len(req_body.get("tools", []))
    tool_names_sent = [t.get("function", {}).get("name", "") for t in req_body.get("tools", []) if t.get("type") == "function"]

    # Calculate approximate token count (rough: 4 chars ≈ 1 token)
    req_text = json.dumps(req_body)
    approx_input_tokens = len(req_text) // 4

    # Extract response info
    resp_detail: dict = {}
    for choice in resp_body.get("choices", []):
        msg = choice.get("message", {})
        tc = msg.get("tool_calls", [])
        if tc:
            resp_detail["tool_calls"] = [
                {"name": t.get("function", {}).get("name"), "arguments": t.get("function", {}).get("arguments", "")[:200]}
                for t in tc
            ]
        if msg.get("content"):
            resp_detail["content_length"] = len(msg["content"])
            resp_detail["content_preview"] = msg["content"][:500]

    usage = resp_body.get("usage", {})
    finish_reason = resp_body.get("choices", [{}])[0].get("finish_reason")
    success = bool(resp_detail.get("tool_calls") or resp_detail.get("content_length"))
    max_retries = 2

    # --- JSON log (existing behaviour, unchanged) ---
    log_entry = {
        "timestamp": now.isoformat(),
        "sequence": _request_counter,
        "model": req_body.get("model", ""),
        "attempt": attempt,
        "was_repaired": was_repaired,
        "error": error,
        "request": {
            "message_count": len(messages),
            "last_user_message": next((m.get("content", "")[:300] for m in reversed(messages) if m.get("role") == "user"), ""),
            "tools_count": tools_sent,
            "tool_names": tool_names_sent,
            "approx_input_tokens": approx_input_tokens,
        },
        "response": {
            **resp_detail,
            "usage": usage,
            "finish_reason": finish_reason,
        },
        "success": success,
    }

    with open(json_path, "w") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)

    # --- Markdown report (new) ---
    md_content = _build_markdown_report(
        seq=_request_counter,
        timestamp=now,
        model=req_body.get("model", ""),
        messages=messages,
        tools_sent=tools_sent,
        tool_names_sent=tool_names_sent,
        approx_input_tokens=approx_input_tokens,
        resp_detail=resp_detail,
        usage=usage,
        finish_reason=finish_reason,
        was_repaired=was_repaired,
        attempt=attempt,
        max_retries=max_retries,
        success=success,
        error=error,
    )
    with open(md_path, "w") as f:
        f.write(md_content)

    # --- Session summary (new) ---
    _append_session_summary(
        log_dir=config.log_dir,
        seq=_request_counter,
        timestamp=now,
        model=req_body.get("model", ""),
        total_tokens=usage.get("total_tokens", "—"),
        tool_calls=resp_detail.get("tool_calls"),
        content_preview=resp_detail.get("content_preview"),
        success=success,
        was_repaired=was_repaired,
        error=error,
    )

    logger.info(f"[{_ts()}] 📝 logged → {stem}.json + .md")
    return json_path

# ---------------------------------------------------------------------------
# JSON repair utilities
# ---------------------------------------------------------------------------

def fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before ] or }."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


def fix_unescaped_quotes(text: str) -> str:
    """
    Attempt to fix unescaped double quotes inside JSON string values.
    This is a best-effort heuristic.
    """
    # Replace sequences like: "key": "value with "inner" quotes"
    # by escaping inner quotes that are NOT already escaped.
    # Strategy: inside strings (after ": "), escape bare " that are
    # not at the start/end of the value.
    def escape_inner(m: re.Match) -> str:
        prefix = m.group(1)
        content = m.group(2)
        # Escape any " not already escaped
        content = re.sub(r'(?<!\\)"', '\\"', content)
        return prefix + '"' + content + '"'

    # Match "key": "value" patterns where value may contain bare quotes
    return re.sub(r'(:\s*)"((?:[^"\\]|\\.)*)"', escape_inner, text)


def fix_missing_closing(text: str) -> str:
    """Append missing closing brackets and braces."""
    open_count = {"[": 0, "{": 0}
    close_map = {"]": "[", "}": "{"}
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch in ("[", "{"):
                open_count[ch] += 1
            elif ch in ("]", "}"):
                opener = close_map[ch]
                if open_count[opener] > 0:
                    open_count[opener] -= 1

    # Close in reverse order of typical nesting (braces before brackets)
    suffix = "}" * open_count["{"] + "]" * open_count["["]
    return text + suffix


def repair_json(text: str) -> tuple[Any, bool]:
    """
    Attempt to parse JSON, applying repair strategies on failure.
    Returns (parsed_object, was_repaired).
    """
    # Fast path: already valid
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        pass

    repaired = text
    for fix in (fix_trailing_commas, fix_missing_closing, fix_unescaped_quotes):
        repaired = fix(repaired)
        try:
            return json.loads(repaired), True
        except json.JSONDecodeError:
            pass

    # Try all fixes combined
    combined = fix_unescaped_quotes(fix_missing_closing(fix_trailing_commas(text)))
    try:
        return json.loads(combined), True
    except json.JSONDecodeError:
        pass

    return None, False


# ---------------------------------------------------------------------------
# Tool schema simplification
# ---------------------------------------------------------------------------

def truncate_description(desc: str, max_len: int = 100) -> str:
    if len(desc) <= max_len:
        return desc
    return desc[: max_len - 1] + "…"


def simplify_parameters(schema: dict) -> dict:
    """Remove optional parameters from a JSON schema object."""
    if not isinstance(schema, dict):
        return schema

    required = set(schema.get("required", []))
    props = schema.get("properties", {})

    simplified_props = {}
    for key, value in props.items():
        if key in required:
            # Recurse into nested objects
            if isinstance(value, dict) and value.get("type") == "object":
                value = simplify_parameters(value)
            simplified_props[key] = value

    result = {k: v for k, v in schema.items() if k != "properties"}
    if simplified_props:
        result["properties"] = simplified_props
    # Keep required list consistent
    if "required" in result:
        result["required"] = [r for r in result["required"] if r in simplified_props]
    return result


def simplify_tools(tools: list[dict], max_tools: int) -> list[dict]:
    """Cap tool count and strip verbose descriptions / optional params."""
    capped = tools[:max_tools]
    simplified = []
    for tool in capped:
        t = dict(tool)
        if t.get("type") == "function" and isinstance(t.get("function"), dict):
            fn = dict(t["function"])
            if "description" in fn:
                fn["description"] = truncate_description(fn["description"])
            if "parameters" in fn:
                fn["parameters"] = simplify_parameters(fn["parameters"])
            t["function"] = fn
        simplified.append(t)
    return simplified


# ---------------------------------------------------------------------------
# Context window monitoring
# ---------------------------------------------------------------------------

def estimate_tokens(obj: Any) -> int:
    """Rough token estimate: 4 chars ≈ 1 token."""
    return len(json.dumps(obj, ensure_ascii=False)) // 4


def check_context_budget(req_body: dict, warn_threshold: float = 0.4, max_context: int = 80000) -> dict | None:
    """
    Check if request is approaching the context budget.
    Returns a warning dict if over threshold, None if OK.
    Dex Horthy rule: context degrades at 40% of window.
    """
    total_tokens = estimate_tokens(req_body)
    budget = int(max_context * warn_threshold)

    if total_tokens > budget:
        usage_pct = total_tokens / max_context * 100
        return {
            "approx_tokens": total_tokens,
            "budget": budget,
            "max_context": max_context,
            "usage_percent": round(usage_pct, 1),
            "warning": f"Context at {usage_pct:.0f}% ({total_tokens}/{max_context} tokens). "
                       f"Quality may degrade. Consider /clear to reset context."
        }
    return None


# ---------------------------------------------------------------------------
# Context auto-truncation
# ---------------------------------------------------------------------------

def truncate_context(messages: list[dict], max_tokens: int = 24000) -> tuple[list[dict], bool]:
    """
    Auto-truncate conversation when context exceeds budget.
    Preserves: system messages, last 3 user/assistant pairs.
    Removes: oldest non-system messages first.
    """
    total = sum(estimate_tokens(m) for m in messages)
    if total <= max_tokens:
        return messages, False

    system_msgs = [m for m in messages if m.get("role") == "system"]
    conv_msgs = [m for m in messages if m.get("role") != "system"]

    keep_last = 6
    if len(conv_msgs) <= keep_last:
        return messages, False

    trimmed = list(conv_msgs)
    while len(trimmed) > keep_last:
        new_total = sum(estimate_tokens(m) for m in system_msgs + trimmed)
        if new_total <= max_tokens:
            break
        trimmed.pop(0)

    result = system_msgs + trimmed
    after_tokens = sum(estimate_tokens(m) for m in result)
    if len(result) < len(messages):
        logger.info(f"[{_ts()}] ✂ truncated: {len(messages)}→{len(result)} msgs, ~{after_tokens:,} tokens")
    return result, len(result) < len(messages)


# ---------------------------------------------------------------------------
# Smart tool filtering by mode
# ---------------------------------------------------------------------------

def filter_tools_by_mode(tools: list[dict], system_content: str) -> list[dict]:
    """Detect Roo Code mode from system message and filter tools to minimum set."""
    if not system_content or not tools:
        return tools

    content_lower = system_content.lower()
    mode_allowlist = {
        "coder": {"read_file", "apply_diff", "write_to_file", "search_and_replace",
                  "insert_content", "list_files", "attempt_completion"},
        "reader": {"read_file", "search_files", "list_files",
                   "list_code_definition_names", "attempt_completion"},
        "runner": {"read_file", "execute_command", "list_files", "attempt_completion"},
        "reviewer": {"read_file", "search_files", "list_files",
                     "list_code_definition_names", "attempt_completion"},
        "planner": {"read_file", "search_files", "list_files",
                    "list_code_definition_names", "attempt_completion"},
    }

    detected = None
    for mode in mode_allowlist:
        if mode in content_lower:
            detected = mode
            break

    if not detected:
        return tools

    allow = mode_allowlist[detected]
    filtered = [t for t in tools if t.get("function", {}).get("name", "") in allow]
    if filtered and len(filtered) < len(tools):
        logger.info(f"[{_ts()}] 🔧 {detected} mode: tools {len(tools)}→{len(filtered)}")
    return filtered if filtered else tools


# ---------------------------------------------------------------------------
# System prompt compression
# ---------------------------------------------------------------------------

def inject_diff_failure_guidance(messages: list[dict]) -> list[dict]:
    """
    Detect apply_diff failures in tool_results and inject guidance.
    When Roo Code returns 'No sufficiently similar match' or 'needs 100%',
    tell the model to read_file first before retrying.
    """
    diff_error_patterns = [
        "sufficiently similar match",
        "needs 100%",
        "similarity",
        "No match found",
        "search content does not match",
        "Invalid diff format",
        "missing required sections",
        "Unable to apply diff",
    ]

    found_diff_error = False
    target_file = None

    for msg in reversed(messages):
        content = ""
        if isinstance(msg.get("content"), str):
            content = msg["content"]
        elif isinstance(msg.get("content"), list):
            content = " ".join(
                block.get("content", "") or block.get("text", "")
                for block in msg["content"]
                if isinstance(block, dict)
            )

        if any(pattern in content for pattern in diff_error_patterns):
            found_diff_error = True
            # Try to extract file path from error message
            import re as _re
            path_match = _re.search(r'["\']?([^\s"\']+\.(java|xml|yml|yaml|properties|json|md|pc|h|c))["\']?', content)
            if path_match:
                target_file = path_match.group(1)
            break

    if found_diff_error:
        guidance = (
            "[FORGE] Previous apply_diff FAILED. To fix:\n"
            "1. Call read_file to get the EXACT current content of the file.\n"
            "2. Use the EXACT text from read_file in your diff.\n"
            "3. Diff format MUST be:\n"
            "<<<<<<< SEARCH\n:start_line: N\n-------\n[exact old text]\n=======\n[new text]\n>>>>>>> REPLACE\n"
            "Do NOT guess content. Do NOT use --- +++ @@ format."
        )
        if target_file:
            guidance += f" Target file: {target_file}"

        logger.info(f"[{_ts()}] 🔧 diff failure detected, injecting read_file guidance")

        # Inject as system message right before the last user message
        result = list(messages)
        # Find last user message position
        for i in range(len(result) - 1, -1, -1):
            if result[i].get("role") == "user":
                result.insert(i, {"role": "system", "content": guidance})
                break
        return result

    return messages


def compress_system_messages(messages: list[dict]) -> list[dict]:
    """
    Compress verbose system messages to save context budget.
    Targets Roo Code's environment_details and tool reminders.
    """
    compressed = []
    for msg in messages:
        if msg.get("role") != "system" and msg.get("role") != "user":
            compressed.append(msg)
            continue

        content = msg.get("content", "")
        if not isinstance(content, str):
            compressed.append(msg)
            continue

        original_len = len(content)

        # Remove verbose environment_details blocks (VSCode file listings)
        if "<environment_details>" in content:
            # Keep only essential parts, remove file tree
            import re as _re
            content = _re.sub(
                r'# Current Workspace Directory.*?(?=# Current Time|# Current Mode|</environment_details>)',
                '# Workspace: (file listing compressed by Forge)\n',
                content,
                flags=_re.DOTALL
            )
            # Remove VSCode visible files / open tabs
            content = _re.sub(
                r'# VSCode Visible Files.*?(?=# Current|</environment_details>)',
                '',
                content,
                flags=_re.DOTALL
            )

        # Remove repetitive todo reminders after first occurrence
        if "REMINDERS" in content and "update_todo_list" in content:
            # Keep only the table, remove the verbose instructions
            content = _re.sub(
                r'IMPORTANT: When task status changes.*?$',
                '',
                content,
                flags=_re.DOTALL | _re.MULTILINE
            )

        new_msg = dict(msg)
        new_msg["content"] = content

        saved = original_len - len(content)
        if saved > 100:
            logger.info(f"[{_ts()}] ✂ compressed system msg: saved {saved} chars (~{saved//4} tokens)")

        compressed.append(new_msg)
    return compressed


# ---------------------------------------------------------------------------
# Response repair
# ---------------------------------------------------------------------------

def sanitize_tool_name(name: str, valid_tools: set[str] | None = None) -> tuple[str, bool]:
    """
    Clean corrupted tool names from weak models.
    E.g. "update_todo_list<|channel|>commentary" → "update_todo_list"
         "functions.read_file" → "read_file"
         "write_file" → "write_to_file" (alias)
    Returns (cleaned_name, was_fixed).
    """
    if not name:
        return name, False

    original = name

    # Remove <|...|> tokens (common in weak model outputs)
    name = re.sub(r"<\|[^|]*\|>.*", "", name)

    # Remove "to=" prefix
    if name.startswith("to="):
        name = name[len("to="):]

    # Remove "functions." prefix (check after "to=" strip to handle "to=functions.xxx")
    if name.startswith("functions."):
        name = name[len("functions."):]

    # Keep only valid tool name chars (alphanumeric + underscore)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)

    # Apply aliases using candidates list (pick first match in valid_tools)
    if name in _TOOL_NAME_ALIAS_CANDIDATES:
        candidates = _TOOL_NAME_ALIAS_CANDIDATES[name]
        if valid_tools:
            for candidate in candidates:
                if candidate in valid_tools:
                    name = candidate
                    break
        else:
            name = candidates[0]

    # If name is still not in valid tools, search all candidates
    if valid_tools and name not in valid_tools:
        for alias, candidates in _TOOL_NAME_ALIAS_CANDIDATES.items():
            if alias in name:
                for candidate in candidates:
                    if candidate in valid_tools:
                        name = candidate
                        break
                if name in valid_tools:
                    break

    return name, name != original


# Tool name aliases: model outputs wrong name → map to correct one
# Aliases are resolved dynamically: target must exist in the request's tool list.
# Multiple candidates are listed — the first match in valid_tools wins.
_TOOL_NAME_ALIAS_CANDIDATES: dict[str, list[str]] = {
    "write_file": ["apply_diff", "write_to_file"],       # 3.51.x has apply_diff, 3.4.x has write_to_file
    "write_to_file": ["apply_diff", "write_file"],       # alias to apply_diff when available
    "create_file": ["write_to_file", "apply_diff"],
    "edit_file": ["apply_diff", "replace_in_file", "search_and_replace"],
    "run_command": ["execute_command"],
    "run": ["execute_command"],
    "search": ["search_files"],
    "find_files": ["search_files"],
    "list": ["list_files"],
    "complete": ["attempt_completion"],
    "ask": ["ask_followup_question"],
}

# Flat lookup built from candidates (first candidate is default)
_TOOL_NAME_ALIASES: dict[str, str] = {
    k: v[0] for k, v in _TOOL_NAME_ALIAS_CANDIDATES.items()
}


# Default values for required parameters when model omits them
_TOOL_PARAM_DEFAULTS: dict[str, dict[str, str]] = {
    "search_files": {"path": "."},
    "list_files": {"path": "."},
    "list_code_definition_names": {"path": "."},
    "read_file": {"path": ""},
    "execute_command": {"command": "echo 'no command specified'"},
    "ask_followup_question": {"follow_up": "How would you like to proceed?"},
}


def inject_missing_required_params(tool_name: str, args: dict, req_tools: list[dict]) -> tuple[dict, bool]:
    """
    If a required parameter is missing from tool call args, inject a default.
    Uses the tool schema from the request to determine required params.
    Falls back to _TOOL_PARAM_DEFAULTS for common tools.
    """
    fixed = False

    # Find the tool schema in the request
    schema_required: list[str] = []
    for tool in req_tools:
        fn = tool.get("function", {})
        if fn.get("name") == tool_name:
            schema_required = fn.get("parameters", {}).get("required", [])
            break

    # Check each required param
    defaults = _TOOL_PARAM_DEFAULTS.get(tool_name, {})
    for param in schema_required:
        if param not in args:
            default_val = defaults.get(param, "")
            if default_val:
                args[param] = default_val
                fixed = True
                logger.info(f"[{_ts()}] 🔧 injected missing param: {tool_name}.{param}={default_val!r}")

    return args, fixed


def repair_response(body: dict, req_tools: list[dict] | None = None) -> tuple[dict, bool]:
    """
    Inspect and repair tool_calls JSON inside a chat completion response.
    - Repairs malformed JSON in arguments
    - Sanitizes corrupted tool names
    - Injects missing required parameters
    Returns (repaired_body, was_repaired).
    """
    repaired = False
    if req_tools is None:
        req_tools = []

    # Build valid tool name set for alias resolution
    valid_tool_names = {t.get("function", {}).get("name", "") for t in req_tools if t.get("type") == "function"}

    choices = body.get("choices", [])
    for choice in choices:
        msg = choice.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        fixed_calls = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            tc = dict(tc)
            fn = dict(fn)

            # 1. Sanitize tool name
            raw_name = fn.get("name", "")
            clean_name, name_fixed = sanitize_tool_name(raw_name, valid_tools=valid_tool_names)
            if name_fixed:
                logger.info(f"[{_ts()}] 🔧 sanitized tool name: {raw_name!r} → {clean_name!r}")
                fn["name"] = clean_name
                repaired = True

            # 2. Repair JSON arguments
            args_str = fn.get("arguments", "")
            parsed_args = {}
            if isinstance(args_str, str) and args_str:
                parsed, was_fixed = repair_json(args_str)
                if parsed is not None:
                    parsed_args = parsed
                    if was_fixed:
                        fn["arguments"] = json.dumps(parsed)
                        repaired = True
                else:
                    parsed_args = {}
            elif isinstance(args_str, dict):
                parsed_args = args_str

            # 3. Transform arguments when tool was aliased (e.g. write_file → apply_diff)
            if name_fixed and clean_name == "apply_diff" and isinstance(parsed_args, dict):
                # Model sent write_file(path, content) → convert to apply_diff(path, diff)
                if "content" in parsed_args and "path" in parsed_args:
                    content = parsed_args["content"]
                    path = parsed_args["path"]
                    # Create a diff that adds the entire file content
                    diff_content = f"--- /dev/null\n+++ {path}\n@@ -0,0 +1 @@\n+{content}"
                    parsed_args = {"path": path, "diff": diff_content}
                    fn["arguments"] = json.dumps(parsed_args)
                    repaired = True
                    logger.info(f"[{_ts()}] 🔧 transformed write_file args → apply_diff format")

            # 4. Inject missing required parameters
            if clean_name and isinstance(parsed_args, dict):
                patched_args, params_fixed = inject_missing_required_params(clean_name, parsed_args, req_tools)
                if params_fixed:
                    fn["arguments"] = json.dumps(patched_args)
                    repaired = True

            tc["function"] = fn
            fixed_calls.append(tc)

        if repaired:
            msg = dict(msg)
            msg["tool_calls"] = fixed_calls
            choice["message"] = msg
    return body, repaired


def extract_tool_calls_from_text(body: dict, req_tools: list[dict] | None = None) -> tuple[dict, bool]:
    """
    NonNativeToolCallingMixin pattern: when a weak model outputs tool calls
    as plain text instead of structured tool_calls, extract and convert them.

    Detects patterns like:
    - to=functions.read_file ... {"path": "..."}
    - {"name": "write_to_file", "arguments": {"path": "...", "content": "..."}}
    - <|channel|> corrupted tool call attempts
    """
    if req_tools is None:
        req_tools = []

    # Build set of valid tool names from request
    valid_tools = set()
    for t in req_tools:
        fn = t.get("function", {})
        name = fn.get("name", "")
        if name:
            valid_tools.add(name)

    converted = False
    for choice in body.get("choices", []):
        msg = choice.get("message", {})

        # Only process if there's content but NO tool_calls
        if msg.get("tool_calls"):
            continue
        content = msg.get("content", "")
        if not content or not isinstance(content, str):
            continue

        # Strategy 1: Find "to=functions.<tool_name>" pattern
        match = re.search(r'to=functions\.(\w+).*?(\{.*)', content, re.DOTALL)
        if match:
            tool_name = match.group(1)
            json_part = match.group(2)
            # Clean the tool name
            tool_name, _ = sanitize_tool_name(tool_name)
            if tool_name in valid_tools:
                parsed, _ = repair_json(json_part)
                if parsed is not None:
                    msg["tool_calls"] = [{
                        "id": f"forge_extracted_{id(msg)}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(parsed)
                        }
                    }]
                    msg["content"] = None
                    converted = True
                    logger.info(f"[{_ts()}] 🔄 extracted tool call from text: {tool_name}")
                    continue

        # Strategy 2: Find {"name": "<tool>", "arguments": {...}} in content
        match = re.search(r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}', content, re.DOTALL)
        if match:
            tool_name = match.group(1)
            args_str = match.group(2)
            tool_name, _ = sanitize_tool_name(tool_name)
            if tool_name in valid_tools:
                parsed, _ = repair_json(args_str)
                if parsed is not None:
                    msg["tool_calls"] = [{
                        "id": f"forge_extracted_{id(msg)}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(parsed)
                        }
                    }]
                    msg["content"] = None
                    converted = True
                    logger.info(f"[{_ts()}] 🔄 extracted tool call from JSON in text: {tool_name}")
                    continue

        # Strategy 3: Find bare tool name followed by JSON (e.g. "read_file\n{...}")
        for tool_name in valid_tools:
            pattern = re.escape(tool_name) + r'\s*[\n:]*\s*(\{.*?\})'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                args_str = match.group(1)
                parsed, _ = repair_json(args_str)
                if parsed is not None:
                    msg["tool_calls"] = [{
                        "id": f"forge_extracted_{id(msg)}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(parsed)
                        }
                    }]
                    msg["content"] = None
                    converted = True
                    logger.info(f"[{_ts()}] 🔄 extracted tool call from bare name: {tool_name}")
                    break

        # If we found tool calls, update finish_reason
        if converted:
            choice["finish_reason"] = "tool_calls"

    return body, converted


def normalize_reasoning_response(body: dict) -> dict:
    """Some models put output in 'reasoning' instead of 'content'. Normalize."""
    for choice in body.get("choices", []):
        msg = choice.get("message", {})
        if not msg.get("content") and not msg.get("tool_calls"):
            # Check for reasoning field (OpenRouter gpt-oss pattern)
            reasoning = msg.get("reasoning")
            if reasoning and isinstance(reasoning, str):
                msg["content"] = reasoning
            elif msg.get("reasoning_details"):
                # Extract text from reasoning_details array
                texts = [d.get("text", "") for d in msg["reasoning_details"] if isinstance(d, dict)]
                combined = "\n".join(t for t in texts if t)
                if combined:
                    msg["content"] = combined
    return body


def response_has_content(body: dict) -> bool:
    """Return True if the response has either content or tool_calls."""
    for choice in body.get("choices", []):
        msg = choice.get("message", {})
        if msg.get("content"):
            return True
        if msg.get("tool_calls"):
            return True
    return False


def extract_response_detail(body: dict) -> str:
    """Build a short log detail from a response body."""
    for choice in body.get("choices", []):
        msg = choice.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            name = tool_calls[0].get("function", {}).get("name", "unknown")
            return f"tool_call: {name}"
        content = msg.get("content", "")
        if content:
            return f"content: {len(content)} chars"
    return "empty"


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Forge Proxy")


async def forward_request(
    method: str,
    path: str,
    headers: dict,
    body: bytes | None,
    timeout: int,
) -> httpx.Response:
    # Strip /v1 prefix from path if target already ends with /v1
    target = config.target.rstrip("/")
    if target.endswith("/v1") and path.startswith("/v1"):
        path = path[3:]  # remove leading /v1
    url = target + path
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.request(
            method=method,
            url=url,
            headers=headers,
            content=body,
        )


def build_upstream_headers(request: Request) -> dict:
    """Copy relevant headers and inject custom ones."""
    skip = {"host", "content-length", "transfer-encoding"}
    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in skip
    }
    if config.user_email:
        headers["X-USER-EMAIL"] = config.user_email
    return headers


@app.api_route("/v1/models", methods=["GET"])
async def proxy_models(request: Request) -> Response:
    """Passthrough for model discovery."""
    headers = build_upstream_headers(request)
    log_request(request.method, "/v1/models", 0)
    try:
        resp = await forward_request(
            method=request.method,
            path="/v1/models",
            headers=headers,
            body=None,
            timeout=config.timeout,
        )
    except httpx.TimeoutException:
        log_response(504, "timeout")
        return JSONResponse({"error": "upstream timeout"}, status_code=504)
    log_response(resp.status_code, "passthrough")
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type", "application/json"),
    )


@app.api_route("/v1/chat/completions", methods=["POST"])
async def proxy_chat_completions(request: Request) -> Response:
    """Main proxy endpoint with tool simplification, JSON repair, and retry."""
    raw_body = await request.body()

    # Parse request body
    try:
        req_body: dict = json.loads(raw_body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid request JSON"}, status_code=400)

    tools = req_body.get("tools", [])
    original_tool_count = len(tools)

    # Smart tool filtering by detected mode
    system_content = next((m.get("content", "") for m in req_body.get("messages", []) if m.get("role") == "system"), "")
    if tools and isinstance(system_content, str):
        tools = filter_tools_by_mode(tools, system_content)

    # Simplify remaining tools
    if tools:
        req_body["tools"] = simplify_tools(tools, config.max_tools)

    # Compress system messages to save context budget
    if "messages" in req_body:
        req_body["messages"] = compress_system_messages(req_body["messages"])

    # Detect diff failures and inject read_file guidance
    if "messages" in req_body:
        req_body["messages"] = inject_diff_failure_guidance(req_body["messages"])

    # Auto-truncate if context too large
    if "messages" in req_body:
        req_body["messages"], was_truncated = truncate_context(req_body["messages"])

    # Check context budget
    budget_warning = check_context_budget(req_body)
    if budget_warning:
        logger.warning(f"[{_ts()}] ⚠ {budget_warning['warning']}")
        # Inject warning into system message so the model knows to wrap up
        if budget_warning["usage_percent"] > 70:
            req_body.setdefault("messages", []).insert(0, {
                "role": "system",
                "content": (
                    f"[FORGE WARNING] Context at {budget_warning['usage_percent']:.0f}% "
                    f"({budget_warning['approx_tokens']:,} tokens). "
                    "Finish current file and use attempt_completion. "
                    "User should start a New Task for remaining work."
                )
            })

    log_request(request.method, "/v1/chat/completions", len(req_body.get("tools", [])))

    headers = build_upstream_headers(request)

    # When tools are present and streaming is requested:
    # Fetch as non-streaming from upstream, repair, then re-emit as streaming to client
    original_stream = req_body.get("stream", False)
    if original_stream and req_body.get("tools"):
        req_body["stream"] = False
        logger.info(f"[{_ts()}] 🔧 fetching non-streaming for repair, will re-emit as SSE")

        # Run the full non-streaming repair pipeline below, then wrap result as SSE
        # (fall through to the non-streaming code path, but wrap response at the end)

    # Streaming: passthrough for non-tool requests only
    if req_body.get("stream"):
        from starlette.responses import StreamingResponse

        target_url = config.target.rstrip("/")
        path = "/chat/completions" if target_url.endswith("/v1") else "/v1/chat/completions"

        def transform_sse_chunk(raw: bytes) -> bytes:
            """Rewrite reasoning → content in SSE stream chunks."""
            lines = raw.split(b"\n")
            out_lines = []
            for line in lines:
                if line.startswith(b"data: ") and not line.startswith(b"data: [DONE]"):
                    try:
                        payload = json.loads(line[6:])
                        for choice in payload.get("choices", []):
                            delta = choice.get("delta", {})
                            # Move reasoning to content if content is empty
                            content = delta.get("content")
                            reasoning = delta.get("reasoning")
                            if (not content or content == "") and reasoning:
                                delta["content"] = reasoning
                            # Also handle reasoning_details
                            if (not delta.get("content")) and delta.get("reasoning_details"):
                                texts = [d.get("text", "") for d in delta["reasoning_details"] if isinstance(d, dict)]
                                combined = "".join(texts)
                                if combined:
                                    delta["content"] = combined
                        out_lines.append(b"data: " + json.dumps(payload).encode())
                    except (json.JSONDecodeError, TypeError):
                        out_lines.append(line)
                else:
                    out_lines.append(line)
            return b"\n".join(out_lines)

        async def stream_generator():
            client = httpx.AsyncClient(timeout=config.timeout)
            try:
                req = client.build_request(
                    "POST",
                    target_url + path,
                    headers=headers,
                    content=json.dumps(req_body).encode(),
                )
                resp = await client.send(req, stream=True)
                async for chunk in resp.aiter_bytes():
                    yield transform_sse_chunk(chunk)
                await resp.aclose()
            except httpx.TimeoutException:
                yield b'data: {"error":"upstream timeout"}\n\n'
            finally:
                await client.aclose()

        log_response(200, "stream passthrough")
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
        )

    max_retries = 2
    backoff = 1.0

    for attempt in range(max_retries + 1):
        try:
            resp = await forward_request(
                method="POST",
                path="/v1/chat/completions",
                headers=headers,
                body=json.dumps(req_body).encode(),
                timeout=config.timeout,
            )
        except httpx.TimeoutException:
            log_response(504, "timeout")
            return JSONResponse({"error": "upstream timeout"}, status_code=504)

        if resp.status_code != 200:
            log_response(resp.status_code, "upstream error")
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )

        # Parse response
        try:
            resp_body: dict = json.loads(resp.content)
        except json.JSONDecodeError:
            raw_text = resp.content.decode(errors="replace")
            logger.warning(f"[{_ts()}] ⚠ Raw response (first 500 chars): {raw_text[:500]}")
            repaired, ok = repair_json(raw_text)
            if ok and repaired is not None:
                resp_body = repaired
            else:
                if attempt < max_retries:
                    error_msg = {
                        "role": "system",
                        "content": "Previous response had unfixable JSON. Please respond again.",
                    }
                    req_body.setdefault("messages", []).append(error_msg)
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                log_response(500, "unfixable JSON")
                return JSONResponse({"error": "unfixable upstream JSON"}, status_code=500)

        # Normalize reasoning-only responses
        resp_body = normalize_reasoning_response(resp_body)

        # Repair tool_calls JSON
        resp_body, was_repaired = repair_response(resp_body, req_tools=req_body.get("tools", []))

        # Extract tool calls from text content (NonNativeToolCallingMixin pattern)
        resp_body, was_extracted = extract_tool_calls_from_text(resp_body, req_tools=req_body.get("tools", []))
        if was_extracted:
            was_repaired = True

        # Retry if empty response
        if not response_has_content(resp_body):
            if attempt < max_retries:
                logger.info(f"[{_ts()}] ↺ empty response, retrying ({attempt + 1}/{max_retries})")
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            # Last attempt: return as-is
            log_response(200, "empty (exhausted retries)")
            log_to_file(req_body, resp_body, attempt=attempt, was_repaired=False, error="empty response")
            return JSONResponse(resp_body)

        detail = extract_response_detail(resp_body)
        if was_repaired:
            detail += " [repaired]"
        log_response(200, detail)
        log_to_file(req_body, resp_body, attempt=attempt, was_repaired=was_repaired)

        # If client requested streaming, convert response to proper SSE chunk format
        if original_stream:
            from starlette.responses import StreamingResponse

            # Convert chat.completion to chat.completion.chunk format
            chunk_body = dict(resp_body)
            chunk_body["object"] = "chat.completion.chunk"
            for choice in chunk_body.get("choices", []):
                msg = choice.pop("message", {})
                choice["delta"] = msg

            async def sse_chunks():
                yield f"data: {json.dumps(chunk_body)}\n\n".encode()
                yield b"data: [DONE]\n\n"

            return StreamingResponse(sse_chunks(), media_type="text/event-stream")

        return JSONResponse(resp_body)

    # Should not reach here
    log_to_file(req_body, {}, attempt=max_retries, was_repaired=False, error="max retries exceeded")
    return JSONResponse({"error": "max retries exceeded"}, status_code=502)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forge: Intelligent GPT-OSS proxy")
    parser.add_argument(
        "--target",
        default=os.environ.get("FORGE_TARGET", "http://localhost:11434/v1"),
        help="Upstream base URL (default: http://localhost:11434/v1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FORGE_PORT", "8080")),
        help="Port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--header",
        metavar="KEY:VALUE",
        help="Custom header to inject, e.g. X-USER-EMAIL:user@company.com",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("FORGE_TIMEOUT", "60")),
        help="Upstream request timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--max-tools",
        type=int,
        default=int(os.environ.get("FORGE_MAX_TOOLS", "8")),
        help="Maximum number of tools to forward (default: 8)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("FORGE_HOST", "127.0.0.1"),
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--log-dir",
        default=os.environ.get("FORGE_LOG_DIR", ""),
        help="Directory to save request/response logs (default: disabled)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    args = parse_args()

    config.target = args.target
    config.port = args.port
    config.timeout = args.timeout
    config.max_tools = args.max_tools
    config.host = args.host
    config.log_dir = args.log_dir

    if args.header:
        if ":" in args.header:
            key, _, value = args.header.partition(":")
            if key.upper() == "X-USER-EMAIL":
                config.user_email = value
        else:
            logger.warning(f"Ignoring malformed --header value: {args.header!r}")

    if not config.user_email:
        config.user_email = os.environ.get("FORGE_USER_EMAIL", "")

    logger.info(f"[{_ts()}] Forge starting → target={config.target} port={config.port} max_tools={config.max_tools}")

    uvicorn.run(app, host=config.host, port=config.port)
