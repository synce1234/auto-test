# Quy trình kiểm thử kết hợp Auto Test + Manual Test

## Mục tiêu

Đảm bảo mỗi bản APK phát hành đều được kiểm thử đầy đủ, giảm thiểu thời gian test thủ công bằng cách tự động hóa các test case lặp đi lặp lại, đồng thời giữ lại manual test cho các kịch bản cần phán đoán con người.

---

## Tổng quan phân chia

| Hạng mục | Auto Test | Manual Test |
|----------|-----------|-------------|
| Smoke test (app không crash) | ✅ | |
| Notification flow | ✅ | |
| Mở file (PDF, DOCX, XLSX, EPUB, PPTX, TXT, ảnh) | ✅ | |
| File có password | ✅ | |
| PDF Tools (Split, Merge, Sign, Scan) | ✅ | |
| UI/UX, layout, căn chỉnh | | ✅ |
| Luồng mua IAP, Subscription | | ✅ |
| Edge case đặc thù / bug cụ thể | Thêm dần | ✅ |
| Kiểm tra trên thiết bị thật đa dạng | | ✅ |

---

## Quy trình theo từng giai đoạn

### Giai đoạn 1 — Chuẩn bị APK

1. Dev build xong APK → đặt file vào thư mục `apks/`
   - Đặt tên theo convention: `AppName_(version)_(versionCode).apk`
   - Ví dụ: `Pdf(2.6.8)_(238).apk`
2. Mở Dashboard: `./run.sh` (mac) hoặc `run.bat` (win)
3. Vào tab **APKs** trên dashboard → xác nhận file đã nhận diện đúng version

---

### Giai đoạn 2 — Auto Test (chạy trước)

> Mục đích: phát hiện sớm các lỗi regression, crash cơ bản mà không tốn thời gian người test.

#### Bước 2.1 — Smoke Test (bắt buộc)

Chạy đầu tiên với mọi APK mới.

**Trên Dashboard:**
- Chọn APK cần test → Install
- Chọn test suite: `test_smoke.py`
- Chọn device → Run

**Smoke test kiểm tra:**
- App khởi động không crash
- Màn hình home hiển thị đúng
- Navigation cơ bản hoạt động

**Quy tắc:**
- Nếu smoke test **FAIL** → dừng lại, báo dev ngay, không test tiếp
- Nếu smoke test **PASS** → tiến sang bước 2.2

---

#### Bước 2.2 — Full Auto Test Suite

Chạy toàn bộ sau khi smoke pass.

| Test suite | Nội dung | Thời gian ước tính |
|------------|----------|--------------------|
| `test_notification.py` | TC-001→TC-010: Notification flow | ~10 phút |
| `test_open_pdf.py` | Mở và đọc PDF | ~8 phút |
| `test_open_files_other.py` | DOCX, XLSX, PPTX, TXT, ảnh, EPUB | ~15 phút |
| `test_open_files_password.py` | File PDF có password | ~5 phút |
| `test_pdf_tools.py` | Split, Merge, Sign, Scan | ~10 phút |
| `test_data_migration.py` | Migration dữ liệu giữa các version | ~5 phút |

**Cách chạy toàn bộ:**
- Dashboard → chọn tất cả suite → Run All
- Hoặc terminal: `./run.sh` → dashboard → chọn All Tests

**Xem kết quả:**
- Dashboard hiển thị PASS/FAIL real-time
- Sau khi xong: tab **Reports** → xem HTML report hoặc tải Excel
- Screenshot lỗi được lưu tự động trong `reports/screenshots/`

---

#### Bước 2.3 — Đọc kết quả Auto Test

Phân loại kết quả:

| Kết quả | Hành động |
|---------|-----------|
| Tất cả PASS | Chuyển sang Manual Test (Giai đoạn 3) |
| Có FAIL rõ ràng (crash, assert sai) | Tạo bug report → báo dev → retest sau khi fix |
| Có FAIL cần xem lại (flaky, device issue) | Chạy lại 1 lần, nếu vẫn fail mới báo dev |
| Có SKIP | Ghi chú lý do, assign manual test cho TC đó |

---

### Giai đoạn 3 — Manual Test (chạy sau auto)

