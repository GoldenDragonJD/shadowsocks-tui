"""CLI entry point for Shadowsocks TUI Client."""

import signal
import sys
from .app import ShadowsocksApp


def main():
    def handle_signal(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    app = ShadowsocksApp()
    app.run()


if __name__ == "__main__":
    main()
