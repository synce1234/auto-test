"""
pytest plugin - Tự động map pytest test name → TC ID → ghi kết quả Excel.

Cách dùng trong test function:
  def test_open_pdf(self, driver, cfg, tc_result):
      tc_result.tc_id = "TC_001"          # khai báo TC ID
      # ... test steps ...
      tc_result.actual = "Mở PDF thành công"

Plugin sẽ tự động:
  - Đọc tc_id từ fixture tc_result
  - Ghi PASS/FAIL/SKIP + actual result vào TCManager
  - Generate Excel report khi session kết thúc
"""
import time
import datetime
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_cases.tc_manager import TCManager


# ─── Shared state ─────────────────────────────────────────────────────────────

# Timestamp tạo lúc session bắt đầu — dùng chung cho tên report và thư mục lưu assets
SESSION_TIMESTAMP: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

class _TCResult:
    """Object fixture truyền vào test để khai báo TC ID và actual result."""
    def __init__(self):
        self.tc_id  = None
        self.actual = ""
        self.notes  = ""
        self._start = time.time()

    @property
    def duration(self) -> float:
        return time.time() - self._start


# ─── Module-level state (để pytest_sessionfinish truy cập được) ───────────────

_session_tc_manager: TCManager | None = None


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tc_manager():
    """TCManager dùng chung cho cả session."""
    global _session_tc_manager
    _session_tc_manager = TCManager()
    return _session_tc_manager


@pytest.fixture
def tc_result():
    """Fixture inject vào mỗi test để khai báo TC ID và actual result."""
    return _TCResult()


# ─── Hook: ghi kết quả sau mỗi test ──────────────────────────────────────────

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    start = time.time()
    outcome = yield
    duration = time.time() - start

    # Lấy tc_result fixture nếu test có dùng
    tc_result_obj = item.funcargs.get("tc_result")
    tc_mgr        = item.funcargs.get("tc_manager")

    if not tc_result_obj or not tc_mgr:
        return

    tc_id = tc_result_obj.tc_id
    if not tc_id:
        return

    exc = outcome.get_result() if not outcome.excinfo else None
    if outcome.excinfo:
        status = "FAIL"
        actual = tc_result_obj.actual or str(outcome.excinfo[1])
    else:
        status = "PASS"
        actual = tc_result_obj.actual or "Test passed"

    tc_mgr.update_result(
        tc_id=tc_id,
        status=status,
        actual=actual,
        duration=duration,
        notes=tc_result_obj.notes,
    )


# ─── Hook: generate report khi session kết thúc ───────────────────────────────

def pytest_sessionfinish(session, exitstatus):
    """Tự động save Excel report và generate HTML dashboard sau khi chạy xong."""
    tc_mgr = _session_tc_manager
    if not tc_mgr or not tc_mgr._results:
        return

    ts = SESSION_TIMESTAMP
    report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    # 1. Lưu Excel report
    xlsx_path = os.path.join(report_dir, f"report_{ts}.xlsx")
    tc_mgr.save_report(xlsx_path)

    # 2. Generate HTML dashboard (truyền run_ts để tìm đúng thư mục screenshot/video)
    try:
        from test_cases.generate_html_report import generate
        html_path = generate(
            source_xlsx=xlsx_path,
            output=os.path.join(report_dir, f"dashboard_{ts}.html"),
            run_ts=ts,
        )
        print(f"\n[DASHBOARD] {html_path}")
    except Exception as e:
        print(f"\n[DASHBOARD FAILED] {e}")