> Tập trung vào những gì auto test không thể kiểm tra được.

#### Nhóm 1 — UI/UX & Visual

Kiểm tra bằng mắt những thứ khó assert bằng code:

- [ ] Màu sắc, font, icon hiển thị đúng theme (light/dark)
- [ ] Layout không bị vỡ trên các màn hình nhỏ/lớn
- [ ] Animation mượt mà
- [ ] Toast, dialog, bottom sheet hiển thị đúng vị trí
- [ ] Ads không che nội dung quan trọng

#### Nhóm 2 — Luồng mua hàng (IAP)

- [ ] Màn hình Premium hiển thị đúng giá
- [ ] Luồng mua subscription (không thực sự thanh toán — dùng test account)
- [ ] Restore purchase hoạt động
- [ ] Free user bị chặn đúng tính năng premium

#### Nhóm 3 — Edge case & Regression manual

- [ ] Mở file rất lớn (>50MB) — quan sát loading, memory
- [ ] Mở nhiều file liên tiếp không bị crash
- [ ] Share file từ app khác vào PDF Reader
- [ ] Deep link / notification tap mở đúng file
- [ ] Back stack và navigation không bị lỗi

#### Nhóm 4 — Test trên thiết bị thật

Emulator không thể mô phỏng đầy đủ:

- [ ] Test trên ít nhất 2 thiết bị thật (màn hình nhỏ + lớn)
- [ ] Test trên Android 10, 12, 14 (nếu có thiết bị)
- [ ] Camera scan (nếu có tính năng)
- [ ] File được mở từ Gmail, Drive, WhatsApp

---

### Giai đoạn 4 — Tổng hợp kết quả & Go/No-Go

Sau khi hoàn thành cả auto và manual test:

**Điền vào bảng tổng hợp:**

| Hạng mục | Tổng TC | PASS | FAIL | SKIP | Ghi chú |
|----------|---------|------|------|------|---------|
| Auto Test | | | | | |
| Manual Test | | | | | |
| **Tổng** | | | | | |

**Tiêu chí Go (phát hành):**
- Smoke test: 100% PASS
- Auto test: ≥ 90% PASS, không có FAIL mức Critical
- Manual test: Không có bug Critical/Blocker chưa fix
- Tất cả bug High priority đã có workaround hoặc đã fix

**Tiêu chí No-Go (giữ lại):**
- Smoke test FAIL
- Crash trên flow chính (open file, navigation)
- Lỗi mất dữ liệu người dùng
- Bug payment/IAP

---

## Workflow thực tế theo vòng sprint

```
Dev build APK
     │
     ▼
Đặt APK vào apks/ ──→ Dashboard nhận diện
     │
     ▼
[Auto] Smoke Test
     │
   FAIL ──→ Báo dev → Fix → Build lại
     │
   PASS
     │
     ▼
[Auto] Full Test Suite
     │
     ├─ Export report Excel/HTML
     ├─ Screenshot lỗi đính kèm bug
     └─ Triage: Fail thật vs Flaky
     │
     ▼
[Manual] UI/UX + IAP + Device thật
     │
     ▼
Tổng hợp kết quả
     │
   Go ──→ Phát hành / Submit Store
   No-Go ──→ Fix → Lặp lại từ đầu
```

---

## Cập nhật test case mới

Khi tìm thấy bug mới hoặc có tính năng mới:

1. Thêm TC vào `test_cases/test_cases.xlsx`
2. Nếu có thể auto hóa → viết thêm vào file `.py` tương ứng trong `tests/test_suite/`
3. Nếu chỉ manual → giữ trong Excel, đánh dấu cột **Type = Manual**
4. Cập nhật tài liệu này nếu quy trình thay đổi

---

## Thông tin kỹ thuật

| Thành phần | Chi tiết |
|-----------|----------|
| Framework | Python + Appium + pytest |
| Dashboard | Flask web server — `http://localhost:8080` |
| Appium | `http://127.0.0.1:4723` |
| Report | HTML + Excel tại `reports/` |
| Screenshot lỗi | `reports/screenshots/` |
| Script cài đặt | `setup.sh` (mac) / `setup.bat` (win) |
| Script chạy | `run.sh` (mac) / `run.bat` (win) |
