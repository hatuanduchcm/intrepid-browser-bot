"""Repository entrypoint — runs the Invoice Adjustment bot from project root.
"""
from dotenv import load_dotenv
from pathlib import Path
from auth.handler_login import handle_login_event, handle_logout
from brand.handler_search_brand import handle_search_brand_event
from order.handler_order_flow import handle_order_flow_event
from gsheets.order_adjustment_sheet import extract_order_index_map, update_columns_for_order
import logging
from brand.handler_search_brand import handle_search_brand_event

logger = logging.getLogger(__name__)


def run_batch_process(sheet_id: str, sheet_name: str, orders_sheet_path: str = None):
    """Orchestrate batch processing:

    1. Extract order index map from the given sheet (order -> row/index and metadata).Browser
    
    2. Loop over each order_id and fetch adjustment info
    3. After processing, upload relevant adjustment info back to the sheet via `update_columns_for_order`.

    `sheet_id` and `sheet_name` identify the Google Sheet to read/write.
    """
    # 1) extract mapping
    mapping = extract_order_index_map(sheet_id, sheet_name, output_path=orders_sheet_path)
    logger.info('Found %d orders to process', len(mapping))

    # 2) iterate — sort by venture first, then brand to group logins together
    last_venture = None
    items = list(mapping.items())
    def _sort_key(item):
        _, meta = item
        v = meta.get('Venture') or meta.get('venture') or ''
        b = meta.get('Brand Name') or meta.get('Brand') or ''
        return (str(v).strip().upper(), str(b).strip().lower())
    items.sort(key=_sort_key)
    for order_id, meta in items:
        try:
            logger.info('Processing order %s (row %s)', order_id, meta.get('index'))
            # logout and re-login when venture changes
            venture = (meta.get('Venture') or meta.get('venture') or '').strip().upper()
            if venture:
                if venture != last_venture:
                    try:
                        if last_venture is not None:
                            logger.info('Venture changed %s -> %s, logging out', last_venture, venture)
                            handle_logout()
                        logger.info('Logging in for venture %s', venture)
                        handle_login_event({'venture': venture})
                        last_venture = venture
                    except Exception as e:
                        logger.warning('Login failed for venture %s: %s', venture, e)
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
            result = handle_order_flow_event({'order_id': order_id, 'brand': brand, 'venture': venture})
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
        # handle_login_event({'venture': 'VN'})
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
            # handle_login_event({'venture': 'VN'})
            # # Example: run brand search
            # handle_search_brand_event({'brand': 'OATSIDE'})
            # res = handle_order_flow_event({'order_id': '2603264PETUQB4'})
            # print('Order flow result:', res)
    except Exception as e:
        print('Errors:', e)


if __name__ == '__main__':
    main()
