# Hướng Dẫn Sử Dụng Auto Test Bot

Framework kiểm thử tự động cho ứng dụng Android PDF Reader, sử dụng Appium + pytest với Web Dashboard tích hợp.

---

## Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt](#2-cài-đặt)
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
| Python | 3.10+ | |
| Node.js | 18+ | Cần để chạy Appium |
| Java (JDK) | 17+ | Cần cho UIAutomator2 |
| Android SDK | Build-tools + Platform-tools | Cài cùng Android Studio |
| Appium | 2.x | Tự cài qua `setup.sh` |
| UIAutomator2 driver | latest | Tự cài qua `setup.sh` |

> **Lưu ý:** Đảm bảo `adb` có trong `$PATH`. Kiểm tra bằng lệnh `adb version`.

---

## 2. Cài đặt

### macOS / Linux

```bash
cd auto-test/
chmod +x setup.sh
./setup.sh
```

Script `setup.sh` tự động:
1. Kiểm tra và cài Python 3, Node.js, Java
2. Cài Appium 2 và UIAutomator2 driver
3. Tạo Python virtualenv (`.venv/`) và cài các package
4. Khởi động Appium server
5. Mở Dashboard tại `http://localhost:8080`

### Windows

```bat
setup.bat
```

### Tùy chọn nâng cao

```bash
./setup.sh --install          # Chỉ cài đặt, không start
./setup.sh --start            # Chỉ start (đã cài trước đó)
./setup.sh --port 9090        # Đổi port (mặc định: 8080)
./setup.sh --dir /path/proj   # Chỉ định thư mục project
```

---

## 3. Khởi động Dashboard

```bash
# Cách 1: Dùng setup.sh
./setup.sh --start

# Cách 2: Chạy trực tiếp
source .venv/bin/activate
python server.py

# Cách 3: Đổi port
python server.py --port 9090
```

Mở trình duyệt: **http://localhost:8080**

> Appium server phải đang chạy trước khi bấm Start test. Kiểm tra tại `http://localhost:4723/status`.

---

## 4. Hướng dẫn dùng Dashboard

### Tab APKs

Quản lý các file APK để cài lên device trước khi test.

**Upload APK:**
- Kéo thả file `.apk` vào vùng upload, hoặc click để chọn file
- Sau khi upload, dashboard tự động đọc version name và version code từ APK

**Xóa APK:**
- Click nút `Delete` ở cuối mỗi dòng

**Thông tin hiển thị:**
| Cột | Mô tả |
|---|---|
| Filename | Tên file APK |
| Version Name | Version hiển thị (vd: `2.6.9`) |
| Version Code | Version code nội bộ (vd: `269`) |
| Size | Dung lượng file (MB) |
| Modified | Thời điểm upload |

---

### Tab Run Tests

Chạy test theo nhóm file hoặc class cụ thể.

**Quy trình:**

1. **Chọn Device** — danh sách tự động hiện các device đang kết nối qua ADB
2. **Chọn APK cài (tùy chọn)** — tick các APK muốn cài lên device trước khi test; hệ thống cài theo thứ tự từ trên xuống
3. **Chọn Test Scripts** — tick class test muốn chạy (mỗi class tương ứng một nhóm test case)
4. **Bấm Start** — log live xuất hiện ngay trong Console Output

**Nút điều khiển:**
| Nút | Chức năng |
|---|---|
| Start | Bắt đầu chạy test |
| Stop | Dừng test đang chạy (gửi SIGTERM cho pytest) |
| Clear | Xóa nội dung console |

**Màu sắc trong Console:**
| Màu | Ý nghĩa |
|---|---|
| Xanh lá | Test PASSED |
| Đỏ | Test FAILED |
| Đỏ nhạt | ERROR / exception |
| Xanh lam | [CMD] / [INSTALL] / [INFO] |
| Xám | Log separator |

---

### Tab Test Cases

Xem và chọn từng test case để chạy theo TC ID.

