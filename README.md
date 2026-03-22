# Android Auto Test Bot

Framework kiểm thử tự động cho ứng dụng Android, sử dụng Appium + pytest. Đi kèm web dashboard để quản lý APK, chạy test và xem kết quả.

---

## Tính năng

- **Web Dashboard** — giao diện local để upload APK, chọn test case, chạy test và xem báo cáo
- **Chạy test tự động** — dùng Appium UIAutomator2, hỗ trợ nhiều device song song
- **Báo cáo HTML** — dashboard tương tác với biểu đồ, lịch sử các lần chạy, screenshot và video từng test case
- **Quay video & chụp ảnh** — tự động ghi lại màn hình trong quá trình test
- **Quản lý test case qua Excel** — import/export test case từ file `.xlsx`

---

## Yêu cầu hệ thống

| Thành phần | Phiên bản |
|---|---|
| macOS / Linux | macOS 13+ hoặc Ubuntu 20.04+ |
| Python | 3.10+ |
| Node.js | 18+ |
| Java (JDK) | 17+ |
| Android SDK | Build-tools + Platform-tools (adb, aapt2) |
| Appium | 2.x |
| Appium UIAutomator2 driver | latest |

> Android SDK được cài cùng Android Studio. Đảm bảo `adb` có trong `$PATH`.

---

## Cài đặt nhanh

```bash
# Clone hoặc copy thư mục auto-test về máy
cd auto-test/

# Cài đặt đầy đủ rồi start server
./setup.sh
```

Script `setup.sh` sẽ tự động:
1. Kiểm tra và cài Python 3, Node.js, Java nếu chưa có
2. Cài Appium và UIAutomator2 driver
3. Tạo Python virtualenv (`.venv/`) và cài các package
4. Start Appium server
5. Mở Auto Test Dashboard tại `http://localhost:8080`

### Tùy chọn khi chạy setup.sh

```bash
./setup.sh                         # Cài đặt đầy đủ + start server
./setup.sh --install               # Chỉ cài đặt, không start
./setup.sh --start                 # Chỉ start server (đã cài trước đó)
./setup.sh --port 9090             # Đổi port (mặc định: 8080)
./setup.sh --dir /path/to/proj    # Chỉ định thư mục project
```

---

## Cấu trúc thư mục

```
auto-test/
├── setup.sh                    # Script cài đặt + chạy server
├── server.py                   # Web server (Flask)
├── config.yaml                 # Cấu hình chung
├── requirements.txt            # Python dependencies
│
├── web/
│   └── index.html              # Giao diện web dashboard
│
├── core/
│   ├── adb_controller.py       # Wrapper ADB (install, launch, screenshot...)
│   ├── app_installer.py        # Cài / update APK lên device
│   └── device_manager.py       # Quản lý device (animation, storage...)
│
├── test_cases/
│   ├── test_cases.xlsx         # Danh sách test case (nguồn sự thật)
│   ├── tc_manager.py           # Đọc/ghi kết quả từ xlsx
│   ├── tc_pytest_plugin.py     # pytest plugin tích hợp TC ID vào test
│   ├── generate_html_report.py # Sinh file dashboard HTML
│   ├── import_tc.py            # Import test case từ xlsx
│   ├── create_template.py      # Tạo file xlsx mẫu
│   └── scripts/
│       ├── conftest.py         # pytest fixtures (driver, screenshot, video)
│       ├── tc_template.py      # Template viết test case mới
│       └── test_open_app.py    # TC_001 → TC_007: kiểm thử màn hình mở app
│
├── tests/                      # Test suite cho update flow
│   ├── conftest.py
│   ├── helpers.py              # Hàm tiện ích (find, is_visible...)
│   └── test_suite/
│       ├── test_smoke.py
│       ├── test_open_pdf.py
│       ├── test_pdf_tools.py
│       └── test_data_migration.py
│
├── apks/                       # Đặt file APK vào đây
├── reports/                    # Kết quả tự động lưu tại đây
│   ├── dashboard_YYYYMMDD_HHmmss.html
│   ├── report_YYYYMMDD_HHmmss.xlsx
│   ├── screenshots/
│   └── videos/
│
└── orchestrator.py             # Chạy update flow đầy đủ (CLI)
```

