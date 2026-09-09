"""Directory consent checks shared by capture and document read endpoints."""
from pathlib import Path


def source_authorized(path: str, config: dict) -> bool:
    if not config.get("enabled") or not config.get("sources", {}).get("directory"):
        return False
    source = Path(path)
    return source.is_absolute() and source.is_file() and any(
        source.resolve().parent == Path(directory).resolve()
        for directory in config.get("directories", []))
