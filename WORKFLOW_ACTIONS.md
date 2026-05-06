# Intrepid Browser Bot — Workflow Actions

## Mục tiêu
Tự động cập nhật "điều chỉnh" (adjustment) trên từng Order trong Intrepid và đẩy kết quả lên Google Sheets.

---

## Luồng chính

```
GUI khởi động (gui_app.py)
  ├─ Check update ngầm từ GitHub Releases
  │    └─ Có bản mới → download ngầm → hiện banner "Cập nhật sẵn sàng"
  │         └─ User click → updater.bat chạy sau khi app thoát → restart
  │
  └─ User nhấn ▶ Run
       ├─ Đọc Sheet ID, Sheet Name, SA JSON từ UI (lưu vào .env)
       ├─ Spawn bot process (multiprocessing)
       │    1. Fetch danh sách Order từ Google Sheet (nhóm theo Venture)
       │    2. Với mỗi Venture:
       │         a. Login Intrepid bằng tài khoản của Venture đó (auth/)
       │         b. Với mỗi Order trong Venture:
       │              i.  Mở Order detail (search by ID)
       │              ii. Tìm section điều chỉnh
       │              iii.OCR / extract adjustment value
       │              iv. Ghi kết quả lên Google Sheet
       │              v.  Đánh dấu processed
       │         c. Logout khỏi Venture sau khi xong toàn bộ order
       │    3. Hoàn thành tất cả Venture
       └─ User nhấn ⏸ Stop → terminate process ngay lập tức
```

---

## Modules

| Thư mục | Trách nhiệm |
|---|---|
| `auth/` | Mở Intrepid, login (email → password → 2FA), logout |
| `brand/` | Tìm kiếm brand, chọn kết quả |
| `order/` | Mở Order theo ID, tìm điều chỉnh, copy adjustment |
| `gsheets/` | Đọc danh sách Order, ghi kết quả lên Sheet |
| `utils/` | OCR, amounts, window, clipboard, 2FA cache |

---

## GUI (gui_app.py)

- **Dark / Light theme** — lưu vào `.env` (`GUI_THEME`)
- **VI / EN language** — lưu vào `.env` (`GUI_LANG`), locale files tại `locales/`
- **Status indicator** — đèn nhấp nháy khi running, tĩnh khi idle/done/stopped
- **Log area** — màu theo level (ERROR/WARNING/INFO/DEBUG)
- **Auto-update** — check `hatuanduchcm/intrepid-browser-bot-dist` khi khởi động

---

## Auto-update flow

```
Developer:
  1. Sửa code
  2. Tăng version trong version.txt (vd: 1.0.0 → 1.0.1)
  3. git commit + git push → GitHub Actions tự động:
       - Build EXE (Windows runner, Python 3.11)
       - Bundle Tesseract-OCR 5.5
       - Nén → InvoiceAdjustmentBot.zip
       - Publish release lên hatuanduchcm/intrepid-browser-bot-dist

User (máy khác):
  - Mở app → check API → thấy version mới
  - Download ZIP ngầm → xong hiện banner xanh
  - Click banner → app thoát → iab_updater.bat giải nén đè → restart
```

---

## Build local (dev)

```bat
build_exe.bat
```
Output: `dist\InvoiceAdjustmentBot\`

---

## Cấu hình (.env)

```env
GSHEET_ID=...
GSHEET_SHEET_NAME=...
GOOGLE_SERVICE_ACCOUNT_PATH=key/order-adjustment-bot.json
GUI_THEME=dark
GUI_LANG=vi
```

---

## Error handling

- Login thất bại → retry 2 lần → dừng
- Order không tìm thấy → log + tiếp tục order kế
- OCR thất bại → screenshot đính kèm log
- Update thất bại (offline/API lỗi) → bỏ qua, app chạy bình thường