---

## Hướng dẫn sử dụng

### 1. Chuẩn bị device

- Kết nối thiết bị Android qua USB hoặc bật **Wireless Debugging**
- Bật **USB Debugging** trong Developer Options
- Xác nhận device được nhận diện:
  ```bash
  adb devices
  ```

### 2. Mở Dashboard

```bash
./setup.sh --start
```

Mở trình duyệt: **http://localhost:8080**

### 3. Upload APK

Vào tab **APKs** → kéo thả file `.apk` vào vùng upload (hoặc click để chọn file).

### 4. Chạy test

Vào tab **Run Tests**:
1. Chọn **Device** từ danh sách tự động phát hiện
2. *(Tùy chọn)* Tích chọn APK muốn cài lên device trước khi test
3. Tích chọn **Test Cases** muốn chạy (từng class riêng lẻ)
4. Bấm **Start** → theo dõi log live trên trang

### 5. Xem kết quả

Vào tab **Reports** để xem dashboard HTML với:
- Biểu đồ tổng hợp pass/fail
- Bảng chi tiết từng test case kèm trạng thái, thời gian, kết quả thực tế
- Screenshot và video tương ứng từng test
- Lịch sử tất cả các lần chạy trước (click để xem lại)

---

## Viết test case mới

### Bước 1 — Thêm vào Excel

Mở `test_cases/test_cases.xlsx`, thêm dòng mới với các cột:

| TC ID | Nhóm | Nội dung | Các bước | Kết quả mong đợi |
|---|---|---|---|---|
| TC_010 | Open app | Mô tả ngắn | 1. Bước 1... | Màn hình X hiện ra |

### Bước 2 — Viết code

Tạo hoặc thêm class vào file trong `test_cases/scripts/`:

```python
class TestTC010:
    """TC_010 - Mô tả test case"""

    @pytest.fixture(autouse=True)
    def setup(self, driver, cfg):
        # Chuẩn bị trước khi test (nếu cần)
        yield
        # Dọn dẹp sau test (nếu cần)

    def test_something(self, driver, tc_result):
        tc_result.tc_id = "TC_010"
        # ... viết test logic ...
        assert condition, "Mô tả lỗi nếu fail"
```

> Xem `test_cases/scripts/tc_template.py` để biết thêm ví dụ.

### Fixtures có sẵn

| Fixture | Mô tả |
|---|---|
| `driver` | Appium WebDriver (session scope) |
| `adb` | ADBController — thao tác ADB trực tiếp |
| `cfg` | Dict config từ `config.yaml` |
| `tc_result` | Ghi TC ID và kết quả vào báo cáo |
| `fresh_launch` | Force-stop và relaunch app trước test |

---

## Cấu hình (`config.yaml`)

```yaml
app:
  package_name: "com.example.app"
  main_activity: "com.example.app.SplashActivity"

appium:
  host: "127.0.0.1"
  port: 4723

device:
  exclude: []           # Serial của device muốn bỏ qua
  launch_timeout: 15   # Giây chờ app khởi động
  ui_timeout: 10       # Giây chờ UI action

test:
  screenshot_on_failure: true
  record_video: true
  video_save_mode: "always"   # "always" | "on_failure"
  video_quality: "low"        # "low" | "medium" | "high"
```

---

## Chạy test thủ công (CLI)

```bash
# Kích hoạt virtualenv
source .venv/bin/activate

# Chạy toàn bộ test
pytest test_cases/scripts/ -v

# Chạy một test class
pytest test_cases/scripts/test_open_app.py::TestTC001 -v

# Chạy nhiều class
pytest test_cases/scripts/test_open_app.py::TestTC001 \
       test_cases/scripts/test_open_app.py::TestTC002 -v
```

---

## Dependencies

| Package | Mục đích |
|---|---|
| `Appium-Python-Client` | Appium Python client |
| `pytest` | Test framework |
| `PyYAML` | Đọc config.yaml |
| `selenium` | WebDriver base |
| `flask` | Web server cho dashboard |
| `werkzeug` | HTTP utilities |
| `openpyxl` | Đọc/ghi file .xlsx |

Cài toàn bộ:
```bash
pip install -r requirements.txt
```
