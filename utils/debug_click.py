import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


def save_last_search_click(x, y, fname: str = 'last_search_click.json'):
    """Save click coordinates to assets/debug_matches/<fname> (overwrites).

    Casts to int to avoid numpy types when serializing.
    """
    try:
        dbg = Path(__file__).resolve().parents[2] / 'assets' / 'debug_matches'
        dbg.mkdir(parents=True, exist_ok=True)
        outp = dbg / fname
        x_val = int(x)
        y_val = int(y)
        with outp.open('w', encoding='utf-8') as fh:
            json.dump({'x': x_val, 'y': y_val}, fh)
        logger.debug('Wrote %s to %s (%s,%s)', fname, outp, x_val, y_val)
        return True
    except Exception as ex:
        logger.debug('Failed to write debug click coordinates: %s', ex)
        return False
