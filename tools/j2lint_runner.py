"""Entry point for running j2lint."""

from __future__ import annotations

import sys

from j2lint import cli

sys.exit(cli.run())
