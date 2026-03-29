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

# Collect ALL test outcomes (dùng khi không có TC IDs — e.g. test_data_migration)
_plain_results: list[dict] = []


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def tc_manager():
    """TCManager dùng chung cho cả session — autouse để luôn khởi tạo dù test file nào chạy."""
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


# ─── Hook: collect ALL test outcomes ─────────────────────────────────────────

def pytest_runtest_logreport(report):
    """Thu thập kết quả mọi test (kể cả không có TC ID) để sinh plain report."""
    if report.when != "call":
        return
    status = "PASS" if report.passed else ("SKIP" if report.skipped else "FAIL")
    _plain_results.append({
        "nodeid":   report.nodeid,
        "name":     report.nodeid.split("::")[-1],
        "status":   status,
        "duration": f"{report.duration:.2f}s",
        "longrepr": str(report.longrepr) if report.failed else "",
    })


def _generate_plain_html(results: list[dict], ts: str, output_path: str) -> str:
    """Sinh HTML đơn giản khi không có TC IDs — hiển thị kết quả từng test function."""
    total  = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped= sum(1 for r in results if r["status"] == "SKIP")
    rate   = f"{passed/total*100:.0f}%" if total else "N/A"

    status_color = {"PASS": "#C6EFCE", "FAIL": "#FFC7CE", "SKIP": "#FFEB9C"}

    rows_html = ""
    for r in results:
        color  = status_color.get(r["status"], "#FFF")
        detail = f'<details><summary>Error</summary><pre style="font-size:11px;white-space:pre-wrap">{r["longrepr"][:2000]}</pre></details>' if r["longrepr"] else ""
        rows_html += (
            f'<tr style="background:{color}">'
            f'<td style="padding:6px 10px;font-family:monospace;font-size:12px">{r["nodeid"]}</td>'
            f'<td style="padding:6px 10px;text-align:center;font-weight:bold">{r["status"]}</td>'
            f'<td style="padding:6px 10px;text-align:center">{r["duration"]}</td>'
            f'<td style="padding:6px 10px">{detail}</td>'
            f'</tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<title>Test Report {ts}</title>
<style>
body{{font-family:sans-serif;margin:24px;background:#f5f5f5}}
h1{{font-size:20px;margin-bottom:4px}}
.cards{{display:flex;gap:12px;margin:16px 0}}
.card{{background:#fff;border-radius:8px;padding:16px 24px;min-width:90px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.card .val{{font-size:28px;font-weight:700}}
.card .lbl{{font-size:12px;color:#666;margin-top:2px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th{{background:#333;color:#fff;padding:8px 10px;text-align:left;font-size:13px}}
td{{border-bottom:1px solid #eee}}
</style></head><body>
<h1>Test Report — {ts}</h1>
<div class="cards">
  <div class="card"><div class="val">{total}</div><div class="lbl">Total</div></div>
  <div class="card" style="background:#C6EFCE"><div class="val">{passed}</div><div class="lbl">PASS</div></div>
  <div class="card" style="background:#FFC7CE"><div class="val">{failed}</div><div class="lbl">FAIL</div></div>
  <div class="card" style="background:#FFEB9C"><div class="val">{skipped}</div><div class="lbl">SKIP</div></div>
  <div class="card"><div class="val">{rate}</div><div class="lbl">Pass rate</div></div>
</div>
<table>
<tr><th>Test</th><th>Status</th><th>Duration</th><th>Detail</th></tr>
{rows_html}
</table>
</body></html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


# ─── Hook: generate report khi session kết thúc ───────────────────────────────

def pytest_sessionfinish(session, exitstatus):
    """Tự động save Excel report và generate HTML dashboard sau khi chạy xong."""
    tc_mgr = _session_tc_manager
    ts = SESSION_TIMESTAMP
    report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    if tc_mgr and tc_mgr._results:
        # ── TC-based report (có @pytest.mark.tc_id hoặc tc_result fixture) ──
        xlsx_path = os.path.join(report_dir, f"report_{ts}.xlsx")
        tc_mgr.save_report(xlsx_path)

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

    elif _plain_results:
        # ── Plain report (không có TC IDs — e.g. test_data_migration) ──
        try:
            html_path = _generate_plain_html(
                results=_plain_results,
                ts=ts,
                output_path=os.path.join(report_dir, f"dashboard_{ts}.html"),
            )
            print(f"\n[DASHBOARD] {html_path}")
        except Exception as e:
            print(f"\n[DASHBOARD FAILED] {e}")
