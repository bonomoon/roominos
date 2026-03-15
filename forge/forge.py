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


config = Config()

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
# Response repair
# ---------------------------------------------------------------------------

def repair_response(body: dict) -> tuple[dict, bool]:
    """
    Inspect and repair tool_calls JSON inside a chat completion response.
    Returns (repaired_body, was_repaired).
    """
    repaired = False
    choices = body.get("choices", [])
    for choice in choices:
        msg = choice.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        fixed_calls = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            args_str = fn.get("arguments", "")
            if isinstance(args_str, str) and args_str:
                parsed, was_fixed = repair_json(args_str)
                if was_fixed and parsed is not None:
                    fn = dict(fn)
                    fn["arguments"] = json.dumps(parsed)
                    tc = dict(tc)
                    tc["function"] = fn
                    repaired = True
            fixed_calls.append(tc)
        if repaired:
            msg = dict(msg)
            msg["tool_calls"] = fixed_calls
            choice["message"] = msg
    return body, repaired


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
    url = config.target.rstrip("/") + path
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

    # Simplify tools
    if tools:
        req_body["tools"] = simplify_tools(tools, config.max_tools)

    log_request(request.method, "/v1/chat/completions", len(req_body.get("tools", [])))

    headers = build_upstream_headers(request)

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
            repaired, ok = repair_json(resp.content.decode(errors="replace"))
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

        # Repair tool_calls JSON
        resp_body, was_repaired = repair_response(resp_body)

        # Retry if empty response
        if not response_has_content(resp_body):
            if attempt < max_retries:
                logger.info(f"[{_ts()}] ↺ empty response, retrying ({attempt + 1}/{max_retries})")
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            # Last attempt: return as-is
            log_response(200, "empty (exhausted retries)")
            return JSONResponse(resp_body)

        detail = extract_response_detail(resp_body)
        if was_repaired:
            detail += " [repaired]"
        log_response(200, detail)
        return JSONResponse(resp_body)

    # Should not reach here
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
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    args = parse_args()

    config.target = args.target
    config.port = args.port
    config.timeout = args.timeout
    config.max_tools = args.max_tools
    config.host = args.host

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
