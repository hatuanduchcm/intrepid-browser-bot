import re
import json
from pathlib import Path
import sys
# ensure repo root on path for local imports
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
from gsheets.order_adjustment_sheet import ADJUSTMENT_COLUMN_KEYS


def load_text(path: str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return p.read_text(encoding='utf-8')


def find_best_key(line: str):
    s = line.lower()
    # first try direct substring match
    for k in ADJUSTMENT_COLUMN_KEYS:
        if k.lower() in s:
            return k
    # try word-by-word match: find key with most shared words
    best = None
    best_score = 0
    words = set(re.findall(r"\w+", s))
    for k in ADJUSTMENT_COLUMN_KEYS:
        kwords = set(re.findall(r"\w+", k.lower()))
        score = len(words & kwords)
        if score > best_score:
            best_score = score
            best = k
    if best_score > 0:
        return best
    return None


def extract_value(line: str):
    # find first amount-like token (may be negative, may include ₫ or đ)
    m = re.search(r"-?\s*[₫đ]?\s*-?\d[\d\.\s]*", line)
    if m:
        return m.group(0).strip()
    return ''


def fix_currency_text(value: str) -> str:
    # user-provided fixes: convert leading 4 or -4 to đ/-đ
    v = re.sub(r"(?<!\w)-4(\d{1,3}\.\d{3})", r"-đ\1", value)
    v = re.sub(r"(?<!\w)4(\d{1,3}\.\d{3})", r"đ\1", v)
    # also normalize lowercase d->đ when adjacent to digits
    v = re.sub(r"\bd(\d)", r"đ\1", v)
    return v


def parse_file(path: str):
    txt = load_text(path)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    mapping = {}
    unmapped = []
    for line in lines:
        key = find_best_key(line)
        val = extract_value(line)
        if key:
            mapping[key] = val
        else:
            unmapped.append(line)

    # print mapping
    print('Parsed mapping:')
    for k in ADJUSTMENT_COLUMN_KEYS:
        if k in mapping:
            print(f'- {k}: {mapping[k]}')
    if unmapped:
        print('\nUnmapped lines:')
        for l in unmapped:
            print('-', l)

    # apply currency fix and print corrected mapping
    corrected = {k: fix_currency_text(v) for k, v in mapping.items()}
    print('\nCorrected mapping:')
    for k in ADJUSTMENT_COLUMN_KEYS:
        if k in corrected:
            print(f'- {k}: {corrected[k]}')

    # save to dist
    out_p = Path('dist/parsed_adjustments.json')
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps({'raw': mapping, 'corrected': corrected}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nSaved parsed JSON to', out_p)


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'assets/debug_matches/ocr_text.txt'
    parse_file(path)
import re
from pathlib import Path
from gsheets.order_adjustment_sheet import ADJUSTMENT_COLUMN_KEYS


def load_ocr_text(paths):
    for p in paths:
        p = Path(p)
        if p.exists():
            return p.read_text(encoding='utf-8')
    return ''


def parse_lines_to_map(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    mapping = {}
    # look for keys in lines; allow partial/case-insensitive match
    for key in ADJUSTMENT_COLUMN_KEYS:
        mapping[key] = ''
    for line in lines:
        for key in ADJUSTMENT_COLUMN_KEYS:
            if key.lower() in line.lower():
                # extract value: last token that looks like a number or has currency symbol
                m = re.findall(r"[\-₫đ]?[0-9][0-9\.,\s]*", line)
                val = m[-1].strip() if m else ''
                mapping[key] = val
                break
    return mapping


def fix_values(mapping: dict):
    money_k = re.compile(r"refund|shipping|voucher|commission|service|adjustment", re.IGNORECASE)
    out = {}
    for k, v in mapping.items():
        if not v:
            out[k] = v
            continue
        t = v.strip()
        # if already has currency symbol, keep
        if '₫' in t or 'đ' in t:
            out[k] = t
            continue
        # heuristic: if label suggests money and value starts with 9 or 4, convert leading char to ₫
        if money_k.search(k) and (t[0] == '9' or t[0] == '4'):
            out[k] = '₫' + t[1:]
        else:
            out[k] = t
    return out


def main():
    paths = [
        'assets/debug_matches/ocr_text_cleaned.txt',
        'assets/debug_matches/ocr_text.txt',
        'assets/debug_matches/copy_adjustment_test_output.txt',
    ]
    txt = load_ocr_text(paths)
    if not txt:
        print('No OCR text found in expected paths')
        return 2
    print('--- Raw OCR ---')
    print(txt)
    mapping = parse_lines_to_map(txt)
    print('\n--- Parsed mapping (before fix) ---')
    for k, v in mapping.items():
        if v:
            print(f'{k}: {v}')
    fixed = fix_values(mapping)
    print('\n--- Parsed mapping (after fix) ---')
    for k, v in fixed.items():
        if v:
            print(f'{k}: {v}')


if __name__ == '__main__':
    raise SystemExit(main())
