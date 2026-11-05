"""Opt-in external observer for the original Context/DSS deadline checks."""

import os

if os.environ.get("OPENBEXI_DEADLINE_TRACE"):
    import observer

    observer.install()
