"""Backfill sparse context v2 enrollment for existing accepted cards.

Usage: uv run python -m backend.canvas.opora_sparse_backfill [--data DIR] [--project P] [--workspace W] [--dry-run]
Idempotent: cards already enrolled are skipped; --dry-run lists what would be enrolled and writes nothing."""
import argparse
import json
import os
import sys

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_sparse_enrollment import backfill


def main(argv=None):
    parser = argparse.ArgumentParser(description="Enroll accepted cards into sparse context v2.")
    parser.add_argument("--data", default=os.environ.get("OPORA_CANVAS_DATA", ".data/production"))
    parser.add_argument("--project")
    parser.add_argument("--workspace")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    service = CanvasService(args.data)
    try:
        result = backfill(service, args.project, args.workspace, dry_run=args.dry_run)
    finally:
        service.close()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
