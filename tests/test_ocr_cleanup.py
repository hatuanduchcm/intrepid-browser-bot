import pathlib
from tools.ocr_common import image_to_text, clean_ocr_text, ocr_image_and_write


def test_cleanup_on_sample_image():
    img = 'assets/debug_matches/proc_popup_crop_cursor_1776159912_1776159912.png'
    out = 'assets/debug_matches/ocr_text_from_image.txt'
    raw = image_to_text(img)
    cleaned = clean_ocr_text(raw)
    # write outputs for manual inspection
    p = pathlib.Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cleaned, encoding='utf-8')

    # Basic sanity assertions
    assert '₫' in cleaned or 'đ' in cleaned or '-' in cleaned
