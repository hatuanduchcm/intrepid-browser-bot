# Intrepid Browser Bot — Workflow Actions

Goal: Tự động cập nhật các "điều chỉnh" trên từng Order trong Intrepid và đẩy kết quả lên Google Sheets.

Top-level flow (high-level):
1. Fetch Order IDs from GSheet or API (TODO).
2. For each Order ID:
   a. Ensure IntrepidBrowser is open and logged in.
   b. Open Order detail page (search by Order ID).
   c. Locate "adjustment" information in the Order view.
   d. Extract/copy adjustment details.
   e. Post extracted info to Google Sheet (TODO).
   f. Mark Order as processed and continue.

Modules (separated responsibilities):
- `auth/`  : open Intrepid app + login automation
- `orders/`: search for order, open order detail, navigation helpers
- `scraper/`: extract adjustment info from Order view (UIA/dom/image/OCR)
- `gsheet/`: placeholder for pushing results to Google Sheets (TODO)
- `api/`  : placeholder to fetch order list via API key (TODO)
- `utils/`: helpers (clipboard, screenshot, retry, logging)

Action list (detailed):
- init
  - start Intrepid if not running (Windows Search)
  - focus window
- auth/login
  - fill username/password (from `.env`)
  - submit and wait until dashboard loads
- navigation
  - open shop/branch selector and choose branch
  - open search box, input Order ID, open result
- extract
  - find File/Invoice section
  - hover/click cloud icon to reveal tooltip/metadata
  - copy adjustment info from tooltip or read text nodes
- publish
  - write row to Google Sheet (sheet, orderid, adjustment text, timestamp)

Error handling & retries
- Retry login 2 times before abort.
- If Order not found, log and continue.
- If extraction fails, take screenshot and attach to log.

Next steps (what I will implement first)
1. Create module scaffold under `src/` with minimal functions.
2. Implement `auth` POC to open app and login using pywinauto.
3. Provide a small test driver CLI to run a single Order ID.

Run instructions (dev)
```powershell
python -m pip install -r requirements.txt
python -m src.cli --order 123456
```

Reply with: which module to implement first (auth/navigation/scraper/api/gsheet). I will implement that module next.