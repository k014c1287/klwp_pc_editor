"""External runtime boundary for Tkinter, Pillow, and stdlib APIs."""

import base64
import copy
from datetime import datetime
import gzip
import io
import json
import math
import os
from os.path import basename
import re
import sys
import time
import uuid
import zipfile

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
    HAS_TK = True
except ImportError:
    HAS_TK = False

try:
    from PIL import (Image, ImageTk, ImageDraw, ImageFilter, ImageFont,
                     ImageChops, ImageEnhance, ImageOps)
    from PIL.Image import Resampling, Transform
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Resampling = None
    Transform = None

APP_TITLE = "KLWP Desktop Editor"
KFILE_PREFIX = "kfile://org.kustom.provider/bitmaps/"

