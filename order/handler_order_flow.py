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

    result = {'order_id': order_id, 'found_adjustment': False, 'adjustment_text': None, 'opened': False}

    opened = False

    try:
        opened = bool(handle_open_order_event(event_payload))
        result['opened'] = opened
    except Exception as e:
        logger.error('[%s] open_order failed: %s', order_id, e)

    if not opened:
        logger.error('[%s] Order page not opened', order_id)
        return result

    try:
        txt = handle_copy_adjustment_event({'venture': event_payload.get('venture', ''), 'order_id': order_id})
        result['adjustment_text'] = txt
        if txt is None:
            logger.error('[%s] copy_adjustment returned None', order_id)
        else:
            logger.info('[%s] copy_adjustment OK: %s', order_id,
                        {k: v for k, v in txt.items() if not str(k).startswith('__')} if isinstance(txt, dict) else txt)
    except Exception as e:
        logger.error('[%s] copy_adjustment failed: %s', order_id, e)

    try:
        closed = close_tab_event()
        logger.debug('close_tab_event invoked, result=%s', closed)
    except Exception:
        logger.debug('close_tab_event failed', exc_info=True)

    return result
