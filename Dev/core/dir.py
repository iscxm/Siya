from pathlib import Path
from Dev import logger

def ensure_dirs():
    for d in ["cache", "downloads"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info("Cache directories updated.")
