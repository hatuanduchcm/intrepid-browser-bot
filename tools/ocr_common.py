import re
from pathlib import Path
from PIL import Image
import pytesseract
from pytesseract import pytesseract as _pyt
_pyt.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def image_to_text(image_path: str) -> str:
    img = Image.open(image_path)
    try:
        return pytesseract.image_to_string(img, lang='eng+vie')
    except Exception as e:
        # fallback to easyocr if tesseract not available
        try:
            import easyocr
        except Exception:
            raise
        reader = easyocr.Reader(['en', 'vi'], gpu=False)
        # easyocr returns list of (bbox, text, prob)
        results = reader.readtext(image_path, detail=0)
        return '\n'.join(results)


def clean_ocr_text(raw: str) -> str:
    s = raw
    # remove common junk
    s = s.replace('\ufeff', '')
    s = s.replace('�', '')
    s = s.replace('[crop]', '')
    s = s.replace('\t', ' ')
    s = s.replace('_', '')
    s = s.replace('@', '')

    # Do not globally convert '4' to currency symbol — only normalize
    # when a token clearly represents an amount without any currency symbol.
    # Fix patterns like '-d' or '- d' or '-4' to '-₫' when they appear attached to amounts
    s = re.sub(r"-\s*[dD]\s*", '-₫', s)

    # Simpler, more robust merging strategy:
    # - classify lines as amount-only if they contain digits and look like a price
    # - for each amount-only line, attach it to the nearest previous non-amount line (label)
    raw_lines = [l.strip() for l in s.splitlines() if l.strip()]

    amt_pattern = re.compile(r"^-?\s*[₫đ]?\s*-?\d+[\d\.\s]*$")

    # Try mapping amounts to a list of expected labels (if present) to preserve correct row pairing.
    expected_labels = [
        'Refund Amount',
        'Shipping Fee Charged by Logistic',
        'Provider',
        'Shipping Fee Rebate From',
        'Shopee',
        'Voucher Sponsored by Seller',
        'Commission Fee',
        'Service Fee',
        'Total Adjustment Amount',
    ]

    # collect labels found in raw_lines in order and amount tokens
    found_labels = []
    amounts = []
    others = []
    for line in raw_lines:
        # If an amount already contains a currency symbol, treat it as 'other' (do not use for mapping)
        if amt_pattern.match(line):
            if '₫' in line or 'đ' in line:
                others.append(line)
            else:
                amounts.append(line)
        elif any(el.lower() in line.lower() for el in expected_labels):
            found_labels.append(line)
        else:
            others.append(line)

    # If we found label-like lines and at least one amount, try to assign sequentially
    if found_labels and amounts:
        mapped = []
        money_keywords = re.compile(r"(refund|shipping|voucher|commission|service|adjustment)", re.IGNORECASE)
        # assign amounts in-order to found labels
        for i, lbl in enumerate(found_labels):
            amt = amounts[i] if i < len(amounts) else ''
            # heuristic: if amt starts with '9' (OCR error) and label looks like money, fix to '₫'
            if amt and money_keywords.search(lbl) and re.match(r"^9\d[\d\.\s]*$", amt.strip()):
                # replace leading '9' with currency symbol
                amt = '₫' + amt.strip()[1:]
            mapped.append(f"{lbl} {amt}".strip())
        mapped.extend(others)
        return "\n".join(mapped)

    # Otherwise fall back to simple attach-to-previous-label behavior
    output_lines = []
    last_label_idx = None
    for idx, line in enumerate(raw_lines):
        if amt_pattern.match(line):
            if last_label_idx is not None:
                output_lines[last_label_idx] = f"{output_lines[last_label_idx]} {line}"
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)
            last_label_idx = len(output_lines) - 1

    return "\n".join(output_lines)


def ocr_image_and_write(image_path: str, out_path: str):
    raw = image_to_text(image_path)
    cleaned = clean_ocr_text(raw)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(cleaned, encoding='utf-8')
    return cleaned