**Bộ lọc:**
| Filter | Mô tả |
|---|---|
| Tìm TC ID / tên | Tìm kiếm theo ID hoặc nội dung test |
| Tất cả nhóm | Lọc theo nhóm (Smoke, Open PDF, PDF Tools...) |
| Tất cả status | Lọc theo trạng thái chạy gần nhất |
| Chỉ TC tự động | Chỉ hiện các TC đã có automation script |

**Chọn và chạy:**
1. Tick các TC muốn chạy (chỉ các TC có nhãn **Auto** mới tick được)
2. Chọn **Device** ở thanh Run bar phía dưới
3. Bấm **Chạy TC đã chọn**
4. Console output hiện ngay bên dưới
5. Sau khi xong, bảng TC tự động refresh để cập nhật status mới

**Nút nhanh:**
- **Chọn tất cả** — tick toàn bộ TC đang hiển thị (có automation)
- **Bỏ chọn** — bỏ tick toàn bộ

---

### Tab Reports

Xem kết quả các lần chạy test.

- Mỗi lần chạy tạo ra 1 file `dashboard_YYYYMMDD_HHmmss.html`
- Click vào dòng để xem báo cáo HTML tương ứng
- Báo cáo bao gồm:
  - Biểu đồ tổng hợp PASS / FAIL / SKIP
  - Bảng chi tiết từng TC: kết quả thực tế, thời gian chạy, screenshot
  - Link tải file Excel kết quả (`.xlsx`)
  - Nút "Mở tab mới" để xem toàn màn hình

---

## 5. Trạng thái Test Case

### Các trạng thái trong Dashboard

| Trạng thái | Màu | Ý nghĩa |
|---|---|---|
| **PASS** | Xanh lá | Test chạy thành công, kết quả đúng với mong đợi |
| **FAIL** | Đỏ | Test thất bại — assertion sai hoặc exception không mong đợi |
| **SKIP** | Vàng | Test bị bỏ qua (thường do điều kiện tiên quyết không đáp ứng) |
| **NEED CONFIRM** | Tím | Kết quả không rõ ràng, cần kiểm tra thủ công |
| **NOT RUN** | Xám | Test chưa được chạy lần nào |

### Giải thích chi tiết

#### PASS
Test case thực thi hoàn tất, tất cả assertion đều đúng. Screenshot trạng thái cuối được lưu tự động.

#### FAIL
Test case gặp lỗi:
- **Assertion Error** — màn hình hiển thị không đúng với kết quả mong đợi
- **NoSuchElementException** — không tìm thấy phần tử UI cần tương tác
- **TimeoutException** — phần tử không xuất hiện trong thời gian chờ
- **AppiumException** — lỗi từ driver (thường do app crash)

Khi FAIL: screenshot + video (nếu bật) được lưu tự động, log lỗi chi tiết trong báo cáo.

#### SKIP
Test bị bỏ qua, thường xảy ra khi:
- Dữ liệu test chưa có (ví dụ: chưa có file PDF nào trong app)
- Phiên bản app không hỗ trợ tính năng đó
- Code test gọi `pytest.skip("lý do")`

#### NEED CONFIRM
Test kết thúc bằng `pytest.skip("NEED CONFIRM: ...")`. Ý nghĩa: automation không thể tự xác định kết quả đúng/sai — cần người kiểm tra thêm. Thường dùng cho các màn hình phụ thuộc dữ liệu người dùng.

#### NOT RUN
Test case có trong database nhưng chưa được chạy trong session hiện tại. Mỗi lần bắt đầu session mới, tất cả TC reset về NOT RUN.

### Nhóm Test Case

| Nhóm | Prefix | Mô tả |
|---|---|---|
| Smoke | `TC_SM_` | Kiểm tra cơ bản: app khởi động, không crash |
| Open PDF | `TC_PDF_` | Mở file PDF, viewer, navigation |
| PDF Tools | `TC_TOOL_` | Công cụ: Split, Merge, Sign, Scanner |
| Data Migration | `TC_DM_` | Dữ liệu còn nguyên sau khi update app |
| Open Files | `TC_` (số) | Mở các loại file khác nhau từ app và từ app khác |

