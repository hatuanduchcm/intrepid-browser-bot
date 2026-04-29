from order.events.handler_copy_adjustment import extract_adjustment_mapping_from_crop
from pathlib import Path
import sys
import json

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_from_image.py <image_path> <venture>")
        sys.exit(1)
    image_path = sys.argv[1]
    venture = sys.argv[2]
    result = extract_adjustment_mapping_from_crop(image_path, venture=venture)
    # Convert all keys to str for JSON serialization
    def convert_keys(obj):
        if isinstance(obj, dict):
            return {str(k): convert_keys(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_keys(i) for i in obj]
        else:
            return obj
    print(json.dumps(convert_keys(result), ensure_ascii=False, indent=2))
