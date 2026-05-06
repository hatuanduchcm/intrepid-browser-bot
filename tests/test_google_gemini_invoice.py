import os
import glob
import time
import pytest
from utils.google_gemini_invoice import extract_shopee_invoice

TEST_IMAGE_DIR = os.path.join(os.path.dirname(__file__), '../assets/test')

# Lấy tất cả file ảnh trong thư mục test (jpg, png, jpeg)
image_files = glob.glob(os.path.join(TEST_IMAGE_DIR, '*.png')) + \
              glob.glob(os.path.join(TEST_IMAGE_DIR, '*.jpg')) + \
              glob.glob(os.path.join(TEST_IMAGE_DIR, '*.jpeg'))

@pytest.mark.parametrize('image_path', image_files)
def test_extract_shopee_invoice(image_path):
    print(f"\nTesting image: {image_path}")
    try:
        result = extract_shopee_invoice(image_path)
        assert isinstance(result, dict)
        assert 'metadata' in result
        assert 'extracted_items' in result
        assert 'total_adjustment_amount_in_image' in result
        assert 'calculated_total' in result
        assert 'is_match' in result
        print("Result:", result)
    except Exception as e:
        pytest.fail(f"extract_shopee_invoice failed for {image_path}: {e}")
