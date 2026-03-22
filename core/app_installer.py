"""
App Installer - Quản lý flow cài đặt và update APK
"""
import os
import time
from core.adb_controller import ADBController


class AppInstaller:
    def __init__(self, adb: ADBController, package_name: str):
        self.adb = adb
        self.package_name = package_name

    def clean_install(self, apk_path: str) -> bool:
        """
        Cài sạch: gỡ app cũ (xóa data) → cài APK mới.
        Dùng ở B1: cài APK version cũ.
        """
        print(f"\n[INSTALL] Clean install: {os.path.basename(apk_path)}")

        if self.adb.is_app_installed(self.package_name):
            print("  Gỡ app cũ...")
            self.adb.uninstall_app(self.package_name)
            time.sleep(2)

        success = self.adb.install_apk(apk_path, replace=False)
        if success:
            version = self.adb.get_installed_version(self.package_name)
            print(f"  Version đã cài: {version}")
        return success

    def update_install(self, apk_path: str) -> bool:
        """
        Update: cài đè APK mới, GIỮ NGUYÊN data người dùng.
        Dùng ở B2: update lên APK mới nhất.
        """
        print(f"\n[UPDATE] Update lên: {os.path.basename(apk_path)}")

        version_before = self.adb.get_installed_version(self.package_name)
        print(f"  Version trước: {version_before}")

        success = self.adb.install_apk(apk_path, replace=True)

        if success:
            version_after = self.adb.get_installed_version(self.package_name)
            print(f"  Version sau:   {version_after}")
            if version_before == version_after:
                print("  [WARN] Version không đổi sau update!")
        return success

    def setup_initial_data(self, activity: str, launch_timeout: int = 15):
        """
        Mở app lần đầu để khởi tạo data (SharedPreferences, DB, v.v.)
        sau khi clean install APK cũ.
        """
        print("\n[SETUP] Khởi động app để init data...")
        self.adb.launch_app(self.package_name, activity)
        time.sleep(launch_timeout)
        self.adb.force_stop_app(self.package_name)
        print("  [OK] App đã init data xong")

    def get_apk_list(self, apks_dir: str) -> list[str]:
        """
        Quét folder apks/ và trả về danh sách file APK (sắp xếp theo tên).
        """
        if not os.path.isdir(apks_dir):
            return []
        files = sorted([
            os.path.join(apks_dir, f)
            for f in os.listdir(apks_dir)
            if f.endswith(".apk")
        ])
        return files
