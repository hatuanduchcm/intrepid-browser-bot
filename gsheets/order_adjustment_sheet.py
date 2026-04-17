import logging
from pathlib import Path
from typing import Dict, List, Union
from enum import Enum
import gspread
from google.oauth2.service_account import Credentials
import os
        
# Requires: gspread, google-auth
# Service account JSON should be pointed by environment variable GOOGLE_SERVICE_ACCOUNT_PATH

logger = logging.getLogger(__name__)

# store last opened Worksheet for external inspection/tests
LAST_WORKSHEET = None

# New structured adjustment column definitions.
class ColumnCategory(Enum):
    G_SHEET_COL = 'g_sheet_col'
    SHOPEE_LABEL = 'shopee_label'


class ColumnName(Enum):
    REFUND_AMOUNT = 'REFUND_AMOUNT'
    SHIPPING_FEE_CHARGED_BY_LOGISTIC = 'SHIPPING_FEE_CHARGED_BY_LOGISTIC'
    SHIPPING_FEE_REBATE_FROM_SHOPEE = 'SHIPPING_FEE_REBATE_FROM_SHOPEE'
    SHIPPING_REBATE_FROM_SHOPEE = 'SHIPPING_REBATE_FROM_SHOPEE'
    ACTUAL_SHIPPING_FEE = 'ACTUAL_SHIPPING_FEE'
    SHIPPING_FEE_PAID_BY_BUYER = 'SHIPPING_FEE_PAID_BY_BUYER'
    SELLER_PAID_SHIPPING_FEE_SST = 'SELLER_PAID_SHIPPING_FEE_SST'
    REVERSE_SHIPPING_FEE = 'REVERSE_SHIPPING_FEE'
    REVERSE_SHIPPING_FEE_SST = 'REVERSE_SHIPPING_FEE_SST'
    COMMISSION_FEE = 'COMMISSION_FEE'
    TRANSACTION_FEE = 'TRANSACTION_FEE'
    SERVICE_FEE = 'SERVICE_FEE'
    AMS_COMMISSION_FEE = 'AMS_COMMISSION_FEE'
    VOUCHER_SPONSORED_BY_SELLER = 'VOUCHER_SPONSORED_BY_SELLER'
    PRODUCT_DISCOUNT_REBATE_FROM_SHOPEE = 'PRODUCT_DISCOUNT_REBATE_FROM_SHOPEE'
    PROMO_CODE_PAID_BY_SELLER = 'PROMO_CODE_PAID_BY_SELLER'
    ORIGINAL_PRODUCT_PRICE = 'ORIGINAL_PRODUCT_PRICE'
    GAP = 'GAP'
    TOTAL_ADJUSTMENT_AMOUNT = 'TOTAL_ADJUSTMENT_AMOUNT'


# Simplified mappings requested: two separate maps
#  - ADJUSTMENT_COLUMNS: ColumnName -> list of Shopee label variants
#  - GSHEET_COLUMN: ColumnName -> GSheet header string
ADJUSTMENT_COLUMNS = {
    ColumnName.REFUND_AMOUNT: ["Refund Amount"],
    ColumnName.SHIPPING_FEE_CHARGED_BY_LOGISTIC: ["Shipping Fee Charged by Logistic Provider", "Shipping Fee Charged by Logistic", "Shipping Fee Charged"],
    ColumnName.SHIPPING_FEE_REBATE_FROM_SHOPEE: ["Shipping Fee Rebate From Shopee", "Shipping Fee Rebate From", "Shipping Fee Rebate"],
    ColumnName.SHIPPING_REBATE_FROM_SHOPEE: ["Shipping Rebate From Shopee", "Shipping Rebate From"],
    ColumnName.ACTUAL_SHIPPING_FEE: ["Actual Shipping Fee"],
    ColumnName.SHIPPING_FEE_PAID_BY_BUYER: ["Shipping Fee Paid by Buyer", "Shipping Fee Paid by"],
    ColumnName.SELLER_PAID_SHIPPING_FEE_SST: ["Seller Paid Shipping Fee SST", "Seller Paid Shipping"],
    ColumnName.REVERSE_SHIPPING_FEE: ["Reverse Shipping Fee"],
    ColumnName.REVERSE_SHIPPING_FEE_SST: ["Reverse Shipping Fee SST"],
    ColumnName.COMMISSION_FEE: ["Commission Fee"],
    ColumnName.TRANSACTION_FEE: ["Transaction Fee"],
    ColumnName.SERVICE_FEE: ["Service Fee"],
    ColumnName.AMS_COMMISSION_FEE: ["AMS Commission Fee"],
    ColumnName.VOUCHER_SPONSORED_BY_SELLER: ["Voucher Sponsored by Seller"],
    ColumnName.PRODUCT_DISCOUNT_REBATE_FROM_SHOPEE: ["Product Discount Rebate from Shopee"],
    ColumnName.PROMO_CODE_PAID_BY_SELLER: ["Promo Code Paid By Seller"],
    ColumnName.ORIGINAL_PRODUCT_PRICE: ["Original product price"],
    ColumnName.GAP: ["Gap"],
    ColumnName.TOTAL_ADJUSTMENT_AMOUNT: ["Total Adjustment Amount"],
}

