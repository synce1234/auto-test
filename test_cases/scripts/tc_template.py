"""
Template cho mỗi file auto test script gắn với Test Case ID.

Cách dùng:
  1. Copy file này → đặt tên theo TC ID, vd: TC_001_open_pdf.py
  2. Điền TC_ID và implement test_run()
  3. Script tự động ghi kết quả vào Excel report
"""
import time
import sys
import os

# Thêm auto-test root vào path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from test_cases.tc_manager import TCManager

# ── Khai báo Test Case ID ──────────────────────────────────────────────────────
TC_ID = "TC_XXX"   # ← thay bằng ID thực tế


def test_run(driver, cfg) -> tuple[bool, str]:
    """
    Implement test steps tại đây.
    Trả về: (passed: bool, actual_result: str)
    """
    # TODO: implement test steps
    # Ví dụ:
    # from tests.helpers import find, go_to_home
    # go_to_home(driver, cfg)
    # el = find(driver, "rcv_all_file")
    # return el.is_displayed(), "Danh sách file hiển thị đúng"

    raise NotImplementedError(f"Chưa implement test cho {TC_ID}")


# ── Chạy độc lập (không qua pytest) ──────────────────────────────────────────

if __name__ == "__main__":
    tc = TCManager()
    info = tc.get(TC_ID)
    if not info:
        print(f"[WARN] Không tìm thấy {TC_ID} trong Excel")
    else:
        print(f"\n{'─'*50}")
        print(f"TC ID   : {info['id']}")
        print(f"Title   : {info['title']}")
        print(f"Steps   : {info['steps']}")
        print(f"Expected: {info['expected']}")
        print(f"{'─'*50}")