---

## 6. Cấu trúc thư mục

```
auto-test/
├── setup.sh / setup.bat        # Cài đặt + khởi động
├── server.py                   # Web server (Flask API)
├── config.yaml                 # Cấu hình chính
├── requirements.txt            # Python dependencies
│
├── web/
│   └── index.html              # Giao diện Dashboard (single-page app)
│
├── core/
│   ├── adb_controller.py       # Wrapper ADB (install, launch, screenshot)
│   ├── app_installer.py        # Logic cài / update APK
│   └── device_manager.py       # Quản lý device settings
│
├── test_cases/
│   ├── test_cases.xlsx         # Database test case (81 TC)
│   ├── tc_manager.py           # Đọc/ghi kết quả test vào xlsx
│   ├── tc_pytest_plugin.py     # pytest plugin: tích hợp TC ID, sinh report
│   └── generate_html_report.py # Tạo file HTML dashboard
│
├── tests/
│   ├── conftest.py             # pytest fixtures: driver, screenshot, video
│   ├── helpers.py              # Hàm tiện ích UI (find, is_visible, go_to_home)
│   └── test_suite/
│       ├── test_smoke.py           # TC_SM_001–004
│       ├── test_open_pdf.py        # TC_PDF_001–009
│       ├── test_pdf_tools.py       # TC_TOOL_001–007
│       ├── test_data_migration.py  # TC_DM_001–007
│       ├── test_open_files_other.py
│       ├── test_open_files_password.py
│       └── test_notification.py
│
├── apks/                       # Đặt file APK vào đây
└── reports/                    # Kết quả test tự động lưu
    ├── dashboard_YYYYMMDD_HHmmss.html
    ├── report_YYYYMMDD_HHmmss.xlsx
    ├── screenshots/
    │   └── YYYYMMDD_HHmmss/    # Screenshot mỗi session
    └── videos/
        └── YYYYMMDD_HHmmss/    # Video mỗi session
```

---

## 7. Cấu hình config.yaml

```yaml
app:
  package_name: "pdf.reader.pdf.viewer..."   # Package name Android
  main_activity: "com...SplashScreenActivity" # Activity khởi động

apks:
  dir: "apks"                  # Thư mục chứa APK

appium:
  host: "127.0.0.1"            # Appium server host
  port: 4723                   # Appium server port

device:
  exclude: []                  # Serial device muốn bỏ qua (để trống = dùng tất cả)
  launch_timeout: 15           # Giây chờ app khởi động sau khi launch
  ui_timeout: 10               # Giây chờ UI element xuất hiện

test:
  record_video: false          # Bật/tắt quay video
  video_save_mode: "on_failure" # "always" | "on_failure"
  video_quality: "low"         # "low" | "medium" | "high"
  step_delay: 1.0              # Giây dừng giữa các bước (tăng nếu device chậm)
  retry_count: 1               # Số lần retry khi test fail
```

### Điều chỉnh theo môi trường

**Device chậm / nhiều lag:**
```yaml
device:
  launch_timeout: 25
  ui_timeout: 15
test:
  step_delay: 2.0
```

**Bật quay video để debug:**
```yaml
test:
  record_video: true
  video_save_mode: "on_failure"  # Chỉ lưu khi fail để tiết kiệm dung lượng
  video_quality: "medium"
```

---

## 8. Viết Test Case mới

### Bước 1: Thêm vào Excel

Mở `test_cases/test_cases.xlsx`, sheet **Test Cases**, thêm dòng mới:

| Cột | Nội dung |
|---|---|
| Testcase ID | `TC_XXX` hoặc `TC_GROUP_XXX` |
| Phân Cấp | Tên nhóm (Smoke, Open PDF...) |
| Nội Dung Test | Mô tả ngắn gọn |
| Điều Kiện / Dữ Liệu Test | Dữ liệu cần có trước khi test |
| Các Bước Thực Hiện | Mô tả từng bước |
| Kết Quả Mong Đợi | Kết quả đúng |