# Map ColumnName -> GSheet header text
GSHEET_COLUMN = {
    ColumnName.REFUND_AMOUNT: "Refund Amount",
    ColumnName.SHIPPING_FEE_CHARGED_BY_LOGISTIC: "Shipping Fee Charged by Logistic Provider",
    ColumnName.SHIPPING_FEE_REBATE_FROM_SHOPEE: "Shipping Fee Rebate From Shopee",
    ColumnName.SHIPPING_REBATE_FROM_SHOPEE: "Shipping Rebate From Shopee",
    ColumnName.ACTUAL_SHIPPING_FEE: "Actual Shipping Fee",
    ColumnName.SHIPPING_FEE_PAID_BY_BUYER: "Shipping Fee Paid by Buyer",
    ColumnName.SELLER_PAID_SHIPPING_FEE_SST: "Seller Paid Shipping Fee SST",
    ColumnName.REVERSE_SHIPPING_FEE: "Reverse Shipping Fee",
    ColumnName.REVERSE_SHIPPING_FEE_SST: "Reverse Shipping Fee SST",
    ColumnName.COMMISSION_FEE: "Commission Fee",
    ColumnName.TRANSACTION_FEE: "Transaction Fee",
    ColumnName.SERVICE_FEE: "Service Fee",
    ColumnName.AMS_COMMISSION_FEE: "AMS Commission Fee",
    ColumnName.VOUCHER_SPONSORED_BY_SELLER: "Voucher Sponsored by Seller",
    ColumnName.PRODUCT_DISCOUNT_REBATE_FROM_SHOPEE: "Product Discount Rebate from Shopee",
    ColumnName.PROMO_CODE_PAID_BY_SELLER: "Promo Code Paid By Seller",
    ColumnName.ORIGINAL_PRODUCT_PRICE: "Original product price",
    ColumnName.GAP: "Gap",
    ColumnName.TOTAL_ADJUSTMENT_AMOUNT: "Total Adjustment Amount",
}

def find_columnname_by_shopee_label(label: str) -> Union[ColumnName, None]:
    """Return the ColumnName whose SHOPEE_LABEL list contains `label` (case-insensitive).

    If multiple match, returns the first found.
    """
    ll = label.strip().lower()
    # ADJUSTMENT_COLUMNS simplified: ColumnName -> list of labels
    for cname, labels in ADJUSTMENT_COLUMNS.items():
        for l in labels:
            if l.strip().lower() == ll:
                return cname
    return None


def map_adjustment_keys_to_columns(sheet_id: str, sheet_name: str) -> Dict[str, int]:
    """Return a dict mapping each ADJUSTMENT_COLUMN_KEYS entry to its column number
    (or None if missing) for the given sheet. Also saves to dist/adjustment_col_map.json.
    """
    # Build a list of expected G_SHEET_COL names in the same order as ADJUSTMENT_COLUMNS
    names = []
    name_to_colname = {}
    for cname, spec in ADJUSTMENT_COLUMNS.items():
        gname = spec.get(ColumnCategory.G_SHEET_COL)
        if gname:
            names.append(gname)
            name_to_colname[gname] = cname

    raw_map = save_adjustment_columns_map(sheet_id, sheet_name, names, output_path='dist/adjustment_col_map.json')
    # convert back to ColumnName -> colnum mapping
    result = {}
    for gname, col in raw_map.items():
        cname = name_to_colname.get(gname)
        if cname:
            result[cname] = col
    return result


