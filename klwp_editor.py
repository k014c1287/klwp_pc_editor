#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KLWP Desktop Editor executable and backward-compatible public facade."""

import sys

from klwp import *  # noqa: F401,F403
from klwp import HAS_PIL, HAS_TK


def main():
    if not HAS_TK:
        print("tkinter が見つかりません。Windows 版 Python では標準搭載です。")
        sys.exit(1)
    if not HAS_PIL:
        print("警告: Pillow 未導入のため画像プレビューが無効です。"
              " (pip install pillow で有効化)")
    application = EditorApp()
    application.mainloop()


if __name__ == "__main__":
    main()
