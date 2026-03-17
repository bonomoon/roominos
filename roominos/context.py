"""Context budget manager — chunk large files, summarize between stages."""

class ContextBudget:
    def __init__(self, max_tokens: int = 24000, chars_per_token: int = 4):
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.used_tokens = 0

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // self.chars_per_token

    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    def use(self, tokens: int) -> None:
        self.used_tokens += tokens

    def reset(self) -> None:
        self.used_tokens = 0

    def chunk_text(self, text: str, max_lines: int = 200) -> list[str]:
        """Split text into chunks that fit within budget."""
        lines = text.split('\n')
        if len(lines) <= max_lines:
            return [text]

        chunks = []
        for i in range(0, len(lines), max_lines):
            chunk = '\n'.join(lines[i:i + max_lines])
            chunks.append(chunk)
        return chunks

    def summarize(self, text: str, max_chars: int = 3000) -> str:
        """Truncate text to fit within budget. Keep first and last parts."""
        if len(text) <= max_chars:
            return text

        half = max_chars // 2
        return text[:half] + f"\n\n... [truncated {len(text) - max_chars} chars] ...\n\n" + text[-half:]

    def fits(self, text: str) -> bool:
        """Check if text fits within remaining budget."""
        return self.estimate_tokens(text) <= self.remaining()

    def trim_to_budget(self, text: str) -> str:
        """Trim text to fit within remaining budget."""
        max_chars = self.remaining() * self.chars_per_token
        if len(text) <= max_chars:
            return text
        return self.summarize(text, max_chars=max_chars)
