"""Reconcile old sandbox records when no corresponding run is active."""

import argparse
import json

from merchant_agent.tools.python_runner import reconcile_pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-age-seconds", type=int, default=300)
    args = parser.parse_args()
    results = reconcile_pending(min_age_seconds=args.min_age_seconds)
    print(json.dumps([{"name": name, "status": status} for name, status in results], ensure_ascii=False))
    return int(any(status == "unresolved" for _, status in results))


if __name__ == "__main__":
    raise SystemExit(main())
