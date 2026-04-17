import os
from dotenv import load_dotenv
load_dotenv()
from order_adjustment_sheet import extract_order_index_map

if __name__ == '__main__':
    sheet_id = os.getenv('GSHEET_ID')
    sheet_name = os.getenv('GSHEET_SHEET_NAME', '2.1 DATA ADJ_RAW_VN')
    out = 'dist/order_index.json'
    if not sheet_id:
        print('GSHEET_ID not set in environment/.env')
        raise SystemExit(1)
    print(f'Opening sheet {sheet_id} -> {sheet_name}...')
    m = extract_order_index_map(sheet_id, sheet_name, output_path=out)
    print(f'Wrote {len(m)} entries to {out}')
