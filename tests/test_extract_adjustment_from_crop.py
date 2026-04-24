import pytest
import json
from pathlib import Path

from order.events.handler_copy_adjustment import extract_adjustment_mapping_from_crop

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEBUG_DIR = _REPO_ROOT / 'assets' / 'debug_matches'

_SAMPLES = [
    ('proc_vn.png', 'VN'),
    ('proc_id.png', 'ID'),
    ('proc_my.png', 'MY'),
    ('proc_th.png', 'TH'),
]


@pytest.mark.parametrize("filename,venture", _SAMPLES, ids=lambda x: x if isinstance(x, str) else '')
def test_extract_adjustment_mapping_from_crop_on_sample(filename, venture):
    """Run extract_adjustment_mapping_from_crop against each named sample with its venture."""
    sample = _DEBUG_DIR / filename
    if not sample.exists():
        pytest.skip(f'{filename} not found in debug_matches')

    result = extract_adjustment_mapping_from_crop(str(sample), venture=venture)
    printable = {str(k): v for k, v in result.items()} if isinstance(result, dict) else result
    print(f"\n--- {filename} (venture={venture}) ---\n{json.dumps(printable, ensure_ascii=False, indent=2)}")
    assert result is not None, f"{filename}: returned None"
    assert isinstance(result, dict), f"{filename}: expected dict, got {type(result)}"
    assert '__ocr_lines__' in result, f"{filename}: missing '__ocr_lines__'"
    assert '__total_check__' in result, f"{filename}: missing '__total_check__'"
    tc = result['__total_check__']
    assert isinstance(tc, dict) and 'matches' in tc, f"{filename}: __total_check__ missing 'matches'"
