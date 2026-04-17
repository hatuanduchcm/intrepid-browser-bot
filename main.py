"""Repository entrypoint — runs the Invoice Adjustment bot from project root.
"""
from dotenv import load_dotenv
from pathlib import Path
from auth.handler_login import handle_login_event
from brand.handler_search_brand import handle_search_brand_event
from order.handler_order_flow import handle_order_flow_event
from gsheets.order_adjustment_sheet import extract_order_index_map, update_columns_for_order
import logging
from brand.handler_search_brand import handle_search_brand_event

logger = logging.getLogger(__name__)


def run_batch_process(sheet_id: str, sheet_name: str, orders_sheet_path: str = None):
    """Orchestrate batch processing:

    1. Extract order index map from the given sheet (order -> row/index and metadata).
    2. Loop over each order_id and fetch adjustment info
    3. After processing, upload relevant adjustment info back to the sheet via `update_columns_for_order`.

    `sheet_id` and `sheet_name` identify the Google Sheet to read/write.
    """
    # 1) extract mapping
    mapping = extract_order_index_map(sheet_id, sheet_name, output_path=orders_sheet_path)
    logger.info('Found %d orders to process', len(mapping))

    # 2) iterate — sort by Brand Name to group identical brands together
    last_venture = None
    # mapping may be a dict; convert to list of (order_id, meta) and sort by Brand Name
    items = list(mapping.items())
    def _brand_key(item):
        _, meta = item
        b = meta.get('Brand Name') or meta.get('Brand') or ''
        return str(b).strip().lower()
    items.sort(key=_brand_key)
    for order_id, meta in items:
        try:
            logger.info('Processing order %s (row %s)', order_id, meta.get('index'))
            # ensure logged-in session matches the Venture/region for this order
            venture = (meta.get('Venture') or meta.get('venture') or '').strip()
            if venture:
                # normalize venture to region code accepted by login handler (e.g., 'VN')
                region = venture.upper()
                if region != last_venture:
                    try:
                        logger.info('Logging in for Venture/region %s', region)
                        handle_login_event({'region': region})
                        last_venture = region
                    except Exception as e:
                        logger.warning('Login failed for region %s: %s', region, e)
            # If brand info available, perform brand search first
            brand = meta.get('Brand Name') or meta.get('Brand')
            if brand:
                try:
                    logger.info('Searching brand %s before processing order %s', brand, order_id)
                    if not handle_search_brand_event({'brand': brand}):
                        logger.warning('Brand search flow indicated failure for brand "%s", order %s. Continuing with next order', brand, order_id)
                        continue
                except Exception as e:
                    logger.warning('Brand search failed for %s: %s', brand, e)
            result = handle_order_flow_event({'order_id': order_id, 'brand': brand})
            # result may include `adjustment_text` as dict from our handler
            updates = {}
            adj = result.get('adjustment_text')
            if isinstance(adj, dict):
                # map parsed ColumnName keys to GSheet headers
                from gsheets.order_adjustment_sheet import GSHEET_COLUMN
                printable = {}
                for k, v in adj.items():
                    try:
                        # k may be ColumnName enum or string; coerce
                        if not isinstance(k, str):
                            key = GSHEET_COLUMN.get(k)
                        else:
                            # if key looks like ColumnName.XXX, try to eval Enum
                            key = None
                        if key:
                            printable[key] = str(v)
                    except Exception:
                        continue
                updates = printable
            # 3) upload updates if any
            if updates:
                try:
                    update_columns_for_order(sheet_id, sheet_name, order_id, updates)
                except Exception as e:
                    logger.exception('Failed to update sheet for order %s: %s', order_id, e)
        except Exception as e:
            logger.exception('Processing failed for order %s: %s', order_id, e)

    logger.info('Batch processing complete')

import logging

# Configure root logger to show debug messages on console during development
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

env_path = Path('.') / '.env'
load_dotenv(env_path)



def main():
    try:
        # handle_login_event({'region': 'VN'})
        # Example: run brand search
        # handle_search_brand_event({'brand': 'OATSIDE'})

        # res = handle_order_flow_event({'order_id': '2603264PETUQB4'})
        # print('Order flow result:', res)
        # If SHEET_ID/SHEET_NAME provided in env, run batch process; otherwise run example flow
        import os
        sheet_id = os.getenv('GSHEET_ID')
        sheet_name = os.getenv('GSHEET_SHEET_NAME')
        if sheet_id and sheet_name:
            print('Running batch process for', sheet_id, sheet_name)
            run_batch_process(sheet_id, sheet_name)
        else:
            logging.info('GSHEET_ID or GSHEET_SHEET_NAME not set in environment; skipping batch process and running example flow')
            # handle_login_event({'region': 'VN'})
            # # Example: run brand search
            # handle_search_brand_event({'brand': 'OATSIDE'})
            # res = handle_order_flow_event({'order_id': '2603264PETUQB4'})
            # print('Order flow result:', res)
    except Exception as e:
        print('Errors:', e)


if __name__ == '__main__':
    main()
