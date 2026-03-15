# Research References

## Core Workflow

- [RPI Workflow — Dex Horthy (HumanLayer)](https://humanlayer.dev/blog/rpi-workflow) — Context degrades at 40% of window; Research → Plan → Implement workflow [archived: originally shared via Dex Horthy's video/blog; URL may have changed]
- [How Boris Uses Claude Code](https://howborisusesclaudecode.com/) — 20-30 PRs/day workflow, plan mode first, verification loops
- [Claude Code Architecture Deep Dive](https://blog.promptlayer.com/claude-code-behind-the-scenes-of-the-master-agent-loop/) — Single-threaded master loop, sub-agent isolation

## Agent Orchestration for Weak Models

### Papers
- [Alpha-UMi: Small LLMs Are Weak Tool Learners (EMNLP 2024)](https://aclanthology.org/2024.emnlp-main.929/) — 7B model split into Planner/Caller/Summarizer outperforms 13B monolithic
- [ReWOO: Reasoning Without Observation](https://arxiv.org/abs/2305.18323) — Plan all tool calls upfront, 5x token efficiency
- [Plan-and-Act (2025)](https://arxiv.org/html/2503.09572v3) — Strong model plans, weak model executes
- [Difficulty-Aware Agent Orchestration (2025)](https://arxiv.org/html/2509.11079v1) — Route queries by difficulty to different models
- [Architecting Resilient Plan-then-Execute Agents (2025)](https://arxiv.org/abs/2509.08646) — Implementation blueprints for LangGraph, CrewAI, AutoGen

### Constrained Decoding
- [XGrammar](https://github.com/mlc-ai/xgrammar) — Default backend for vLLM/SGLang, 100x speedup
- [llguidance](https://github.com/guidance-ai/llguidance) — Microsoft, foundation for OpenAI Structured Outputs
- [Outlines](https://github.com/dottxt-ai/outlines) — Python library for enforcing JSON Schema during generation
- [LMQL](https://github.com/lmql-lang/lmql) — Query language with constrained generation, 75-85% token reduction
- [JSONSchemaBench](https://arxiv.org/abs/2501.10868) — Constrained decoding speeds up generation 50%, improves accuracy 4%

### Self-Correction and Retry
- [Reflexion (NeurIPS 2023)](https://arxiv.org/abs/2303.11366) — Verbal reinforcement learning with episodic memory
- [When Can LLMs Actually Correct Their Own Mistakes? (TACL 2025)](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00713/125177/) — External feedback >> self-reflection
- [LLMLOOP (ICSME 2025)](https://valerio-terragni.github.io/assets/pdf/ravi-icsme-2025.pdf) — Iterative refinement with compiler/test feedback
- [Reflect, Retry, Reward (2025)](https://arxiv.org/html/2505.24726) — RL for better self-reflections

## Agent Frameworks

- [SWE-agent](https://github.com/SWE-agent/SWE-agent) — Agent-Computer Interface, custom shell commands
- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) — 100 lines, bash-only, 74% on SWE-bench Verified
- [OpenHands](https://github.com/OpenHands/OpenHands) — Event-sourced, NonNativeToolCallingMixin for weak models
- [Agentless](https://github.com/OpenAutoCoder/Agentless) — No agent loop, fixed pipeline: Localize → Repair → Validate
- [Aider](https://github.com/Aider-AI/aider) — Text-based edit formats, adaptive by model capability
- [Goose](https://github.com/block/goose) — Rust, MCP-native tool abstraction

## Fine-Tuned Coding Models

- [SWE-agent-LM-32B](https://huggingface.co/SWE-bench/SWE-agent-LM-32B) — 40.2% SWE-bench Verified
- [DeepSWE-Preview](https://huggingface.co/agentica-org/DeepSWE-Preview) — 59.2% with RL training
- [Devstral Small 2 (24B)](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512) — 68.0% on consumer hardware
- [Gorilla / OpenFunctions-v2](https://github.com/ShishirPatil/gorilla) — Surpasses GPT-4 on API calling
- [ToolACE-8B (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/file/663865ea167425c6c562cb0b6bcf76c7-Paper-Conference.pdf) — Best 8B model on BFCL

## Cursor/Roo Code Rules

- [awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) — Community cursor rules, Java/Spring/JPA patterns
- [Java Spring Boot + JPA rules](https://github.com/PatrickJS/awesome-cursorrules/tree/main/rules/java-springboot-jpa-cursorrules-prompt-file) — Layered architecture rules with glob scoping

## Evaluation

- [SWE-bench](https://www.swebench.com/SWE-bench/) — Standard coding agent benchmark
- [FeatureBench (2026)](https://arxiv.org/abs/2602.10975) — Complex feature development benchmark
- [BFCL V4 Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html) — Function calling benchmark
- [Demystifying Evals for AI Agents (Anthropic)](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

## GitHub Automation

- [claude-code-action](https://github.com/anthropics/claude-code-action) — Claude Code as GitHub Action for PR review
- [codex-action](https://github.com/openai/codex-action) — OpenAI Codex as GitHub Action
- [CodeRabbit](https://docs.coderabbit.ai/) — AI-powered PR review (most-installed GitHub AI app)
- [GitHub Agentic Workflows](https://github.github.com/gh-aw/) — Native agent framework for GitHub Actions

## Model Routing

- [xRouter (2025)](https://arxiv.org/html/2510.08439v1) — Cost-aware RL routing across LLMs
- [FrugalGPT](https://arxiv.org/abs/2305.05176) — Cascading: cheap model first, escalate if needed
- [AutoMix (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/file/5503a7c69d48a2f86fc00b3dc09de686-Paper-Conference.pdf) — Self-verify, route to larger model on failure
- [awesome-ai-model-routing](https://github.com/Not-Diamond/awesome-ai-model-routing) — Curated list
