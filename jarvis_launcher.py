"""PyInstaller entry point (keeps ``python -m jarvis`` working too)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from jarvis.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
