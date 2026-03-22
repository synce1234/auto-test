"""
ADB Controller - Wrapper cho các lệnh ADB
"""
import subprocess
import time
import os
import glob as _glob


# ─── Tìm aapt2 trong Android SDK ──────────────────────────────────────────────

def _find_aapt2() -> str:
    """Tìm đường dẫn aapt2 mới nhất trong Android SDK build-tools."""
    sdk_root = os.environ.get(
        "ANDROID_SDK_ROOT",
        os.path.expanduser("~/Library/Android/sdk"),
    )
    candidates = sorted(
        _glob.glob(os.path.join(sdk_root, "build-tools", "*", "aapt2")),
        reverse=True,  # lấy version mới nhất
    )
    if candidates:
        return candidates[0]
    return "aapt2"  # fallback: hy vọng có trong PATH


AAPT2 = _find_aapt2()


class ADBController:
    def __init__(self, serial: str = ""):
        """
        serial: serial của device (để trống nếu chỉ có 1 device)
        """
        self.serial = serial
        self._prefix = ["adb", "-s", serial] if serial else ["adb"]

    def _run(self, cmd: list, timeout: int = 30) -> tuple[int, str, str]:
        """Chạy lệnh ADB, trả về (returncode, stdout, stderr)"""
        full_cmd = self._prefix + cmd
        print(f"  [ADB] {' '.join(full_cmd)}")
        result = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    # ─── Device ───────────────────────────────────────────────────────────────

    def get_connected_devices(self) -> list[str]:
        """Lấy danh sách device đang kết nối"""
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")[1:]  # bỏ dòng header
        devices = [
            line.split("\t")[0]
            for line in lines
            if line.strip() and "offline" not in line
        ]
        return devices

    def is_device_connected(self) -> bool:
        devices = self.get_connected_devices()
        if self.serial:
            return self.serial in devices
        return len(devices) > 0

    def wait_for_device(self, timeout: int = 60):
        """Chờ device sẵn sàng"""
        print("  [ADB] Chờ device sẵn sàng...")
        self._run(["wait-for-device"], timeout=timeout)

    # ─── APK Install / Uninstall ──────────────────────────────────────────────

    def install_apk(self, apk_path: str, replace: bool = False) -> bool:
        """
        Cài APK lên device.
        replace=True: giữ nguyên data (dùng khi update)
        """
        if not os.path.exists(apk_path):
            print(f"  [ERROR] APK không tồn tại: {apk_path}")
            return False

        cmd = ["install"]
        if replace:
            cmd.append("-r")  # replace existing app, giữ data
        cmd.append(apk_path)

        code, out, err = self._run(cmd, timeout=120)
        success = code == 0 and "Success" in out
        if success:
            print(f"  [OK] Cài thành công: {os.path.basename(apk_path)}")
        else:
            print(f"  [FAIL] Cài thất bại: {err or out}")
        return success

    def uninstall_app(self, package_name: str) -> bool:
        """Gỡ cài đặt app (xóa luôn data)"""
        code, out, err = self._run(["uninstall", package_name])
        success = "Success" in out
        if success:
            print(f"  [OK] Gỡ cài đặt thành công: {package_name}")
        else:
            print(f"  [INFO] App chưa được cài hoặc lỗi: {out}")
        return success

    def is_app_installed(self, package_name: str) -> bool:
        """Kiểm tra app đã được cài chưa"""
        _, out, _ = self._run(["shell", "pm", "list", "packages", package_name])
        return package_name in out

    def get_installed_version(self, package_name: str) -> str:
        """Lấy versionName của app đang cài"""
        _, out, _ = self._run([
            "shell", "dumpsys", "package", package_name,
            "|", "grep", "versionName"
        ])
        # fallback nếu pipe không work trên mọi shell
        code, out, _ = self._run([
            "shell", f"dumpsys package {package_name} | grep versionName"
        ])
        for line in out.splitlines():
            if "versionName" in line:
                return line.strip().split("=")[-1]
        return "unknown"

    # ─── App Launch / Stop ────────────────────────────────────────────────────

    def launch_app(self, package_name: str, activity: str) -> bool:
        """Khởi động app"""
        code, out, err = self._run([
            "shell", "am", "start", "-n", f"{package_name}/{activity}"
        ])
        return code == 0

    def force_stop_app(self, package_name: str):
        """Dừng app"""
        self._run(["shell", "am", "force-stop", package_name])

    def clear_app_data(self, package_name: str) -> bool:
        """Xóa data của app (reset như mới cài)"""
        code, out, _ = self._run(["shell", "pm", "clear", package_name])
        return "Success" in out

    # ─── Screenshot / Log ─────────────────────────────────────────────────────

    def take_screenshot(self, save_path: str) -> bool:
        """Chụp screenshot và lưu về máy"""
        remote_path = "/sdcard/screenshot_autotest.png"
        self._run(["shell", "screencap", "-p", remote_path])
        code, _, _ = self._run(["pull", remote_path, save_path])
        self._run(["shell", "rm", remote_path])
        if code == 0:
            print(f"  [OK] Screenshot: {save_path}")
        return code == 0

    def get_logcat(self, package_name: str, lines: int = 100) -> str:
        """Lấy log của app"""
        _, out, _ = self._run([
            "shell", "logcat", "-d", "-t", str(lines),
            f"--pid=$(pidof {package_name})"
        ], timeout=15)
        return out

    def clear_logcat(self):
        """Xóa log buffer"""
        self._run(["logcat", "-c"])

    def push_file(self, local_path: str, remote_path: str) -> bool:
        """Push file lên device"""
        code, _, err = self._run(["push", local_path, remote_path], timeout=60)
        return code == 0

    # ─── APK file info (không cần device) ────────────────────────────────────

    @staticmethod
    def get_apk_info(apk_path: str) -> dict:
        """
        Dùng aapt2 để lấy versionName và versionCode từ file APK.
        Trả về dict: {"version_name": "2.6.7", "version_code": 237, "package": "..."}
        """
        try:
            result = subprocess.run(
                [AAPT2, "dump", "badging", apk_path],
                capture_output=True, text=True, timeout=15,
            )
            info = {"version_name": "unknown", "version_code": 0, "package": ""}
            for line in result.stdout.splitlines():
                if line.startswith("package:"):
                    for part in line.split():
                        if part.startswith("name="):
                            info["package"] = part.split("=", 1)[1].strip("'")
                        elif part.startswith("versionCode="):
                            try:
                                info["version_code"] = int(part.split("=", 1)[1].strip("'"))
                            except ValueError:
                                pass
                        elif part.startswith("versionName="):
                            info["version_name"] = part.split("=", 1)[1].strip("'")
                    break
            return info
        except Exception as e:
            print(f"  [WARN] Không đọc được APK info: {e}")
            return {"version_name": "unknown", "version_code": 0, "package": ""}

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def wait(self, seconds: float):
        time.sleep(seconds)

    def get_device_info(self) -> dict:
        """Lấy thông tin cơ bản của device"""
        _, model, _ = self._run(["shell", "getprop", "ro.product.model"])
        _, android_ver, _ = self._run(["shell", "getprop", "ro.build.version.release"])
        _, sdk, _ = self._run(["shell", "getprop", "ro.build.version.sdk"])
        return {
            "model": model,
            "android_version": android_ver,
            "sdk": sdk,
            "serial": self.serial or "default",
        }
