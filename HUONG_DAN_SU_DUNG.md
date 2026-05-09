# Hướng Dẫn Sử Dụng Auto Test Bot

Framework kiểm thử tự động cho ứng dụng Android PDF Reader, sử dụng Appium + pytest với Web Dashboard tích hợp.

---

## Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt lần đầu](#2-cài-đặt-lần-đầu)
3. [Khởi động Dashboard](#3-khởi-động-dashboard)
4. [Hướng dẫn dùng Dashboard](#4-hướng-dẫn-dùng-dashboard)
   - [Tab APKs](#tab-apks)
   - [Tab Run Tests](#tab-run-tests)
   - [Tab Test Cases](#tab-test-cases)
   - [Tab Reports](#tab-reports)
5. [Trạng thái Test Case](#5-trạng-thái-test-case)
6. [Cấu trúc thư mục](#6-cấu-trúc-thư-mục)
7. [Cấu hình config.yaml](#7-cấu-hình-configyaml)
8. [Viết Test Case mới](#8-viết-test-case-mới)
9. [Chạy test từ dòng lệnh](#9-chạy-test-từ-dòng-lệnh)
10. [Câu hỏi thường gặp](#10-câu-hỏi-thường-gặp)

---

## 1. Yêu cầu hệ thống

| Thành phần | Phiên bản tối thiểu | Ghi chú |
|---|---|---|
| macOS / Linux | macOS 13+ hoặc Ubuntu 20.04+ | Windows dùng `setup.bat` |
| Python | 3.10+ | Script tự phát hiện `python3.12`, `python3.11`... |
| Node.js | 18+ | Cần để chạy Appium server |
| Java (JDK) | 17+ | Bắt buộc cho UIAutomator2 driver |
| Android SDK | Build-tools + Platform-tools | Cài cùng Android Studio |
| Appium | 2.x+ | Tự cài qua `setup.sh` |
| UIAutomator2 driver | latest | Tự cài qua `setup.sh` |
| ffmpeg | any | Ghép video test (tự cài qua Homebrew) |

> **Kiểm tra nhanh:** Mở Terminal và chạy `adb devices` — phải thấy thiết bị ở trạng thái `device` (không phải `offline`).

---

## 2. Cài đặt lần đầu

### Cách 1: Double-click (khuyến nghị)

Double-click vào file **`start.command`** trong Finder.

- Lần đầu: macOS hỏi xác nhận → chọn **Open**
- Script tự động phát hiện nếu chưa cài và chạy `setup.sh`
- Sau khi cài xong, server start và trình duyệt mở tự động

### Cách 2: Terminal

```bash
cd auto-test/
bash setup.sh
```

`setup.sh` tự động thực hiện các bước sau:

| Bước | Nội dung |
|---|---|
| 1 | Kiểm tra Homebrew, Python 3, Node.js, Java |
| 2 | Cài ffmpeg (dùng để ghép video recording) |
| 3 | Kiểm tra Android SDK (`adb`, `aapt2`) |
| 4 | Cài Appium 2 và UIAutomator2 driver (nếu chưa có) |
| 5 | Tạo Python virtual environment (`.venv/`) |
| 6 | Cài toàn bộ Python package từ `requirements.txt` |

> **Ví dụ output thành công:**
> ```
> ✓  macOS 14.2
> ✓  Python 3.12
> ✓  Appium 2.5.4 (đã cài — bỏ qua)
> ✓  UIAutomator2 driver đã có
> ✓  .venv đã tạo xong
> ✓  Tất cả packages đã cài xong
> ✓  Cài đặt hoàn tất!
> ```

---

## 3. Khởi động Dashboard

### Cách 1: Double-click (nhanh nhất)

Double-click **`start.command`** — server tự start và trình duyệt tự mở tại `http://localhost:8080`.

### Cách 2: Terminal

```bash
# Dùng script có sẵn (tự start Appium + server)
./run.sh

# Hoặc chạy thủ công
source .venv/bin/activate
python3 server.py --port 8080
```

### Cách 3: Đổi port

```bash
./run.sh --port 9090
# hoặc
python3 server.py --port 9090
```

> **Lưu ý:** Appium server phải đang chạy trước khi bấm Start test.
> Kiểm tra Appium tại: `http://localhost:4723/status` — phải trả về `{"ready": true}`.

---

## 4. Hướng dẫn dùng Dashboard

### Tab APKs

Quản lý các file APK để cài lên thiết bị trước khi test.

**Upload APK:**
- Kéo thả file `.apk` vào vùng upload, hoặc click để chọn file từ máy
- Sau khi upload xong, dashboard tự đọc **Version Name** và **Version Code** từ APK

> **Ví dụ:** Upload `Pdf2.7.0_2394.apk` → dashboard hiển thị `Version: 2.7.0 (2394)`

**Xóa APK:**
- Click nút **Delete** ở cuối mỗi dòng

**Thông tin hiển thị:**

| Cột | Mô tả | Ví dụ |
|---|---|---|
| Filename | Tên file APK | `Pdf2.7.0_2394.apk` |
| Version Name | Version hiển thị cho người dùng | `2.7.0` |
| Version Code | Version code nội bộ (số nguyên) | `2394` |
| Size | Dung lượng file | `48.3 MB` |
| Modified | Thời điểm upload | `2026-05-09 10:30` |

---

### Tab Run Tests

Chạy test theo nhóm file hoặc class cụ thể.

**Bước 1 — Chọn Device**

Danh sách device tự động hiện ra dựa trên kết quả `adb devices`.

> Ví dụ: `emulator-5554 (Pixel_6a_2)` hoặc `R3CN90BXXXX (Samsung Galaxy S22)`

Nếu không thấy device, kiểm tra kết nối:
```bash
adb devices
# Phải thấy: emulator-5554   device
```

**Bước 2 — Chọn APK cài (tùy chọn)**

Tick các APK muốn cài lên device trước khi chạy test. Hệ thống cài theo thứ tự từ trên xuống dưới.

> **Ví dụ:** Tick `Pdf2.6.9_2369.apk` rồi `Pdf2.7.0_2394.apk` để test upgrade từ 2.6.9 → 2.7.0.
>
> Nếu không tick APK nào: test chạy ngay trên app đang cài sẵn trên thiết bị.

**Bước 3 — Chọn Test Scripts**

Tick các class test muốn chạy. Mỗi class tương ứng một nhóm test case.

| Class | File | Nội dung |
|---|---|---|
| `TestSmoke` | `test_smoke.py` | Kiểm tra cơ bản: app không crash, bottom nav hiển thị |
| `TestOpenPdf` | `test_open_pdf.py` | Mở PDF, viewer, zoom, navigation |
| `TestPdfTools` | `test_pdf_tools.py` | Split, Merge, Sign, Scanner |
| `TestDataMigration` | `test_data_migration.py` | Dữ liệu còn nguyên sau update app |
| `TestOpenFilesOther` | `test_open_files_other.py` | Mở PDF/PPTX/EPUB/TXT/DOCX/XLSX từ app khác |
| `TestRememberPassword` | `test_open_files_password.py` | Mở PDF có mật khẩu, nhớ mật khẩu |
| `TestNotification` | `test_notification.py` | Push notification |

**Bước 4 — Bấm Start**

Log live xuất hiện ngay trong **Console Output**. Mỗi dòng log có timestamp.

> **Ví dụ console:**
> ```
> [10:31:05] [INSTALL] Đang cài Pdf2.7.0_2394.apk...
> [10:31:22] [INFO] Appium session created: emulator-5554
> [10:31:35] PASSED  TC_SM_001 test_app_launches_without_crash
> [10:31:48] FAILED  TC_SM_002 test_no_crash_dialog
> ```

**Nút điều khiển:**

| Nút | Chức năng |
|---|---|
| **Start** | Bắt đầu chạy test |
| **Stop** | Dừng test đang chạy (gửi SIGTERM cho pytest) |
| **Clear** | Xóa nội dung console |

**Màu sắc trong Console:**

| Màu | Ý nghĩa |
|---|---|
| Xanh lá | Test PASSED |
| Đỏ đậm | Test FAILED |
| Đỏ nhạt | ERROR / exception |
| Xanh lam | `[CMD]` / `[INSTALL]` / `[INFO]` |
| Xám | Separator giữa các test |

---

### Tab Test Cases

Xem danh sách test case và chạy theo TC ID cụ thể.

**Bộ lọc:**

| Filter | Mô tả | Ví dụ |
|---|---|---|
| Tìm TC ID / tên | Tìm kiếm text | `TC_SM` hoặc `password` |
| Nhóm | Lọc theo nhóm | `Open Files`, `Smoke`... |
| Trạng thái | Lọc theo kết quả chạy gần nhất | `FAILED`, `NOT RUN`... |
| Chỉ TC tự động | Chỉ hiện TC đã có automation script | Bỏ tick để xem cả TC thủ công |

**Chọn và chạy theo TC ID:**

1. Dùng bộ lọc để tìm TC cần chạy
   > Ví dụ: lọc `FAILED` để chạy lại các TC lỗi
2. Tick các TC muốn chạy — chỉ TC có nhãn **Auto** mới tick được
3. Chọn **Device** ở thanh Run bar phía dưới màn hình
4. Bấm **Chạy TC đã chọn**
5. Console output hiện ngay bên dưới
6. Sau khi xong, bảng tự động refresh, cột **Last Result** cập nhật kết quả mới

**Nút nhanh:**
- **Chọn tất cả** — tick toàn bộ TC đang lọc (chỉ các TC có automation)
- **Bỏ chọn** — bỏ tick toàn bộ

> **Ví dụ workflow:** Sau khi chạy full suite, lọc theo `FAILED` → tick tất cả → chạy lại chỉ các TC lỗi để tiết kiệm thời gian.

---

### Tab Reports

Xem kết quả các lần chạy test trước đó.

- Mỗi lần chạy tạo 1 file `dashboard_YYYYMMDD_HHmmss.html`
- Click vào dòng để mở báo cáo HTML chi tiết
- Báo cáo bao gồm:
  - Biểu đồ tổng hợp PASS / FAIL / SKIP
  - Bảng chi tiết từng TC: kết quả, thời gian chạy, screenshot
  - Link tải file Excel kết quả (`.xlsx`)

> **Ví dụ:** `dashboard_20260509_103500.html` → session chạy lúc 10:35:00 ngày 09/05/2026

---

## 5. Trạng thái Test Case

| Trạng thái | Màu | Ý nghĩa |
|---|---|---|
| **PASS** | Xanh lá | Test chạy thành công, kết quả đúng với mong đợi |
| **FAIL** | Đỏ | Test thất bại — assertion sai hoặc exception không mong đợi |
| **SKIP** | Vàng | Test bị bỏ qua (điều kiện tiên quyết không đáp ứng) |
| **NEED CONFIRM** | Tím | Cần kiểm tra thủ công — automation không tự kết luận được |
| **NOT RUN** | Xám | Chưa được chạy trong session hiện tại |

### Giải thích chi tiết

**PASS** — Test thực thi hoàn tất, tất cả assertion đúng. Screenshot được lưu tự động tại `reports/screenshots/<timestamp>/TC_XXX_PASS.png`.

**FAIL** — Test gặp lỗi, thường do:
- `AssertionError` — màn hình hiển thị không đúng với mong đợi
- `NoSuchElementException` — không tìm thấy phần tử UI cần tương tác
- `TimeoutException` — phần tử không xuất hiện trong thời gian chờ
- `AppiumException` — app crash hoặc UiAutomator2 bị treo

Khi FAIL: screenshot + video (nếu bật) lưu tự động, log lỗi chi tiết trong báo cáo.

**SKIP** — Test bị bỏ qua, thường khi:
- Chưa có file PDF trong app (ví dụ: TC cần file có sẵn)
- Phiên bản app không hỗ trợ tính năng đó
- Code test gọi `pytest.skip("lý do")`

**NEED CONFIRM** — Automation không thể tự xác định đúng/sai. Dùng cho màn hình phụ thuộc dữ liệu thực của người dùng (ví dụ: notification, in-app purchase).

**NOT RUN** — TC có trong database nhưng chưa được chạy. Mỗi lần bắt đầu session mới, tất cả TC reset về NOT RUN.

---

## 6. Cấu trúc thư mục

```
auto-test/
├── start.command               # Double-click để start (macOS)
├── run.sh / run.bat            # Script khởi động (terminal)
├── setup.sh / setup.bat        # Cài đặt môi trường
├── server.py                   # Web server Flask (API + serve dashboard)
├── conftest.py                 # pytest fixtures: driver, screenshot, video
├── config.yaml                 # Cấu hình chính
├── requirements.txt            # Python dependencies
│
├── web/
│   └── index.html              # Giao diện Dashboard (single-page app)
│
├── core/
│   ├── adb_controller.py       # Wrapper ADB (install, launch, screenshot)
│   ├── app_installer.py        # Logic cài / update APK lên device
│   └── device_manager.py       # Quản lý device settings
│
├── test_cases/
│   ├── test_cases.xlsx         # Database test case (~80 TC)
│   ├── tc_manager.py           # Đọc/ghi kết quả test vào xlsx
│   ├── tc_pytest_plugin.py     # pytest plugin: ghi TC ID, sinh report
│   └── generate_html_report.py # Tạo file HTML dashboard
│
├── tests/
│   ├── helpers.py              # Hàm tiện ích UI (find, is_visible, go_to_home...)
│   └── test_suite/
│       ├── test_smoke.py               # TC_SM_001–004: cơ bản, không crash
│       ├── test_open_pdf.py            # TC_PDF_001–009: mở và đọc PDF
│       ├── test_pdf_tools.py           # TC_TOOL_001–007: Split, Merge, Sign...
│       ├── test_data_migration.py      # TC_DM_001–007: dữ liệu sau update
│       ├── test_open_files_other.py    # TC-026–040: mở PPTX/EPUB/TXT/DOCX/XLSX
│       ├── test_open_files_password.py # TC password PDF
│       └── test_notification.py        # TC notification
│
├── apks/                       # Đặt file APK vào đây trước khi test
└── reports/                    # Kết quả test tự động lưu vào đây
    ├── dashboard_YYYYMMDD_HHmmss.html
    ├── report_YYYYMMDD_HHmmss.xlsx
    ├── screenshots/
    │   └── YYYYMMDD_HHmmss/    # Ảnh chụp màn hình mỗi session
    └── videos/
        └── YYYYMMDD_HHmmss/    # Video quay màn hình mỗi session
```

---

## 7. Cấu hình config.yaml

File cấu hình chính của toàn bộ framework. Mỗi lần sửa, **không cần restart server** — chỉ cần chạy test mới là áp dụng.

```yaml
app:
  package_name: pdf.reader.pdf.viewer.all.document.reader.office.viewer
  main_activity: com.simple.pdf.reader.ui.main.SplashScreenActivity

apks:
  dir: apks                      # Thư mục chứa APK (relative từ project root)
  file: Pdf2.7.0_2394.apk        # APK mặc định nếu không chọn từ dashboard

device:
  exclude: []                    # Serial device muốn bỏ qua. Ví dụ: ["R3CN90B1234"]
  launch_timeout: 15             # Giây chờ app khởi động sau khi launch
  ui_timeout: 10                 # Giây chờ UI element xuất hiện

appium:
  host: 127.0.0.1
  port: 4723

test:
  screenshot_on_failure: true    # Chụp màn hình tự động khi test FAIL
  record_video: true             # Bật quay video màn hình
  video_save_mode: always        # "always" = lưu tất cả | "on_failure" = chỉ khi fail
  video_quality: low             # "low" | "medium" | "high"
  step_delay: 1                  # Giây dừng giữa các bước (tăng nếu device chậm)
  retry_count: 1                 # Số lần retry khi test fail

test_pdfs:
  simple: tests/resources/sample_simple.pdf
  large: tests/resources/sample_large.pdf
```

### Điều chỉnh theo tình huống

**Device chậm / nhiều lag (emulator cũ, máy yếu):**
```yaml
device:
  launch_timeout: 25
  ui_timeout: 15
test:
  step_delay: 2.0
```

**Debug — lưu video mọi lúc để xem lại:**
```yaml
test:
  record_video: true
  video_save_mode: always
  video_quality: medium
```

**Chạy nhanh — chỉ lưu video khi fail, không retry:**
```yaml
test:
  record_video: true
  video_save_mode: on_failure
  video_quality: low
  retry_count: 0
```

**Bỏ qua thiết bị cụ thể:**
```yaml
device:
  exclude: ["R3CN90B1234", "emulator-5556"]
```

---

## 8. Viết Test Case mới

### Bước 1: Thêm vào Excel

Mở `test_cases/test_cases.xlsx`, sheet **Test Cases**, thêm dòng mới:

| Cột | Nội dung | Ví dụ |
|---|---|---|
| Testcase ID | ID duy nhất | `TC_SM_005` |
| Phân Cấp | Tên nhóm | `Smoke` |
| Nội Dung Test | Mô tả ngắn | `App không crash khi xoay màn hình` |
| Điều Kiện / Dữ Liệu Test | Tiền điều kiện | `App đang ở màn hình Home` |
| Các Bước Thực Hiện | Các bước thực hiện | `1. Xoay thiết bị sang landscape` |
| Kết Quả Mong Đợi | Kết quả đúng | `App không crash, hiển thị đúng layout` |

### Bước 2: Viết code automation

Thêm method vào class test phù hợp trong `tests/test_suite/`, hoặc tạo file mới:

```python
import pytest
from tests.helpers import find, is_visible, go_to_home

class TestSmoke:

    @pytest.fixture(autouse=True)
    def _ensure_tc_manager(self, tc_manager):
        """Bắt buộc inject tc_manager để kết quả được ghi vào report."""
        pass

    @pytest.mark.tc_id("TC_SM_005")
    def test_no_crash_on_rotate(self, driver, cfg):
        """App không crash khi xoay màn hình."""
        go_to_home(driver, cfg)

        # Xoay sang landscape
        driver.orientation = "LANDSCAPE"
        import time; time.sleep(1)

        # Kiểm tra app vẫn hiển thị (không crash)
        assert is_visible(driver, "bottom_navigation", timeout=5), \
            "Bottom nav không còn sau khi xoay màn hình"

        # Xoay lại portrait
        driver.orientation = "PORTRAIT"
```

> **Quy tắc đặt tên:**
> - Class: `TestTenNhom` — pytest tự nhận diện
> - Method: `test_ten_tc` — bắt đầu bằng `test_`
> - Marker: `@pytest.mark.tc_id("TC_XXX")` — **bắt buộc** để ghi vào report

### Bước 3: Chạy thử TC mới

```bash
# Chạy đúng TC vừa viết
pytest tests/test_suite/test_smoke.py::TestSmoke::test_no_crash_on_rotate -v -s

# Kiểm tra marker được nhận diện
pytest tests/test_suite/test_smoke.py --collect-only | grep TC_SM_005
```

### Các hàm tiện ích trong helpers.py

| Hàm | Mô tả | Ví dụ |
|---|---|---|
| `find(driver, rid, timeout=10)` | Tìm element theo resource-id | `find(driver, "btn_home")` |
| `find_all(driver, rid, timeout=10)` | Tìm tất cả element cùng ID | `items = find_all(driver, "file_item")` |
| `find_text(driver, text)` | Tìm element theo text chính xác | `find_text(driver, "Open with")` |
| `find_text_contains(driver, text)` | Tìm element chứa text | `find_text_contains(driver, "PDF")` |
| `is_visible(driver, rid, timeout=5)` | Kiểm tra element có hiển thị | `assert is_visible(driver, "toolbar")` |
| `go_to_home(driver, cfg)` | Về màn hình Home của app | Gọi ở đầu mỗi test |
| `dismiss_ads(driver, cfg)` | Đóng quảng cáo nếu đang hiện | Gọi sau khi mở file |
| `wait_uia2_ready(driver, timeout=40)` | Chờ UiAutomator2 phục hồi sau crash | Gọi sau khi File Chooser đóng |

### Các fixture có sẵn

| Fixture | Scope | Mô tả |
|---|---|---|
| `driver` | function | Appium WebDriver — tự restart trước mỗi test |
| `adb` | session | `ADBController` — dùng `adb.install()`, `adb.screenshot()` |
| `cfg` | session | Dict từ `config.yaml` — dùng `cfg["device"]["ui_timeout"]` |
| `tc_manager` | session | Ghi kết quả vào Excel report — phải inject để report hoạt động |

---

## 9. Chạy test từ dòng lệnh

Dùng khi muốn debug trực tiếp, không qua dashboard.

```bash
# Kích hoạt virtualenv trước
source .venv/bin/activate
```

**Chạy một TC cụ thể:**
```bash
pytest tests/test_suite/test_smoke.py::TestSmoke::test_app_launches_without_crash -v -s
```

**Chạy một nhóm (class):**
```bash
pytest tests/test_suite/test_smoke.py::TestSmoke -v -s
```

**Chạy toàn bộ một file:**
```bash
pytest tests/test_suite/test_open_files_password.py -v -s
```

**Chạy toàn bộ test suite:**
```bash
pytest tests/test_suite/ -v -s
```

**Chỉ định thiết bị:**
```bash
TEST_DEVICE_SERIAL=emulator-5554 pytest tests/test_suite/ -v -s
```

**Chạy kèm init app (clear data, cài lại APK):**
```bash
RUN_INIT=1 TEST_DEVICE_SERIAL=emulator-5554 pytest tests/test_suite/test_smoke.py -v -s
```

**Chạy kèm cài APK cụ thể:**
```bash
RUN_INIT=1 INSTALL_APK=Pdf2.7.0_2394.apk pytest tests/test_suite/ -v -s
```

**Chỉ xem danh sách TC (không chạy):**
```bash
pytest tests/test_suite/ --collect-only
```

> **Biến môi trường:**
>
> | Biến | Mô tả | Ví dụ |
> |---|---|---|
> | `TEST_DEVICE_SERIAL` | Serial thiết bị cần dùng | `emulator-5554` |
> | `RUN_INIT` | Chạy bước khởi tạo app trước test | `RUN_INIT=1` |
> | `INSTALL_APK` | Tên APK cần cài (trong thư mục `apks/`) | `Pdf2.7.0_2394.apk` |

---

## 10. Câu hỏi thường gặp

**Q: Dashboard hiện "Không có device nào"?**
> Chạy `adb devices` trong terminal. Device phải ở trạng thái `device` (không phải `offline` hay `unauthorized`).
> - Với wireless debugging: chạy `adb connect 192.168.1.x:5555` trước.
> - Với emulator: đảm bảo emulator đã boot xong (màn hình unlock được).

**Q: Lỗi "Failed to create session" khi chạy test?**
> Appium chưa chạy. Khởi động lại bằng:
> ```bash
> appium --port 4723 &
> ```
> Hoặc dùng `./run.sh` — script tự start Appium trước.

**Q: Test bị treo / timeout?**
> Tăng timeout trong `config.yaml`:
> ```yaml
> device:
>   launch_timeout: 25
>   ui_timeout: 15
> ```
> Nguyên nhân thường do: device lag, quảng cáo đang hiển thị, hoặc app chưa load xong.

**Q: Không thấy report sau khi chạy test?**
> Report chỉ sinh ra khi test **kết thúc bình thường** (không bị Stop giữa chừng).
> Vào tab **Reports** → bấm **Refresh** để tải danh sách mới.

**Q: Screenshot không có trong report?**
> Screenshot lưu tại `reports/screenshots/YYYYMMDD_HHmmss/`.
> Tên file: `TC_XXX_test_method_name_PASS.png` hoặc `_FAIL.png`.
> Kiểm tra `screenshot_on_failure: true` trong `config.yaml`.

**Q: Làm sao tìm resource ID của một element trong app?**
> Có 2 cách:
> - **Appium Inspector** (app riêng): kết nối tới session đang chạy, duyệt UI tree và copy resource ID.
> - **ADB dump**: `adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml` — mở file XML để tìm `resource-id`.

**Q: UiAutomator2 bị crash giữa chừng?**
> Framework có cơ chế tự phục hồi 2 cấp:
> - **Cấp 1:** `adb shell input keyevent KEYCODE_HOME` để về Home, thử lại
> - **Cấp 2:** Restart toàn bộ Appium server và tạo session mới
>
> Nếu crash liên tục, xem log chi tiết tại `reports/logs/<timestamp>/`.

**Q: Muốn chạy test upgrade (cài version cũ → mới)?**
> 1. Upload cả 2 APK vào tab **APKs**
> 2. Tab **Run Tests** → tick APK cũ trước, APK mới sau
> 3. Chọn test class `TestDataMigration`
> 4. Bấm **Start** — hệ thống cài theo thứ tự, sau đó chạy test kiểm tra dữ liệu còn nguyên