# Backwards-compatible flat list of GSheet header names (preserves previous API)
# Build from GSHEET_COLUMN mapping (ColumnName -> header string)
ADJUSTMENT_COLUMN_KEYS = [v for v in GSHEET_COLUMN.values()]


def _open_sheet(sheet_id: str, sheet_name: str):
    global LAST_WORKSHEET
    # If a LAST_WORKSHEET was set earlier, reuse it only when its title matches
    if LAST_WORKSHEET is not None:
        try:
            if getattr(LAST_WORKSHEET, 'title', None) == sheet_name:
                return LAST_WORKSHEET
        except Exception:
            pass

    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    try:
        env_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
        if not env_path:
            raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_PATH not set')
        creds = Credentials.from_service_account_file(env_path, scopes=scopes)
    except Exception as e:
        logger.error('Failed to load service account credentials from GOOGLE_SERVICE_ACCOUNT_PATH: %s', e)
        raise

    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    worksheet = sh.worksheet(sheet_name)
    try:
        LAST_WORKSHEET = worksheet
    except Exception:
        pass
    return worksheet


def update_columns_for_order(sheet_id: str, sheet_name: str, order_id: str, updates: Dict[str, str]):
    """
    Find the row that contains `order_id` in any of the columns (Order ID column) and update
    the given columns by header name with values from `updates`.

    - `updates` keys are header names (e.g., "Refund Amount") and values are the new cell values.
    - The function will find header row (row 1), map header names to column numbers,
      locate the row matching `order_id`, then perform a batch update.
    """
    try:
        worksheet = _open_sheet(sheet_id, sheet_name)
    except Exception:
        raise

    # Read header row
    header = worksheet.row_values(1)
    header_map = {h: i + 1 for i, h in enumerate(header)}  # name -> col number (1-based)

    # Validate requested columns exist
    missing = [c for c in updates.keys() if c not in header_map]
    if missing:
        logger.warning('Requested update columns missing in sheet: %s', missing)

    # Find the row with order_id
    try:
        # Try to find exact match in the sheet (search entire sheet)
        cell = worksheet.find(order_id)
        row_number = cell.row
    except Exception:
        # fallback: scan the column(s) where Order ID likely is
        # Try to locate any header that contains 'order id'
        order_cols = [name for name in header if 'order' in name.lower() and 'id' in name.lower()]
        row_number = None
        if order_cols:
            col = header_map[order_cols[0]]
            col_values = worksheet.col_values(col)
            for idx, val in enumerate(col_values, start=1):
                if val.strip() == order_id:
                    row_number = idx
                    break
        if not row_number:
            raise RuntimeError('Order ID not found in sheet')

    # Prepare updates
    cell_updates: List = []
    # ensure ranges include worksheet title so spreadsheet batch update targets correct sheet
    ws_title = getattr(worksheet, 'title', None)
    for col_name, value in updates.items():
        if col_name not in header_map:
            continue
        col_num = header_map[col_name]
        a1 = gspread.utils.rowcol_to_a1(row_number, col_num)
        full_range = f"{ws_title}!{a1}" if ws_title else a1
        cell_updates.append({
            'range': full_range,
            'values': [[value]]
        })

    # Batch update
    if cell_updates:
        try:
            body = {'valueInputOption': 'USER_ENTERED', 'data': cell_updates}
            # debug: log target spreadsheet/worksheet and ranges
            try:
                ss_id = getattr(worksheet.spreadsheet, 'id', None)
                ss_title = getattr(worksheet.spreadsheet, 'title', None)
                ws_title = getattr(worksheet, 'title', None)
            except Exception:
                ss_id = ss_title = ws_title = None
            logger.debug('Batch update target spreadsheet id=%s title=%s worksheet=%s data=%s', ss_id, ss_title, ws_title, cell_updates)
            worksheet.spreadsheet.values_batch_update(body)
            logger.info('Updated row %s for order %s with %s (sheet=%s)', row_number, order_id, list(updates.keys()), ws_title)
        except Exception as e:
            logger.error('Failed to batch update sheet: %s', e)
            raise
    else:
        logger.info('No valid columns to update for order %s', order_id)

    return row_number


