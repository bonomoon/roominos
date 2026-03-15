"""
Tests for Forge proxy.

All upstream HTTP calls are mocked — no real server needed.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient, Response as HttpxResponse
from fastapi.testclient import TestClient

from forge import (
    app,
    config,
    fix_missing_closing,
    fix_trailing_commas,
    repair_json,
    simplify_tools,
    repair_response,
    response_has_content,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_chat_response(content: str | None = None, tool_calls: list | None = None) -> dict:
    msg: dict = {"role": "assistant"}
    if content is not None:
        msg["content"] = content
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def make_tool_call(name: str, arguments: str) -> dict:
    return {
        "id": "call_test",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def make_upstream_response(body: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


# ---------------------------------------------------------------------------
# Unit tests: JSON repair
# ---------------------------------------------------------------------------

def test_fix_missing_bracket():
    """JSON with missing closing } should be repaired."""
    broken = '{"key": "value"'
    fixed, repaired = repair_json(broken)
    assert repaired is True
    assert fixed == {"key": "value"}


def test_fix_trailing_comma():
    """JSON with trailing comma before } should be repaired."""
    broken = '{"a": 1, "b": 2,}'
    fixed, repaired = repair_json(broken)
    assert repaired is True
    assert fixed == {"a": 1, "b": 2}


def test_fix_truncated_tool_call():
    """Incomplete tool_calls JSON (truncated mid-object) should be repaired."""
    # Simulates a truncated argument string
    truncated = '{"path": "/tmp/foo", "content": "hello"'
    fixed, repaired = repair_json(truncated)
    assert repaired is True
    assert fixed["path"] == "/tmp/foo"
    assert fixed["content"] == "hello"


def test_valid_json_not_marked_repaired():
    """Valid JSON should parse without being marked as repaired."""
    valid = '{"key": "value"}'
    parsed, repaired = repair_json(valid)
    assert repaired is False
    assert parsed == {"key": "value"}


def test_fix_missing_closing_nested():
    """Nested structures with missing closers should be repaired."""
    broken = '[{"a": 1}, {"b": 2'
    result = fix_missing_closing(broken)
    assert result.endswith("}]")
    parsed = json.loads(result)
    assert len(parsed) == 2


def test_fix_trailing_comma_array():
    """Trailing comma inside array should be removed."""
    broken = "[1, 2, 3,]"
    result = fix_trailing_commas(broken)
    assert result == "[1, 2, 3]"


# ---------------------------------------------------------------------------
# Unit tests: tool simplification
# ---------------------------------------------------------------------------

def test_tool_simplification():
    """Tool count should be capped and optional params removed."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": f"tool_{i}",
                "description": "A" * 150,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "required_param": {"type": "string"},
                        "optional_param": {"type": "string"},
                    },
                    "required": ["required_param"],
                },
            },
        }
        for i in range(12)
    ]

    result = simplify_tools(tools, max_tools=8)

    # Count capped
    assert len(result) == 8

    # Descriptions truncated to <= 100 chars
    for t in result:
        assert len(t["function"]["description"]) <= 100

    # Optional params removed
    for t in result:
        params = t["function"]["parameters"]
        assert "required_param" in params["properties"]
        assert "optional_param" not in params["properties"]


