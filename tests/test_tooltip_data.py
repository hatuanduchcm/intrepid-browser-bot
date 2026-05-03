import pytest
from pathlib import Path
from order.events.handler_copy_adjustment import get_tooltip_data

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEBUG_DIR = _REPO_ROOT / 'assets' / 'test'

@pytest.mark.parametrize("filename,venture", [
    ("test_vn2.png", "VN"),
    ("test_vn3.png", "VN"),
])
def test_get_tooltip_data_on_sample(filename, venture):
    sample = _DEBUG_DIR / filename
    debug_dir = _REPO_ROOT / 'assets' / 'debug_matches'
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_sample = debug_dir / filename
    # Copy file sang debug_matches để test không xóa file gốc
    if not sample.exists():
        pytest.skip(f'{filename} not found in test assets')
    import shutil
    shutil.copyfile(sample, debug_sample)
    result = get_tooltip_data(_path=str(debug_sample), venture=venture)
    assert result is not None, f"{filename}: returned None"
    assert isinstance(result, dict), f"{filename}: expected dict, got {type(result)}"
    assert '__ocr_lines__' in result, f"{filename}: missing '__ocr_lines__'"
    assert '__total_check__' in result, f"{filename}: missing '__total_check__'"
    tc = result['__total_check__']
    assert isinstance(tc, dict) and 'matches' in tc, f"{filename}: __total_check__ missing 'matches'"
    assert tc['matches'] is True, f"{filename}: total_check matches=False (expected matches=True).\nDetails: {tc}"
    print(f"\n--- {filename} (venture={venture}) ---\n", result)
