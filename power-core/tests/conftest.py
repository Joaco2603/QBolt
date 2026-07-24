"""Make the src-layout imports work from the repository root or power-core/."""

from pathlib import Path
import sys


POWER_CORE = Path(__file__).parents[1]
SRC = POWER_CORE / "src"

for path in (str(POWER_CORE), str(SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)
