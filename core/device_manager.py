"""
Device Manager - Kiểm tra và chuẩn bị device trước khi test
"""
import subprocess
from core.adb_controller import ADBController


def get_all_connected_devices(exclude: list[str] = None) -> list[dict]:
    """
    Quét tất cả device đang kết nối qua ADB.
    Trả về list dict: [{"serial": "emulator-5554", "model": "...", "android": "..."}]
    """
    result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
    devices = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line or "offline" in line or "unauthorized" in line:
            continue
        serial = line.split()[0]
        if exclude and serial in exclude:
            continue

        adb = ADBController(serial)
        info = adb.get_device_info()
        devices.append({
            "serial":  serial,
            "model":   info["model"],
            "android": info["android_version"],
            "sdk":     info["sdk"],
        })
    return devices


class DeviceManager:
    def __init__(self, adb: ADBController):
        self.adb = adb
        self._device_info = None

    def check_device_ready(self) -> bool:
        """Kiểm tra device đã kết nối và sẵn sàng chưa"""
        if not self.adb.is_device_connected():
            print("[ERROR] Không tìm thấy device!")
            print("  - Kiểm tra USB debugging đã bật chưa")
            print("  - Chạy 'adb devices' để xem danh sách")
            return False

        info = self.get_device_info()
        print(f"[DEVICE] {info['serial']} | {info['model']} | Android {info['android_version']} (SDK {info['sdk']})")
        return True

    def get_device_info(self) -> dict:
        if not self._device_info:
            self._device_info = self.adb.get_device_info()
        return self._device_info

    def prepare_test_storage(self, package_name: str):
        """Cấp quyền storage cho app."""
        permissions = [
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
        ]
        print("[SETUP] Cấp quyền storage...")
        for perm in permissions:
            self.adb._run(["shell", "pm", "grant", package_name, perm])

    def push_test_pdfs(self, pdf_files: dict):
        """Push các file PDF test lên device."""
        print("[SETUP] Push test PDF files lên device...")
        remote_dir = "/sdcard/Download/autotest/"
        self.adb._run(["shell", "mkdir", "-p", remote_dir])
        for local_path, filename in pdf_files.items():
            remote_path = remote_dir + filename
            if self.adb.push_file(local_path, remote_path):
                print(f"  [OK] {filename}")
            else:
                print(f"  [WARN] Không push được: {filename}")

    def disable_animations(self):
        """Tắt animation để test nhanh và ổn định hơn."""
        print("[SETUP] Tắt animations...")
        for key in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
            self.adb._run(["shell", "settings", "put", "global", key, "0"])

    def restore_animations(self):
        """Bật lại animation về mặc định."""
        for key in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
            self.adb._run(["shell", "settings", "put", "global", key, "1"])
