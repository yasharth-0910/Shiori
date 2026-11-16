"""uv run python -m collector <source> [--limit N] [--bundles N] [--dry-run]

--limit caps the number of new files downloaded, --bundles the number of bundles
with new files. Bundles are taken whole, in the adapter's priority order (IT first),
so a run may stop below either limit.
"""

import argparse
import sys
from collections.abc import Callable
from functools import partial

from collector.collect import Candidate, run
from collector.http import BlockedError, PoliteClient
from collector.sources import digital, listing, pportal, sites

SOURCES: dict[str, Callable[[PoliteClient], list[Candidate]]] = {
    "digital": digital.discover,
    pportal.SOURCE: pportal.discover,
    **{site.source: partial(listing.discover, site=site) for site in sites.ALL},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m collector")
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument(
        "--limit", type=int, default=10, help="max new files (default 10)"
    )
    parser.add_argument("--bundles", type=int, help="max bundles with new files")
    parser.add_argument("--dry-run", action="store_true", help="list, don't download")
    args = parser.parse_args(argv)

    client = PoliteClient()
    try:
        candidates = SOURCES[args.source](client)
        run(
            args.source,
            candidates,
            client,
            args.limit,
            args.dry_run,
            max_bundles=args.bundles,
        )
    except BlockedError as e:  # D-17: skip the site, no workarounds
        print(f"blocked, skipping {args.source}: {e}", file=sys.stderr)
        return 1
    finally:
        print(f"HTTP requests made: {client.request_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
