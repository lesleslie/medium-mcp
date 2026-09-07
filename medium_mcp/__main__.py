"""medium-mcp CLI entry point.

Scaffold stub. Real entry point will dispatch to the FastMCP server
once the server module is implemented.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Placeholder entry point. Prints version and exits."""
    from medium_mcp import __version__

    print(f"medium-mcp {__version__} (scaffold — not yet implemented)")
    return 0


if __name__ == "__main__":
    sys.exit(main())