import pytest
import json
from pathlib import Path
from unittest.mock import patch

from order.events.handler_copy_adjustment import extract_adjustment_mapping_from_crop

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEBUG_DIR = _REPO_ROOT / 'assets' / 'test'

_SAMPLES = [
    ('test_vn.png', 'VN'),
    ('test_vn1.png', 'VN'),
    ('test_vn2.png', 'VN'),
    ('test_vn3.png', 'VN'),
    ('test_vn4.png', 'VN'),
    ('test_id.png', 'ID'),
    ('test_my.png', 'MY'),
    ('test_th.png', 'TH'),
    ('test_th2.png', 'TH'),
    ('test_ph.png', 'PH'),
    ('test_ph2.png', 'PH'),
    ('test_ph3.png', 'PH'),
    ('test_ph4.png', 'PH'),
]


@pytest.mark.parametrize("filename,venture", _SAMPLES, ids=lambda x: x if isinstance(x, str) else '')
def test_extract_adjustment_mapping_from_crop_on_sample(filename, venture):
    """Run extract_adjustment_mapping_from_crop against each named sample with its venture."""
    sample = _DEBUG_DIR / filename
    if not sample.exists():
        pytest.skip(f'{filename} not found in debug_matches')

    result = extract_adjustment_mapping_from_crop(str(sample), venture=venture)
    printable = {str(k): v for k, v in result.items()} if isinstance(result, dict) else result
    source = result.get('__source__', 'unknown') if isinstance(result, dict) else 'unknown'
    print(f"\n--- {filename} (venture={venture}) [source={source}] ---\n{json.dumps(printable, ensure_ascii=True, indent=2)}")
    assert result is not None, f"{filename}: returned None"
    assert isinstance(result, dict), f"{filename}: expected dict, got {type(result)}"
    assert '__ocr_lines__' in result, f"{filename}: missing '__ocr_lines__'"
    assert '__total_check__' in result, f"{filename}: missing '__total_check__'"
    tc = result['__total_check__']
    assert isinstance(tc, dict) and 'matches' in tc, f"{filename}: __total_check__ missing 'matches'"
    assert tc['matches'] is True, f"{filename}: total_check matches=False (expected matches=True).\nDetails: {tc}"
    assert source == 'ocr', f"{filename}: expected source=ocr but got source={source} (Gemini was used unexpectedly)"


@pytest.mark.parametrize("filename,venture", [('test_vn4.png', 'VN')])
def test_gemini_fallback_when_ocr_fails(filename, venture):
    """Force OCR to return None, expect Gemini AI fallback to produce a valid result."""
    sample = _DEBUG_DIR / filename
    if not sample.exists():
        pytest.skip(f'{filename} not found')

    # Patch ocr_image to always return None to simulate OCR failure
    with patch('utils.ocr.ocr_image', return_value=None):
        result = extract_adjustment_mapping_from_crop(str(sample), venture=venture)

    source = result.get('__source__', 'unknown') if isinstance(result, dict) else 'unknown'
    printable = {str(k): v for k, v in result.items()} if isinstance(result, dict) else result
    print(f"\n--- {filename} (venture={venture}) [source={source}] ---\n{json.dumps(printable, ensure_ascii=True, indent=2)}")

    assert result is not None, f"{filename}: Gemini fallback returned None"
    assert isinstance(result, dict), f"{filename}: expected dict"
    assert source == 'gemini', f"{filename}: expected source=gemini, got {source}"
    assert '__total_check__' in result, f"{filename}: missing __total_check__"
    tc = result['__total_check__']
    assert isinstance(tc, dict) and tc.get('matches') is True, f"{filename}: Gemini result matches=False.\nDetails: {tc}"
