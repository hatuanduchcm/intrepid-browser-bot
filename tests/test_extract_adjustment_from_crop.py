import pytest
from pathlib import Path

from order.events.handler_copy_adjustment import extract_adjustment_mapping_from_crop


def test_extract_adjustment_mapping_from_crop_on_sample():
    """Run `extract_adjustment_mapping_from_crop` against a sample crop if available.

    The test is skipped when the sample image is not present in
    `assets/debug_matches/popup_crop_1776608983.png`.
    """
    repo_root = Path(__file__).resolve().parents[1]
    sample = repo_root / 'assets' / 'debug_matches' / 'popup_crop_1776608983.png'
    if not sample.exists():
        pytest.skip(f"Sample crop not present: {sample}")

    result = extract_adjustment_mapping_from_crop(str(sample))
    assert result is not None, "extract_adjustment_mapping_from_crop returned None for sample crop"
    assert isinstance(result, dict), f"Expected dict result, got {type(result)}"

    # Ensure debug fields attached
    assert '__ocr_lines__' in result, "Parsed mapping missing '__ocr_lines__'"
    assert '__total_check__' in result, "Parsed mapping missing '__total_check__'"
    tc = result['__total_check__']
    assert isinstance(tc, dict) and 'matches' in tc, "__total_check__ missing 'matches' boolean"
