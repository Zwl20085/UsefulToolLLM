"""
Entry point for the IEEE Early Access paper viewer.

Usage:
    python main.py                        # uses default journals, opens browser
    python main.py --port 8080            # custom port
    python main.py --no-browser           # skip auto-open
"""

import argparse
import logging

from ieee_early_access.server import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IEEE Early Access Paper Viewer")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(host=args.host, port=args.port, open_browser=not args.no_browser)
