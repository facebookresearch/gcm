import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_version() -> str:
    if "__file__" in globals():
        root = Path(__file__).absolute().parent
        try:
            version = open(root / "version.txt").read().strip()
            return version
        except Exception:
            logger.info("Could not find version.txt file", exc_info=True)

    env_version = os.environ.get("GCM_VERSION")
    if env_version is not None:
        return env_version

    # do not fail due to not able to find version
    return "unknown"


__version__ = get_version()
