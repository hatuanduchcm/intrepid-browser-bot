import json
from pathlib import Path
from typing import Dict

CACHE_PATH = Path(__file__).resolve().parents[2] / 'assets' / 'debug_matches' / 'twofa_cache.json'


def _load_cache() -> Dict[str, bool]:
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding='utf-8') or '{}')
    except Exception:
        pass
    return {}


def _save_cache(data: Dict[str, bool]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def is_brand_verified(brand_name: str) -> bool:
    if not brand_name:
        return False
    data = _load_cache()
    return bool(data.get(str(brand_name).strip().lower()))


def mark_brand_verified(brand_name: str) -> None:
    if not brand_name:
        return
    data = _load_cache()
    data[str(brand_name).strip().lower()] = True
    _save_cache(data)
