"""
Text-based tool executor — parse model output for FILE/RUN/READ patterns.
No JSON function calling. The model outputs plain text with markers.
"""
import os
import re
import subprocess
from dataclasses import dataclass

@dataclass
class ToolResult:
    tool: str  # "file", "run", "read"
    path: str
    success: bool
    output: str

class TextToolExecutor:
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir

    def execute_all(self, model_output: str) -> list[ToolResult]:
        """Parse model output and execute all tool calls found."""
        results = []

        # Parse FILE: blocks
        for match in re.finditer(r'FILE:\s*(.+?)\n```[\w]*\n(.*?)```', model_output, re.DOTALL):
            path = match.group(1).strip()
            content = match.group(2)
            result = self._write_file(path, content)
            results.append(result)

        # Parse RUN: commands
        for match in re.finditer(r'RUN:\s*(.+)', model_output):
            command = match.group(1).strip()
            result = self._run_command(command)
            results.append(result)

        # Parse READ: requests
        for match in re.finditer(r'READ:\s*(.+)', model_output):
            path = match.group(1).strip()
            result = self._read_file(path)
            results.append(result)

        return results

    def extract_code(self, text: str) -> str:
        """Extract code from markdown fences or return raw text."""
        # Try to extract from ```...```
        match = re.search(r'```[\w]*\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to extract from FILE: block
        match = re.search(r'FILE:\s*.+?\n```[\w]*\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Return as-is, stripping leading/trailing whitespace
        return text.strip()

    def _write_file(self, rel_path: str, content: str) -> ToolResult:
        """Write content to a file."""
        try:
            full_path = os.path.join(self.base_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            return ToolResult(tool="file", path=rel_path, success=True, output=f"Created {rel_path} ({len(content)} chars)")
        except Exception as e:
            return ToolResult(tool="file", path=rel_path, success=False, output=str(e))

    def _run_command(self, command: str) -> ToolResult:
        """Run a shell command."""
        # Safety: block dangerous commands
        dangerous = ["rm -rf /", "rm -rf ~", "format", "mkfs", "dd if="]
        if any(d in command for d in dangerous):
            return ToolResult(tool="run", path=command, success=False, output="Blocked: dangerous command")

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=60, cwd=self.base_dir
            )
            output = result.stdout + result.stderr
            return ToolResult(tool="run", path=command, success=result.returncode == 0, output=output[:2000])
        except subprocess.TimeoutExpired:
            return ToolResult(tool="run", path=command, success=False, output="Timeout (60s)")
        except Exception as e:
            return ToolResult(tool="run", path=command, success=False, output=str(e))

    def _read_file(self, rel_path: str) -> ToolResult:
        """Read a file's content."""
        try:
            full_path = os.path.join(self.base_dir, rel_path)
            with open(full_path) as f:
                content = f.read()
            # Truncate if too large
            if len(content.split('\n')) > 200:
                lines = content.split('\n')
                content = '\n'.join(lines[:50]) + f"\n\n... [{len(lines) - 100} lines truncated] ...\n\n" + '\n'.join(lines[-50:])
            return ToolResult(tool="read", path=rel_path, success=True, output=content)
        except FileNotFoundError:
            return ToolResult(tool="read", path=rel_path, success=False, output=f"File not found: {rel_path}")
        except Exception as e:
            return ToolResult(tool="read", path=rel_path, success=False, output=str(e))
