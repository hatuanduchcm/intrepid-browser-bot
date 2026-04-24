from order.events.handler_open_order import handle_open_order_event
from order.events.handler_copy_adjustment import handle_copy_adjustment_event
from utils.close_tab import close_tab_event
from brand.handler_search_brand import should_process_brand
import logging

logger = logging.getLogger(__name__)


def handle_order_flow_event(event_payload):
    """Orchestrate order flow: open -> find adjustment -> copy adjustment.

    Expects {'order_id': '12345'} in payload. Returns dict with results.
    """
    order_id = event_payload.get('order_id')
    if not order_id:
        raise RuntimeError('Missing order_id')

    result = {'order_id': order_id, 'found_adjustment': False, 'adjustment_text': None}

    opened = False

    try:
        opened = bool(handle_open_order_event(event_payload))
    except Exception as e:
        logger.debug('open_order failed: %s', e)

    if not opened:
        return result

    try:
        txt = handle_copy_adjustment_event({'venture': event_payload.get('venture', '')})
        result['adjustment_text'] = txt
    except Exception as e:
        logger.debug('copy_adjustment failed: %s', e)

    try:
        closed = close_tab_event()
        logger.debug('close_tab_event invoked, result=%s', closed)
    except Exception:
        logger.debug('close_tab_event failed', exc_info=True)

    return result
