"""Editor command for an explicit one-click ADB transfer."""

from ..shared import *  # noqa: F401,F403
from ..adb import AdbLocator, AdbTransfer, AdbTransferError


class AdbTransferMixin:
    def cmd_adb_transfer(self):
        self.cmd_save()
        memory = self.memory
        archive = memory["archive"]
        path = archive["path"]
        if not path or memory["dirty"]:
            return
        try:
            executable = AdbLocator.find()
            device, destination = AdbTransfer(executable, path).send()
        except (AdbTransferError, OSError) as error:
            messagebox.showerror(APP_TITLE, f"端末転送に失敗しました:\n{error}")
            return
        memory["status"].configure(
            text=f"端末 {device} へ転送しました: {destination}")
        messagebox.showinfo(
            APP_TITLE, "KLWPへ転送しました。\nKLWPの読み込み画面から選択してください。")
