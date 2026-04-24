"""Utilities package for intrepid-browser-bot.
This file makes `utils` an importable package for helper modules.

It also re-exports legacy helpers from the top-level `utils.py` so existing
imports like `from utils import get_intrepid_window` continue to work.
"""
from pathlib import Path
import importlib.util

__all__ = ["ocr", "get_desktop"]


