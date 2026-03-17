"""Text-based LLM client — no function calling, just prompts and responses."""
import httpx
import json
import time
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    tokens_used: int
    model: str


class LLMClient:
    def __init__(self, api_base: str, api_key: str, model: str, max_tokens: int = 3000, timeout: int = 90):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    def ask(self, prompt: str, system: str = "", max_retries: int = 3) -> LLMResponse:
        """Send a text prompt, get text response. Retries on connection errors."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        url = self.api_base
        if not url.endswith("/chat/completions"):
            if url.endswith("/v1"):
                url += "/chat/completions"
            else:
                url += "/v1/chat/completions"

        for attempt in range(max_retries):
            try:
                resp = httpx.post(url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": messages, "max_tokens": self.max_tokens},
                    timeout=self.timeout)

                data = resp.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content") or msg.get("reasoning") or ""
                tokens = data.get("usage", {}).get("total_tokens", 0)

                return LLMResponse(content=content, tokens_used=tokens, model=self.model)
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException,
                    httpx.RemoteProtocolError, httpx.HTTPStatusError, Exception) as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
                    continue
                return LLMResponse(content="", tokens_used=0, model=self.model)
