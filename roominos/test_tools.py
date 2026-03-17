"""Tests for TextToolExecutor"""
import os
import tempfile
import pytest
from roominos.tools import TextToolExecutor, ToolResult

def test_extract_code_from_fences():
    executor = TextToolExecutor()
    text = "Here is the code:\n```java\npublic class Foo {}\n```\nDone."
    assert executor.extract_code(text) == "public class Foo {}"

def test_extract_code_plain():
    executor = TextToolExecutor()
    text = "public class Foo {}"
    assert executor.extract_code(text) == "public class Foo {}"

def test_parse_file_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = TextToolExecutor(base_dir=tmpdir)
        model_output = 'FILE: src/Foo.java\n```java\npublic class Foo {}\n```'
        results = executor.execute_all(model_output)

        assert len(results) == 1
        assert results[0].tool == "file"
        assert results[0].success is True
        assert os.path.exists(os.path.join(tmpdir, "src/Foo.java"))

def test_parse_run_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = TextToolExecutor(base_dir=tmpdir)
        results = executor.execute_all("RUN: echo hello")

        assert len(results) == 1
        assert results[0].tool == "run"
        assert results[0].success is True
        assert "hello" in results[0].output

def test_parse_read_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file first
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "src/test.txt"), 'w') as f:
            f.write("hello world")

        executor = TextToolExecutor(base_dir=tmpdir)
        results = executor.execute_all("READ: src/test.txt")

        assert len(results) == 1
        assert results[0].success is True
        assert "hello world" in results[0].output

def test_block_dangerous_commands():
    executor = TextToolExecutor()
    results = executor.execute_all("RUN: rm -rf /")
    assert len(results) == 1
    assert results[0].success is False
    assert "Blocked" in results[0].output

def test_multiple_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = TextToolExecutor(base_dir=tmpdir)
        model_output = '''FILE: a.java
```java
class A {}
```

FILE: b.java
```java
class B {}
```

RUN: echo done'''

        results = executor.execute_all(model_output)
        assert len(results) == 3
        assert results[0].tool == "file"
        assert results[1].tool == "file"
        assert results[2].tool == "run"