### Bước 2: Viết code automation

Thêm method vào file test phù hợp trong `tests/test_suite/`, hoặc tạo file mới:

```python
import pytest
from tests.helpers import find, is_visible, go_to_home

class TestTenNhom:

    @pytest.fixture(autouse=True)
    def setup(self, driver, cfg, tc_manager):
        go_to_home(driver, cfg)
        yield

    @pytest.mark.tc_id("TC_XXX")
    def test_ten_test_case(self, driver):
        """Mô tả test case."""
        # 1. Thao tác với app
        find(driver, "resource_id_cua_element").click()

        # 2. Kiểm tra kết quả
        assert is_visible(driver, "element_ket_qua", timeout=5), \
            "Màn hình X không hiển thị (Expected: ...)"
```

### Hàm tiện ích trong helpers.py

| Hàm | Mô tả |
|---|---|
| `find(driver, rid, timeout=10)` | Tìm element theo resource-id, raise nếu không thấy |
| `find_all(driver, rid, timeout=10)` | Tìm tất cả element cùng resource-id |
| `find_text_contains(driver, text)` | Tìm element chứa text |
| `is_visible(driver, rid, timeout=5)` | Kiểm tra element có hiển thị không |
| `go_to_home(driver, cfg)` | Về màn hình Home của app |
| `dismiss_onboarding(driver, cfg)` | Bỏ qua màn onboarding nếu có |

### Fixture có sẵn

| Fixture | Scope | Mô tả |
|---|---|---|
| `driver` | session | Appium WebDriver |
| `adb` | session | ADBController (adb shell, install...) |
| `cfg` | session | Dict từ config.yaml |
| `tc_manager` | session | Ghi kết quả vào report |

---

## 9. Chạy test từ dòng lệnh

```bash
# Kích hoạt virtualenv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows

# Chạy toàn bộ test suite
pytest tests/test_suite/ -v

# Chạy một nhóm cụ thể
pytest tests/test_suite/test_smoke.py -v
pytest tests/test_suite/test_open_pdf.py -v

# Chạy một class
pytest tests/test_suite/test_smoke.py::TestSmoke -v

# Chạy một test cụ thể
pytest tests/test_suite/test_smoke.py::TestSmoke::test_app_not_crash -v

# Chỉ định device
TEST_DEVICE_SERIAL=emulator-5554 pytest tests/test_suite/ -v

# Hiện log output
pytest tests/test_suite/ -v -s
```

---

## 10. Câu hỏi thường gặp

**Q: Dashboard hiện "Không có device nào"?**
> Kiểm tra: `adb devices` — device phải ở trạng thái `device` (không phải `offline` hay `unauthorized`). Với wireless debugging, chạy `adb connect IP:PORT` trước.

**Q: Test fail với lỗi "Failed to create session"?**
> Appium server chưa chạy. Khởi động lại bằng `./setup.sh --start` hoặc chạy `appium` thủ công.

**Q: Test bị treo / timeout?**
> Tăng `ui_timeout` và `launch_timeout` trong `config.yaml`. Nguyên nhân thường do device lag hoặc ad đang hiển thị.

**Q: Không thấy report sau khi chạy test?**
> Report chỉ sinh ra khi test kết thúc bình thường (không bị Stop giữa chừng). Vào tab Reports và bấm Refresh.

**Q: Screenshot không có trong report?**
> Screenshot lưu theo session timestamp tại `reports/screenshots/YYYYMMDD_HHmmss/`. Mỗi TC có ảnh tên `tc_id_funcname_PASS.png` hoặc `_FAIL.png`.

**Q: Muốn thêm TC nhưng không biết resource ID của element?**
> Dùng **Appium Inspector** (app riêng) để duyệt UI hierarchy và lấy resource ID. Hoặc dùng `adb shell uiautomator dump` để dump XML.
