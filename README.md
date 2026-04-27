# Intrepid Invoice Sync

Tự động hóa đồng bộ điều chỉnh hóa đơn từ Intrepid Seller Center sang Google Sheets.

## Cấu trúc

| File/Folder | Mô tả |
|---|---|
| `main.py` | Entry point — hàm `run_batch_process` |
| `gui_app.py` | Giao diện GUI (tkinter) |
| `requirements.txt` | Python dependencies |
| `build_exe.bat` | Script build file `.exe` |
| `make_icon.py` | Tạo icon `.ico` từ PNG |
| `auth/` | Login / 2FA handlers |
| `brand/` | Tìm kiếm brand |
| `order/` | Xử lý order flow |
| `gsheets/` | Đọc/ghi Google Sheets |
| `utils/` | OCR, amount parsing, helpers |

---

## Cài đặt nhanh (chạy bằng Python)

```powershell
python -m pip install -r requirements.txt
```

Sao chép file cấu hình:
```powershell
copy .env.example .env
```

Chỉnh sửa `.env` — điền các giá trị:
```env
INTREPID_PASS=your_password
GSHEET_ID=<Google Sheet ID>
GSHEET_SHEET_NAME=<Tên sheet>
GOOGLE_SERVICE_ACCOUNT_PATH=C:\path\to\key\order-adjustment-bot.json
```

Chạy GUI:
```powershell
python gui_app.py
```

---

## Build thành file .exe

### Yêu cầu

- Python 3.10+
- Tesseract OCR đã cài: https://github.com/UB-Mannheim/tesseract/wiki
- Tất cả dependencies đã cài (`![alt text](image.png)`)

### Các bước build

**Bước 1 — Tạo icon** (chạy 1 lần):
```powershell
python make_icon.py
```
→ Tạo file `assets/app_icon.ico`

**Bước 2 — Build exe** (double-click hoặc chạy trong terminal):
```powershell
.\build_exe.bat
```
→ Output: `dist\InvoiceAdjustmentBot.exe`

**Bước 3 — Copy file cấu hình vào thư mục `dist\`:**
```powershell
copy .env dist\
mkdir dist\key
copy key\order-adjustment-bot.json dist\key\
```

**Bước 4 — Chạy:**

Double-click `dist\InvoiceAdjustmentBot.exe` — giao diện mở lên, điền thông tin và bấm **▶ Chạy Bot**.

### Lưu ý khi distribute cho người khác

Cần copy cả thư mục `dist\` bao gồm:
```
dist\
  InvoiceAdjustmentBot.exe
  .env                          ← credentials
  key\
    order-adjustment-bot.json   ← Google service account key
```

> ⚠ **Không commit file `.env` và `key/*.json` lên git.** Các file này chứa thông tin nhạy cảm.

---

## Sử dụng GUI

1. Mở app → nhập **Sheet ID** và **Sheet Name**
2. Chọn file **Service Account JSON** (nếu chưa có trong `.env`)
3. Bấm **▶ Chạy Bot** — log hiển thị real-time bên dưới
4. Bấm **■ Dừng** để dừng ngay lập tức (kill process)

---

## Yêu cầu hệ thống

- Windows 10/11 (64-bit)
- Tesseract OCR: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Google Service Account có quyền edit Google Sheet tương ứng
