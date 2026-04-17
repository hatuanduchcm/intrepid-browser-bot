from src.orders import search_order_in_app

def handle_search_order(event_payload):
    order_id = event_payload.get('order_id')
    return search_order_in_app(order_id)