def test_tool_simplification_preserves_required_params():
    """Required parameters must survive simplification."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "File content"},
                        "encoding": {"type": "string", "description": "Optional encoding"},
                    },
                    "required": ["path", "content"],
                },
            },
        }
    ]

    result = simplify_tools(tools, max_tools=8)
    props = result[0]["function"]["parameters"]["properties"]
    assert "path" in props
    assert "content" in props
    assert "encoding" not in props


# ---------------------------------------------------------------------------
# Unit tests: response analysis
# ---------------------------------------------------------------------------

def test_response_has_content_with_text():
    body = make_chat_response(content="Hello world")
    assert response_has_content(body) is True


def test_response_has_content_with_tool_calls():
    body = make_chat_response(tool_calls=[make_tool_call("read_file", '{"path": "/tmp/x"}')])
    assert response_has_content(body) is True


def test_response_has_content_empty():
    body = make_chat_response(content=None, tool_calls=None)
    assert response_has_content(body) is False


def test_repair_response_fixes_truncated_args():
    """repair_response should fix truncated tool_call arguments."""
    body = make_chat_response(
        tool_calls=[make_tool_call("write_file", '{"path": "/tmp/foo"')]
    )
    repaired_body, was_repaired = repair_response(body)
    assert was_repaired is True
    args = json.loads(
        repaired_body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    assert args["path"] == "/tmp/foo"


# ---------------------------------------------------------------------------
# Integration tests: FastAPI endpoints (mocked upstream)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to known defaults before each test."""
    config.target = "http://fake-upstream/v1"
    config.user_email = "test@example.com"
    config.timeout = 5
    config.max_tools = 8
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_header_injection(client):
    """Verify X-USER-EMAIL header is injected into upstream requests."""
    config.user_email = "injected@example.com"

    captured_headers = {}

    async def mock_request(*args, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        body = make_chat_response(content="OK")
        return make_upstream_response(body)

    with patch("forge.forward_request", side_effect=mock_request):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert captured_headers.get("X-USER-EMAIL") == "injected@example.com"


def test_passthrough_valid_response(client):
    """Valid responses with content should pass through unchanged."""
    upstream_body = make_chat_response(content="Hello from upstream!")

    async def mock_request(*args, **kwargs):
        return make_upstream_response(upstream_body)

    with patch("forge.forward_request", side_effect=mock_request):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "Hello from upstream!"


def test_retry_on_empty_response(client):
    """Should retry up to 2 times when response has no content and no tool_calls."""
    call_count = 0
    empty_body = make_chat_response(content=None, tool_calls=None)
    # content key is already absent when content=None (make_chat_response skips it)

    async def mock_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return make_upstream_response(empty_body)
        # Third attempt returns content
        return make_upstream_response(make_chat_response(content="Finally got content"))

    with patch("forge.forward_request", side_effect=mock_request):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
            )

    assert resp.status_code == 200
    assert call_count == 3
    assert resp.json()["choices"][0]["message"]["content"] == "Finally got content"


def test_tool_count_reduced_in_request(client):
    """Forge should cap tools before forwarding."""
    captured_body = {}

    async def mock_request(*args, **kwargs):
        nonlocal captured_body
        captured_body = json.loads(kwargs["body"])
        return make_upstream_response(make_chat_response(content="ok"))

    tools = [
        {"type": "function", "function": {"name": f"tool_{i}", "description": "desc", "parameters": {"type": "object", "properties": {}, "required": []}}}
        for i in range(12)
    ]

    config.max_tools = 5

    with patch("forge.forward_request", side_effect=mock_request):
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "tools": tools,
            },
        )

    assert resp.status_code == 200
    assert len(captured_body["tools"]) == 5


def test_upstream_error_passthrough(client):
    """Non-200 upstream responses should be returned as-is."""
    async def mock_request(*args, **kwargs):
        return httpx.Response(
            status_code=503,
            content=b'{"error": "service unavailable"}',
            headers={"content-type": "application/json"},
        )

    with patch("forge.forward_request", side_effect=mock_request):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 503


def test_timeout_returns_504(client):
    """Upstream timeout should return 504."""
    async def mock_request(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    with patch("forge.forward_request", side_effect=mock_request):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 504
    assert "timeout" in resp.json()["error"]


def test_models_passthrough(client):
    """GET /v1/models should proxy to upstream without modification."""
    models_body = {"object": "list", "data": [{"id": "gpt-4", "object": "model"}]}

    async def mock_request(*args, **kwargs):
        return make_upstream_response(models_body)

    with patch("forge.forward_request", side_effect=mock_request):
        resp = client.get("/v1/models")

    assert resp.status_code == 200
    assert resp.json()["data"][0]["id"] == "gpt-4"
