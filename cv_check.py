"""Convenience entry point: ``python cv_check.py --cv cv.pdf --job job_ad.txt``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cv_ats_check.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
