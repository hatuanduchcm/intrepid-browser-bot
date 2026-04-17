import json
import sys, pathlib
# ensure project root is on sys.path so local packages import correctly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[0]))
from order.events.handler_copy_adjustment import get_tooltip_data
path='assets/debug_matches/proc_popup_crop_cursor_1776226692.png'
res = get_tooltip_data(_path=path)
# print(json.dumps(res = get_tooltip_data(_path=path)
# , ensure_ascii=False, indent=2))
