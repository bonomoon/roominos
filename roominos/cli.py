"""Roominos CLI — orchestration tool for weak LLMs"""
import argparse
import os
import sys
import time
from .llm import LLMClient
from .pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Roominos: Coding orchestration for weak LLMs")
    sub = parser.add_subparsers(dest="command")

    # migrate command
    migrate = sub.add_parser("migrate", help="Migrate source code to target platform")
    migrate.add_argument("--source", required=True, help="Source file(s) to migrate")
    migrate.add_argument("--output", required=True, help="Output directory")
    migrate.add_argument("--model", default=os.environ.get("ROOMINOS_MODEL", "openai/gpt-oss-20b"))
    migrate.add_argument("--api-base", default=os.environ.get("ROOMINOS_API_BASE", "https://openrouter.ai/api/v1"))
    migrate.add_argument("--api-key", default=os.environ.get("ROOMINOS_API_KEY", os.environ.get("OPENAI_API_KEY", "")))
    migrate.add_argument("--max-tokens", type=int, default=3000)
    migrate.add_argument("--skill", default="migration", choices=["migration", "greenfield", "refactor", "test-gen", "review"])

    # generate command
    gen = sub.add_parser("generate", help="Generate code from template")
    gen.add_argument("--template", required=True, choices=["entity", "service", "controller", "test"])
    gen.add_argument("--name", required=True)
    gen.add_argument("--output", required=True)

    # project command
    proj = sub.add_parser("project", help="Migrate an entire project directory")
    proj.add_argument("--source-dir", required=True, help="Source directory with .pc/.c/.h files")
    proj.add_argument("--output", required=True, help="Output directory")
    proj.add_argument("--model", default=os.environ.get("ROOMINOS_MODEL", "openai/gpt-oss-20b"))
    proj.add_argument("--api-base", default=os.environ.get("ROOMINOS_API_BASE", "https://openrouter.ai/api/v1"))
    proj.add_argument("--api-key", default=os.environ.get("ROOMINOS_API_KEY", os.environ.get("OPENAI_API_KEY", "")))
    proj.add_argument("--max-tokens", type=int, default=4000)
    proj.add_argument("--skill", default="migration", choices=["migration", "greenfield", "refactor", "test-gen", "review"])

    args = parser.parse_args()

    if args.command == "migrate":
        run_migrate(args)
    elif args.command == "generate":
        run_generate(args)
    elif args.command == "project":
        run_project(args)
    else:
        parser.print_help()


def run_migrate(args):
    if not args.api_key:
        print("ERROR: Set ROOMINOS_API_KEY or --api-key")
        sys.exit(1)

    print(f"{'='*50}")
    print(f"  Roominos Migration")
    print(f"{'='*50}")
    print(f"  Source: {args.source}")
    print(f"  Output: {args.output}")
    print(f"  Model:  {args.model}")
    print(f"{'='*50}")

    with open(args.source) as f:
        source = f.read()

    from .templates.registry import get_skill

    llm = LLMClient(api_base=args.api_base, api_key=args.api_key, model=args.model, max_tokens=args.max_tokens)
    skill = get_skill(args.skill)
    pipeline = Pipeline(llm=llm, output_dir=args.output, template=skill)

    start = time.time()
    results = pipeline.run(source, source_path=args.source)
    elapsed = time.time() - start

    print(f"\n{'='*50}")
    print(f"  Results ({elapsed:.1f}s, {pipeline.total_tokens:,} tokens)")
    print(f"{'='*50}")
    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"  [{status}] {r.stage}: {r.output[:80]} ({r.tokens_used:,} tokens)")
    print(f"{'='*50}")


def run_project(args):
    from .templates.registry import get_skill
    from .project import ProjectPipeline

    if not args.api_key:
        print("ERROR: Set ROOMINOS_API_KEY or --api-key")
        sys.exit(1)

    print(f"{'='*50}")
    print(f"  Roominos Project Migration")
    print(f"{'='*50}")
    print(f"  Source: {args.source_dir}")
    print(f"  Output: {args.output}")
    print(f"  Model:  {args.model}")
    print(f"{'='*50}")

    llm = LLMClient(api_base=args.api_base, api_key=args.api_key, model=args.model, max_tokens=args.max_tokens)
    skill = get_skill(args.skill)
    project = ProjectPipeline(llm=llm, output_dir=args.output, template=skill)

    start = time.time()
    results = project.run(args.source_dir)
    elapsed = time.time() - start

    print(f"\n{'='*50}")
    print(f"  Project Results ({elapsed:.1f}s, {project.total_tokens:,} tokens)")
    print(f"{'='*50}")
    print(project.format_report())
    print(f"{'='*50}")


def run_generate(args):
    print("Generate not yet implemented")


if __name__ == "__main__":
    main()
