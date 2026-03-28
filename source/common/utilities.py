import sys
import os
from pathlib import Path

def resource_path(relative_path: str | Path) -> Path:
    """
    Get the absolute path to a resource, whether running as a script or as a PyInstaller exe.
    """
    try:
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    except AttributeError:
        base_path = Path(__file__).resolve().parent.parent.parent  # Adjust based on where this file is

    return base_path / relative_path

def log_to_screen(message, is_logging_enabled=True):
    """
    Log a message to the screen.
    """
    if is_logging_enabled:
        print(message)

def get_base_path() -> Path:
    """
    Returns the base path to use for loading assets.
    Works correctly when frozen with PyInstaller.
    """
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent  # Adjust depth if needed