def extract_order_index_map(sheet_id: str, sheet_name: str, output_path: str = None) -> Dict[str, dict]:
    """
    Đọc worksheet, tìm các cột `Venture`, `Brand Name`, `Platform`, `Order ID`
    và sinh dict mapping order_id -> { 'index': row_number, 'Venture': ..., 'Brand Name': ..., 'Platform': ... }
    Nếu `output_path` được cung cấp, lưu kết quả dưới dạng JSON tại đó.
    Trả về dict đã tạo.
    """
    import json

    worksheet = _open_sheet(sheet_id, sheet_name)
    header = worksheet.row_values(1)
    # tìm các cột quan tâm (phù hợp không phân biệt hoa thường)
    def find_col(name_variants):
        for i, h in enumerate(header, start=1):
            if any(v.lower() == h.strip().lower() for v in name_variants):
                return i
        return None

    venture_col = find_col(['Venture'])
    brand_col = find_col(['Brand Name', 'Brand'])
    platform_col = find_col(['Platform'])
    order_col = find_col(['Order ID', 'OrderID', 'Order'])

    if not order_col:
        raise RuntimeError('Could not find Order ID column in header')

    data_map = {}
    # read all rows in needed columns to speed up
    col_indices = [c for c in [venture_col, brand_col, platform_col, order_col] if c]
    max_row = worksheet.row_count
    # read as a rectangular range from row 2 to last used row
    rows = worksheet.get_all_values()
    for idx, row in enumerate(rows[1:], start=2):
        try:
            order_id = row[order_col - 1].strip() if len(row) >= order_col else ''
            if not order_id:
                continue
            entry = {'index': idx}
            if venture_col and len(row) >= venture_col:
                entry['Venture'] = row[venture_col - 1].strip()
            else:
                entry['Venture'] = ''
            if brand_col and len(row) >= brand_col:
                entry['Brand Name'] = row[brand_col - 1].strip()
            else:
                entry['Brand Name'] = ''
            if platform_col and len(row) >= platform_col:
                entry['Platform'] = row[platform_col - 1].strip()
            else:
                entry['Platform'] = ''
            data_map[order_id] = entry
        except Exception:
            continue

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open('w', encoding='utf-8') as f:
            json.dump(data_map, f, ensure_ascii=False, indent=2)

    return data_map


def save_adjustment_columns_map(sheet_id: str, sheet_name: str, column_names: List[str], output_path: str = 'dist/adjustment_col_map.json') -> Dict[str, int]:
    """
    Map provided `column_names` (exact header text) to column numbers in the sheet and
    save the mapping to `output_path` as JSON with structure {col_name: col_number}.
    Returns the mapping dict.
    """
    import json

    worksheet = _open_sheet(sheet_id, sheet_name)
    header = worksheet.row_values(1)
    header_map = {h.strip(): i + 1 for i, h in enumerate(header)}

    mapping = {}
    for name in column_names:
        # try exact match first, then case-insensitive match
        if name in header_map:
            mapping[name] = header_map[name]
            continue
        found = None
        for h, idx in header_map.items():
            if h.strip().lower() == name.strip().lower():
                found = idx
                break
        # If exact/case-insensitive not found, allow prefix/shortened header variants.
        if not found:
            lname = name.strip().lower()
            for h, idx in header_map.items():
                hh = h.strip().lower()
                # if the provided name is a shortened prefix of the header
                if hh.startswith(lname):
                    found = idx
                    break
                # or if the header is a shortened prefix of the provided name
                if lname.startswith(hh):
                    found = idx
                    break
        if found:
            mapping[name] = found
        else:
            mapping[name] = None

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with out_p.open('w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return mapping


def save_header_map(sheet_id: str, sheet_name: str, output_path: str = 'dist/header_map.json') -> Dict[str, int]:
    """
    Read header row and save a mapping header_text -> column_number to `output_path`.
    Returns the mapping.
    """
    import json

    worksheet = _open_sheet(sheet_id, sheet_name)
    header = worksheet.row_values(1)
    header_map = {h.strip(): i + 1 for i, h in enumerate(header)}

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with out_p.open('w', encoding='utf-8') as f:
        json.dump(header_map, f, ensure_ascii=False, indent=2)

    return header_map
