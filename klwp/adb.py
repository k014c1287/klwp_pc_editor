"""Transfer a saved KLWP preset to one connected Android device."""

import os
from pathlib import Path
import shutil
import subprocess


REMOTE_DIRECTORY = "/sdcard/Kustom/wallpapers"


class AdbTransferError(RuntimeError):
    pass


class AdbLocator:
    @staticmethod
    def find():
        executable = shutil.which("adb")
        if executable:
            return executable
        candidates = AdbLocator._sdk_candidates()
        located = next(filter(AdbLocator._exists, candidates), None)
        if located is None:
            raise AdbTransferError(
                "adbが見つかりません。Android SDK Platform-Toolsを導入してください。")
        return str(located)

    @staticmethod
    def _sdk_candidates():
        environment = os.environ
        local_data = environment.get("LOCALAPPDATA", "")
        sdk_home = environment.get("ANDROID_HOME", "")
        sdk_root = environment.get("ANDROID_SDK_ROOT", "")
        return (
            Path(local_data) / "Android/Sdk/platform-tools/adb.exe",
            Path(sdk_home) / "platform-tools/adb.exe",
            Path(sdk_root) / "platform-tools/adb.exe",
        )

    @staticmethod
    def _exists(path):
        return bool(str(path)) and path.is_file()


class AdbDevices:
    @staticmethod
    def connected(output):
        lines = output.splitlines()
        devices = map(AdbDevices._device_from_line, lines)
        return tuple(filter(None, devices))

    @staticmethod
    def _device_from_line(line):
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
        return None

    @staticmethod
    def require_one(output):
        devices = AdbDevices.connected(output)
        if not devices:
            raise AdbTransferError(
                "接続済み端末がありません。USBデバッグの許可を確認してください。")
        if len(devices) > 1:
            raise AdbTransferError(
                "複数端末が接続されています。転送先を1台にしてください。")
        return devices[0]


class AdbTransfer:
    def __init__(self, executable, source):
        self._executable = str(executable)
        self._source = Path(source)

    def send(self):
        source = self._source
        if not source.is_file():
            raise AdbTransferError("転送するKLWPファイルが見つかりません。")
        devices = self._execute(("devices",))
        device = AdbDevices.require_one(devices)
        prefix = ("-s", device)
        self._execute(prefix + ("shell", "mkdir", "-p", REMOTE_DIRECTORY))
        destination = self.destination()
        self._execute(prefix + ("push", str(self._source), destination))
        return device, destination

    def destination(self):
        source = self._source
        return REMOTE_DIRECTORY + "/" + source.name

    def _execute(self, arguments):
        command = [self._executable, *arguments]
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=30, check=False)
        if result.returncode == 0:
            return result.stdout
        standard_error = result.stderr
        standard_output = result.stdout
        detail = standard_error.strip() or standard_output.strip()
        raise AdbTransferError(detail or "adbコマンドに失敗しました。")
