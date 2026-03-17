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

    # generate command
    gen = sub.add_parser("generate", help="Generate code from template")
    gen.add_argument("--template", required=True, choices=["entity", "service", "controller", "test"])
    gen.add_argument("--name", required=True)
    gen.add_argument("--output", required=True)

    args = parser.parse_args()

    if args.command == "migrate":
        run_migrate(args)
    elif args.command == "generate":
        run_generate(args)
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

    from .templates.migration import MigrationTemplate

    llm = LLMClient(api_base=args.api_base, api_key=args.api_key, model=args.model, max_tokens=args.max_tokens)
    template = MigrationTemplate(target_stack="Spring Boot 3.2, JDK 17, Spring Data JPA, Oracle")
    pipeline = Pipeline(llm=llm, output_dir=args.output, template=template)

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


def run_generate(args):
    print("Generate not yet implemented")


if __name__ == "__main__":
    main()
