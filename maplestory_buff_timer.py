#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
楓之谷懷舊服 Buff 技能倒數提醒工具 (MapleStory Classic Buff Timer)
==================================================================
功能特點：
1. 現代簡潔 UI，支援「深色主題 (Dark)」與「淺色主題 (Light)」一鍵切換，並支援視窗置頂。
2. 內建 6 組獨立計時器，每組皆可隨時切換「啟用 / 停用」。
3. 自訂技能名稱、觸發按鍵（支援點擊後直接按鍵綁定）、倒數秒數、提醒音效（內建 4 種合成音效 + 支援自選 .wav/.mp3 檔案）。
4. 開啟程式即自動全局監控鍵盤：
   - 首次按下綁定按鍵：開始倒數計時。
   - 計時途中再次按下該按鍵：自動重置並重新開始倒數。
   - 支援多個啟用中的計時器綁定同一個按鍵（例如遊戲內組合技宏）。
5. 所有設定變更時自動儲存至同目錄下的 `buff_timer_config.json`，下次開啟自動還原。

執行環境說明：
- Windows 系統：直接使用 Python 內建標準庫 (`tkinter`, `ctypes`, `winsound`) 即可完整運行（免安裝額外套件）。
  ※ 提示：若楓之谷以「系統管理員身分」執行，請同樣以「系統管理員身分」執行本程式，確保全局鍵盤監控在遊戲視窗內生效。
- macOS / Linux 系統：建議安裝 `pynput` (`pip install pynput`) 以支援跨平台全局鍵盤監控。
"""

import ctypes
import json
import math
import os
import platform
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave
import tkinter as tk
from tkinter import filedialog, messagebox

# 嘗試載入選用的跨平台鍵盤監聽套件 (非 Windows 環境備援)
try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import winsound


# ==============================================================================
# Windows 虛擬按鍵碼 (Virtual-Key Codes) 對照表
# ==============================================================================
VK_MAP = {
    "BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "SHIFT": 0x10,
    "CTRL": 0x11, "ALT": 0x12, "PAUSE": 0x13, "CAPSLOCK": 0x14,
    "ESC": 0x1B, "SPACE": 0x20, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "END": 0x23, "HOME": 0x24, "LEFT": 0x25, "UP": 0x26,
    "RIGHT": 0x27, "DOWN": 0x28, "INSERT": 0x2D, "DELETE": 0x2E,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
    "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
    "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
    "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59, "Z": 0x5A,
    "NUM0": 0x60, "NUM1": 0x61, "NUM2": 0x62, "NUM3": 0x63, "NUM4": 0x64,
    "NUM5": 0x65, "NUM6": 0x66, "NUM7": 0x67, "NUM8": 0x68, "NUM9": 0x69,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
    "F11": 0x7A, "F12": 0x7B,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}

TK_KEYSYM_NORMALIZE = {
    "Return": "ENTER", "Escape": "ESC", "BackSpace": "BACKSPACE",
    "Tab": "TAB", "space": "SPACE",
    "Shift_L": "SHIFT", "Shift_R": "SHIFT",
    "Control_L": "CTRL", "Control_R": "CTRL",
    "Alt_L": "ALT", "Alt_R": "ALT",
    "Prior": "PAGEUP", "Next": "PAGEDOWN",
    "Home": "HOME", "End": "END",
    "Insert": "INSERT", "Delete": "DELETE",
    "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
    "Caps_Lock": "CAPSLOCK", "Pause": "PAUSE",
    "KP_0": "NUM0", "KP_1": "NUM1", "KP_2": "NUM2", "KP_3": "NUM3",
    "KP_4": "NUM4", "KP_5": "NUM5", "KP_6": "NUM6", "KP_7": "NUM7",
    "KP_8": "NUM8", "KP_9": "NUM9",
    "semicolon": ";", "equal": "=", "comma": ",", "minus": "-",
    "period": ".", "slash": "/", "grave": "`", "bracketleft": "[",
    "backslash": "\\", "bracketright": "]", "apostrophe": "'",
}


# ==============================================================================
# 主題配色定義 (Dark & Light Themes)
# ==============================================================================
THEMES = {
    "dark": {
        "bg": "#0F172A",           # 主視窗背景 (深藍灰)
        "card_bg": "#1E293B",      # 計時器卡片背景
        "card_active": "#1E3A5F",  # 計時中卡片微亮背景
        "card_expired": "#3B1D2E", # 時間到提醒背景
        "card_border": "#334155",  # 邊框顏色
        "text_primary": "#F8FAFC", # 主要文字
        "text_secondary": "#94A3B8", # 次要文字
        "entry_bg": "#0F172A",     # 輸入框背景
        "entry_fg": "#F8FAFC",     # 輸入框文字
        "btn_bg": "#334155",       # 一般按鈕背景
        "btn_fg": "#F1F5F9",       # 一般按鈕文字
        "btn_hover": "#475569",    # 按鈕滑過
        "accent": "#38BDF8",       # 主強調色 (天空藍)
        "accent_fg": "#0F172A",
        "success": "#22C55E",      # 啟用 / 進行中綠
        "warning": "#F59E0B",      # 即將到期橘黃
        "danger": "#EF4444",       # 到期紅
        "progress_bg": "#0F172A",  # 進度條底色
    },
    "light": {
        "bg": "#F1F5F9",           # 主視窗背景 (淺雲灰)
        "card_bg": "#FFFFFF",      # 計時器卡片背景
        "card_active": "#EFF6FF",  # 計時中卡片微亮背景
        "card_expired": "#FEF2F2", # 時間到提醒背景
        "card_border": "#CBD5E1",  # 邊框顏色
        "text_primary": "#0F172A", # 主要文字
        "text_secondary": "#64748B", # 次要文字
        "entry_bg": "#F8FAFC",     # 輸入框背景
        "entry_fg": "#0F172A",     # 輸入框文字
        "btn_bg": "#E2E8F0",       # 一般按鈕背景
        "btn_fg": "#1E293B",       # 一般按鈕文字
        "btn_hover": "#CBD5E1",    # 按鈕滑過
        "accent": "#0284C7",       # 主強調色 (寶藍)
        "accent_fg": "#FFFFFF",
        "success": "#16A34A",      # 啟用 / 進行中綠
        "warning": "#D97706",      # 即將到期橘黃
        "danger": "#DC2626",       # 到期紅
        "progress_bg": "#E2E8F0",  # 進度條底色
    },
}


# ==============================================================================
# 內建提醒音效合成器 (自動生成高音質 WAV 音效，免外部檔案依賴)
# ==============================================================================
BUILTIN_SOUNDS = {
    "bell": "🔔 清脆雙響鈴 (預設)",
    "chime": "✨ 柔和上升和弦",
    "beep": "⚡ 高頻急促提示",
    "horn": "📯 渾厚低音號角",
    "custom": "🎵 自訂音效檔案...",
}


class SoundManager:
    """負責生成內建提示音與非同步播放音效（支援內建音效及自選 .wav / .mp3）"""

    def __init__(self):
        self.temp_dir = os.path.join(tempfile.gettempdir(), "maplestory_buff_sounds")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.sound_files = {}
        self._generate_builtin_wavs()

    def _generate_builtin_wavs(self):
        """預先合成 4 種不同風格的 WAV 提示音"""
        presets = {
            # (頻率序列, 每段秒數, 音量衰減)
            "bell": [(880, 0.12), (0, 0.04), (1174.66, 0.22)],
            "chime": [(523.25, 0.10), (659.25, 0.10), (783.99, 0.12), (1046.50, 0.25)],
            "beep": [(1400, 0.08), (0, 0.04), (1400, 0.08), (0, 0.04), (1400, 0.12)],
            "horn": [(392.00, 0.15), (0, 0.03), (587.33, 0.30)],
        }
        sample_rate = 44100
        for name, notes in presets.items():
            path = os.path.join(self.temp_dir, f"builtin_{name}.wav")
            self.sound_files[name] = path
            if os.path.exists(path):
                continue
            try:
                frames = bytearray()
                for freq, duration in notes:
                    num_samples = int(sample_rate * duration)
                    for i in range(num_samples):
                        if freq <= 0:
                            val = 0
                        else:
                            t = i / sample_rate
                            # 加入泛音與指數衰減包絡線，讓聲音清脆不刺耳
                            envelope = math.exp(-3.5 * (i / num_samples))
                            # 前 5ms 淡入避免爆音
                            fade_in = min(1.0, i / (sample_rate * 0.005))
                            wave_val = (
                                0.75 * math.sin(2 * math.pi * freq * t)
                                + 0.25 * math.sin(2 * math.pi * (freq * 2) * t)
                            )
                            val = int(32767 * 0.45 * envelope * fade_in * wave_val)
                        frames.extend(struct.pack("<h", max(-32768, min(32767, val))))
                with wave.open(path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(bytes(frames))
            except Exception:
                pass

    def play(self, sound_key: str, custom_path: str = ""):
        """在背景執行緒播放指定音效，避免阻塞 UI 與計時器"""
        target_path = (
            custom_path
            if (sound_key == "custom" and custom_path and os.path.isfile(custom_path))
            else self.sound_files.get(sound_key, self.sound_files.get("bell"))
        )
        threading.Thread(
            target=self._play_worker, args=(target_path,), daemon=True
        ).start()

    def _play_worker(self, filepath: str):
        if not filepath or not os.path.exists(filepath):
            if IS_WINDOWS:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return

        ext = os.path.splitext(filepath)[1].lower()
        if IS_WINDOWS:
            if ext == ".wav":
                try:
                    winsound.PlaySound(
                        filepath, winsound.SND_FILENAME | winsound.SND_NODEFAULT
                    )
                    return
                except Exception:
                    pass
            # 使用 Windows 內建 MCI 介面播放 MP3 或其他音訊格式
            alias = f"sound_{int(time.time() * 1000) % 100000}"
            try:
                mci = ctypes.windll.winmm.mciSendStringW
                mci(f'open "{filepath}" type mpegvideo alias {alias}', None, 0, 0)
                mci(f"play {alias} wait", None, 0, 0)
                mci(f"close {alias}", None, 0, 0)
            except Exception:
                winsound.MessageBeep(winsound.MB_OK)
        else:
            # macOS / Linux 系統音效播放支援
            for cmd in (["afplay", filepath], ["aplay", "-q", filepath], ["paplay", filepath]):
                try:
                    subprocess.run(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
                    break
                except Exception:
                    continue


# ==============================================================================
# 預設 6 組計時器設定 (經典懷舊楓之谷常見技能範例)
# ==============================================================================
DEFAULT_CONFIG = {
    "theme": "dark",
    "always_on_top": True,
    "timers": [
        {
            "enabled": True,
            "name": "神聖祈禱 (HS)",
            "key": "PGUP",
            "vk_name": "PAGEUP",
            "duration": 120,
            "sound": "bell",
            "custom_sound_path": "",
        },
        {
            "enabled": True,
            "name": "速度激發 / 武器加速",
            "key": "SHIFT",
            "vk_name": "SHIFT",
            "duration": 200,
            "sound": "chime",
            "custom_sound_path": "",
        },
        {
            "enabled": True,
            "name": "楓葉祝福 (MW)",
            "key": "HOME",
            "vk_name": "HOME",
            "duration": 600,
            "sound": "bell",
            "custom_sound_path": "",
        },
        {
            "enabled": False,
            "name": "火眼晶晶 / 精神強化",
            "key": "END",
            "vk_name": "END",
            "duration": 300,
            "sound": "beep",
            "custom_sound_path": "",
        },
        {
            "enabled": False,
            "name": "魔心防禦 (Magic Guard)",
            "key": "DEL",
            "vk_name": "DELETE",
            "duration": 600,
            "sound": "horn",
            "custom_sound_path": "",
        },
        {
            "enabled": False,
            "name": "自訂技能 6",
            "key": "INS",
            "vk_name": "INSERT",
            "duration": 180,
            "sound": "bell",
            "custom_sound_path": "",
        },
    ],
}


# ==============================================================================
# 單一計時器列 UI 與狀態元件 (TimerRow)
# ==============================================================================
class TimerRow:
    def __init__(self, parent, index: int, data: dict, app):
        self.parent = parent
        self.index = index
        self.app = app

        # 設定資料
        self.enabled_var = tk.BooleanVar(value=bool(data.get("enabled", False)))
        self.name_var = tk.StringVar(value=str(data.get("name", f"技能 {index + 1}")))
        self.vk_name = str(data.get("vk_name", "F1")).upper()
        self.duration_var = tk.StringVar(value=str(data.get("duration", 120)))
        self.sound_key = str(data.get("sound", "bell"))
        if self.sound_key not in BUILTIN_SOUNDS:
            self.sound_key = "bell"
        self.custom_sound_path = str(data.get("custom_sound_path", ""))

        # 計時狀態: "standby" (待命), "running" (倒數中), "expired" (請補放!)
        self.state = "standby"
        self.end_timestamp = 0.0
        self.total_duration = self._parse_duration()
        self.remaining_seconds = 0.0

        self._build_ui()
        self._bind_traces()

    def _parse_duration(self) -> int:
        """支援純秒數 (如 '120') 或 分:秒 (如 '2:00') 輸入"""
        raw = self.duration_var.get().strip()
        try:
            if ":" in raw:
                parts = raw.split(":")
                mins = int(parts[0].strip() or 0)
                secs = int(parts[1].strip() or 0)
                return max(1, mins * 60 + secs)
            return max(1, int(float(raw)))
        except ValueError:
            return 120

    def _build_ui(self):
        # 外框卡片
        self.card = tk.Frame(
            self.parent,
            bd=0,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        self.card.pack(fill="x", pady=5)

        # 上排：啟用開關 | 技能名稱 | 按鍵綁定 | 倒數秒數 | 音效選單 | 試聽 | 剩餘時間與狀態
        top_row = tk.Frame(self.card, bd=0)
        top_row.pack(fill="x")
        self.top_row = top_row

        # 1. 啟用/停用切換按鈕
        self.toggle_btn = tk.Button(
            top_row,
            text="啟用" if self.enabled_var.get() else "停用",
            width=6,
            relief="flat",
            font=("Microsoft JhengHei UI", 9, "bold"),
            cursor="hand2",
            command=self.toggle_enable,
        )
        self.toggle_btn.pack(side="left", padx=(0, 8))

        # 2. 技能名稱輸入框
        self.name_entry = tk.Entry(
            top_row,
            textvariable=self.name_var,
            width=16,
            relief="flat",
            highlightthickness=1,
            font=("Microsoft JhengHei UI", 10),
        )
        self.name_entry.pack(side="left", padx=(0, 8), ipady=3)

        # 3. 觸發按鍵綁定按鈕
        self.key_btn = tk.Button(
            top_row,
            text=f"按鍵: {self.vk_name}",
            width=12,
            relief="flat",
            font=("Consolas", 10, "bold"),
            cursor="hand2",
            command=self.start_key_capture,
        )
        self.key_btn.pack(side="left", padx=(0, 8), ipady=1)

        # 4. 倒數時間輸入框 (秒)
        self.sec_label_prefix = tk.Label(
            top_row, text="秒數:", font=("Microsoft JhengHei UI", 9)
        )
        self.sec_label_prefix.pack(side="left", padx=(2, 3))

        self.duration_entry = tk.Entry(
            top_row,
            textvariable=self.duration_var,
            width=6,
            justify="center",
            relief="flat",
            highlightthickness=1,
            font=("Consolas", 10, "bold"),
        )
        self.duration_entry.pack(side="left", padx=(0, 8), ipady=3)

        # 5. 音效選擇按鈕 (點擊展開選單或瀏覽檔案)
        self.sound_btn = tk.Button(
            top_row,
            text=self._get_sound_display_name(),
            width=16,
            relief="flat",
            font=("Microsoft JhengHei UI", 9),
            cursor="hand2",
            command=self.show_sound_menu,
        )
        self.sound_btn.pack(side="left", padx=(0, 4), ipady=1)

        # 6. 試聽音效按鈕
        self.test_sound_btn = tk.Button(
            top_row,
            text="🔊",
            width=3,
            relief="flat",
            font=("Segoe UI Emoji", 9),
            cursor="hand2",
            command=self.play_alert_sound,
        )
        self.test_sound_btn.pack(side="left", padx=(0, 10), ipady=1)

        # 7. 右側：重置按鈕 + 倒數狀態與時間顯示
        self.reset_btn = tk.Button(
            top_row,
            text="重置",
            width=5,
            relief="flat",
            font=("Microsoft JhengHei UI", 9),
            cursor="hand2",
            command=self.reset_to_standby,
        )
        self.reset_btn.pack(side="right", padx=(6, 0))

        self.timer_display = tk.Label(
            top_row,
            text="待命中",
            width=11,
            anchor="e",
            font=("Consolas", 13, "bold"),
        )
        self.timer_display.pack(side="right")

        # 下排：視覺化進度條 Canvas
        self.progress_canvas = tk.Canvas(
            self.card, height=6, bd=0, highlightthickness=0
        )
        self.progress_canvas.pack(fill="x", pady=(8, 0))
        self.progress_rect = self.progress_canvas.create_rectangle(
            0, 0, 0, 6, width=0
        )

    def _bind_traces(self):
        self.name_var.trace_add("write", lambda *_: self.app.save_config())
        self.duration_var.trace_add("write", self._on_duration_changed)

    def _on_duration_changed(self, *_):
        self.total_duration = self._parse_duration()
        self.app.save_config()

    def _get_sound_display_name(self) -> str:
        if self.sound_key == "custom" and self.custom_sound_path:
            base = os.path.basename(self.custom_sound_path)
            return f"🎵 {base[:10]}..." if len(base) > 10 else f"🎵 {base}"
        return BUILTIN_SOUNDS.get(self.sound_key, BUILTIN_SOUNDS["bell"])

    def show_sound_menu(self):
        """彈出音效選擇選單"""
        menu = tk.Menu(self.app.root, tearoff=0, font=("Microsoft JhengHei UI", 9))
        for key, label in BUILTIN_SOUNDS.items():
            menu.add_command(
                label=label,
                command=lambda k=key: self._select_sound(k),
            )
        x = self.sound_btn.winfo_rootx()
        y = self.sound_btn.winfo_rooty() + self.sound_btn.winfo_height()
        menu.tk_popup(x, y)

    def _select_sound(self, key: str):
        if key == "custom":
            filepath = filedialog.askopenfilename(
                parent=self.app.root,
                title=f"選擇【{self.name_var.get()}】的提醒音效檔案",
                filetypes=[
                    ("音訊檔案 (*.wav; *.mp3)", "*.wav *.mp3"),
                    ("WAV 音訊 (*.wav)", "*.wav"),
                    ("MP3 音訊 (*.mp3)", "*.mp3"),
                    ("所有檔案 (*.*)", "*.*"),
                ],
            )
            if filepath:
                self.sound_key = "custom"
                self.custom_sound_path = filepath
        else:
            self.sound_key = key

        self.sound_btn.config(text=self._get_sound_display_name())
        self.app.save_config()
        self.play_alert_sound()

    def play_alert_sound(self):
        self.app.sound_manager.play(self.sound_key, self.custom_sound_path)

    def toggle_enable(self):
        new_state = not self.enabled_var.get()
        self.enabled_var.set(new_state)
        if not new_state:
            self.state = "standby"
            self.remaining_seconds = 0.0
        self.app.save_config()
        self.update_visuals()

    def start_key_capture(self):
        """進入按鍵綁定模式"""
        self.app.start_listening_for_row(self)

    def set_bound_key(self, vk_name: str):
        self.vk_name = vk_name.upper()
        self.key_btn.config(text=f"按鍵: {self.vk_name}")
        self.app.save_config()
        self.update_visuals()

    def trigger_or_restart(self):
        """當監控到玩家按下此計時器的綁定按鍵時呼叫：開始或重新計時"""
        if not self.enabled_var.get():
            return
        self.total_duration = self._parse_duration()
        self.end_timestamp = time.monotonic() + self.total_duration
        self.remaining_seconds = float(self.total_duration)
        self.state = "running"
        self.update_visuals()

    def reset_to_standby(self):
        """手動重置回待命狀態"""
        self.state = "standby"
        self.remaining_seconds = 0.0
        self.update_visuals()

    def tick(self, now: float):
        """由主迴圈每 50ms 呼叫一次，更新倒數進度與到期檢查"""
        if not self.enabled_var.get():
            return

        if self.state == "running":
            rem = self.end_timestamp - now
            if rem <= 0:
                self.remaining_seconds = 0.0
                self.state = "expired"
                self.play_alert_sound()
                self.update_visuals()
            else:
                self.remaining_seconds = rem
                self._update_timer_text_and_bar()

    def _format_time(self, seconds: float) -> str:
        secs = int(math.ceil(seconds))
        m, s = divmod(secs, 60)
        return f"{m:02d}:{s:02d}"

    def _update_timer_text_and_bar(self):
        t = THEMES[self.app.current_theme]
        canvas_w = max(1, self.progress_canvas.winfo_width())

        if not self.enabled_var.get():
            self.timer_display.config(text="已停用", fg=t["text_secondary"])
            self.progress_canvas.coords(self.progress_rect, 0, 0, 0, 6)
            return

        if self.state == "standby":
            self.timer_display.config(
                text=f"待命 ({self._format_time(self.total_duration)})",
                fg=t["text_secondary"],
            )
            self.progress_canvas.coords(self.progress_rect, 0, 0, 0, 6)
        elif self.state == "running":
            ratio = max(0.0, min(1.0, self.remaining_seconds / max(1, self.total_duration)))
            bar_w = int(canvas_w * ratio)
            # 剩餘低於 10 秒或 15% 時轉為橘黃色提醒
            if self.remaining_seconds <= 10 or ratio <= 0.15:
                color = t["warning"]
            else:
                color = t["accent"]
            self.timer_display.config(
                text=self._format_time(self.remaining_seconds), fg=color
            )
            self.progress_canvas.coords(self.progress_rect, 0, 0, bar_w, 6)
            self.progress_canvas.itemconfig(self.progress_rect, fill=color)
        elif self.state == "expired":
            self.timer_display.config(text="請補放技能!", fg=t["danger"])
            self.progress_canvas.coords(self.progress_rect, 0, 0, canvas_w, 6)
            self.progress_canvas.itemconfig(self.progress_rect, fill=t["danger"])

    def update_visuals(self):
        """套用主題色彩與當前狀態樣式"""
        t = THEMES[self.app.current_theme]
        is_enabled = self.enabled_var.get()

        if not is_enabled:
            card_bg = t["card_bg"]
        elif self.state == "expired":
            card_bg = t["card_expired"]
        elif self.state == "running":
            card_bg = t["card_active"]
        else:
            card_bg = t["card_bg"]

        self.card.config(
            bg=card_bg,
            highlightbackground=(
                t["danger"]
                if (is_enabled and self.state == "expired")
                else (t["accent"] if (is_enabled and self.state == "running") else t["card_border"])
            ),
        )
        self.top_row.config(bg=card_bg)
        self.sec_label_prefix.config(bg=card_bg, fg=t["text_secondary"])
        self.timer_display.config(bg=card_bg)
        self.progress_canvas.config(bg=t["progress_bg"])

        # 啟用/停用按鈕樣式
        if is_enabled:
            self.toggle_btn.config(
                text="✔ 啟用", bg=t["success"], fg="#FFFFFF", activebackground=t["success"]
            )
        else:
            self.toggle_btn.config(
                text="停用", bg=t["btn_bg"], fg=t["text_secondary"], activebackground=t["btn_hover"]
            )

        # 輸入框與按鈕樣式
        for entry in (self.name_entry, self.duration_entry):
            entry.config(
                bg=t["entry_bg"],
                fg=t["entry_fg"] if is_enabled else t["text_secondary"],
                insertbackground=t["text_primary"],
                highlightbackground=t["card_border"],
                highlightcolor=t["accent"],
            )

        if self.app.listening_row is self:
            self.key_btn.config(
                text="請按任意鍵...", bg=t["warning"], fg="#FFFFFF"
            )
        else:
            self.key_btn.config(
                text=f"按鍵: {self.vk_name}",
                bg=t["btn_bg"],
                fg=t["accent"] if is_enabled else t["text_secondary"],
                activebackground=t["btn_hover"],
            )

        for btn in (self.sound_btn, self.test_sound_btn, self.reset_btn):
            btn.config(
                bg=t["btn_bg"],
                fg=t["btn_fg"],
                activebackground=t["btn_hover"],
                activeforeground=t["text_primary"],
            )

        self._update_timer_text_and_bar()

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled_var.get(),
            "name": self.name_var.get().strip() or f"技能 {self.index + 1}",
            "key": self.vk_name,
            "vk_name": self.vk_name,
            "duration": self._parse_duration(),
            "sound": self.sound_key,
            "custom_sound_path": self.custom_sound_path,
        }


# ==============================================================================
# 主應用程式 (MapleBuffTimerApp)
# ==============================================================================
class MapleBuffTimerApp:
    CONFIG_FILENAME = "buff_timer_config.json"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🍁 楓之谷懷舊服 Buff 技能計時提醒器")
        self.root.geometry("780x540")
        self.root.minsize(740, 500)

        self.config_path = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0])), self.CONFIG_FILENAME
        )
        self.sound_manager = SoundManager()
        self.config_data = self._load_config()

        self.current_theme = self.config_data.get("theme", "dark")
        if self.current_theme not in THEMES:
            self.current_theme = "dark"

        self.always_on_top = bool(self.config_data.get("always_on_top", True))
        self.root.attributes("-topmost", self.always_on_top)

        self.listening_row = None
        self.rows = []
        self._pressed_keys_state = set()  # 記錄目前按住的按鍵，避免長按重複觸發

        self._build_main_ui()
        self.apply_theme()

        # 綁定視窗內的按鍵事件（用於設定綁定按鍵，以及非 Windows 無 pynput 時的備援）
        self.root.bind("<KeyPress>", self._on_tk_key_press)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 啟動全局鍵盤監控與計時更新迴圈
        self._start_global_keyboard_monitor()
        self._schedule_tick()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and "timers" in loaded:
                    # 確保固定有 6 組計時器
                    timers = loaded["timers"][:6]
                    while len(timers) < 6:
                        timers.append(DEFAULT_CONFIG["timers"][len(timers)].copy())
                    loaded["timers"] = timers
                    return loaded
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULT_CONFIG))

    def save_config(self):
        if not hasattr(self, "rows") or len(self.rows) < 6:
            return
        data = {
            "theme": self.current_theme,
            "always_on_top": self.always_on_top,
            "timers": [row.to_dict() for row in self.rows],
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_main_ui(self):
        # 頂部標題與控制列
        self.header = tk.Frame(self.root, padx=18, pady=14)
        self.header.pack(fill="x")

        title_box = tk.Frame(self.header)
        title_box.pack(side="left")
        self.title_box = title_box

        self.title_label = tk.Label(
            title_box,
            text="🍁 楓之谷 Buff 技能倒數提醒器",
            font=("Microsoft JhengHei UI", 15, "bold"),
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(
            title_box,
            text="全局鍵盤監控已啟動：遊戲中按下對應技能鍵自動開始計時，重複按鍵自動重新倒數",
            font=("Microsoft JhengHei UI", 9),
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        # 右上角控制按鈕區
        ctrl_box = tk.Frame(self.header)
        ctrl_box.pack(side="right")
        self.ctrl_box = ctrl_box

        self.theme_btn = tk.Button(
            ctrl_box,
            text="☀️ 淺色主題" if self.current_theme == "dark" else "🌙 深色主題",
            relief="flat",
            padx=10,
            pady=4,
            font=("Microsoft JhengHei UI", 9, "bold"),
            cursor="hand2",
            command=self.toggle_theme,
        )
        self.theme_btn.pack(side="right", padx=(6, 0))

        self.topmost_btn = tk.Button(
            ctrl_box,
            text="📌 視窗置頂: 開" if self.always_on_top else "📌 視窗置頂: 關",
            relief="flat",
            padx=10,
            pady=4,
            font=("Microsoft JhengHei UI", 9),
            cursor="hand2",
            command=self.toggle_topmost,
        )
        self.topmost_btn.pack(side="right", padx=(6, 0))

        self.reset_all_btn = tk.Button(
            ctrl_box,
            text="🔄 全部重置",
            relief="flat",
            padx=10,
            pady=4,
            font=("Microsoft JhengHei UI", 9),
            cursor="hand2",
            command=self.reset_all_timers,
        )
        self.reset_all_btn.pack(side="right", padx=(6, 0))

        # 6 組計時器列表容器
        self.list_container = tk.Frame(self.root, padx=18, pady=4)
        self.list_container.pack(fill="both", expand=True)

        for idx, timer_cfg in enumerate(self.config_data["timers"]):
            row = TimerRow(self.list_container, idx, timer_cfg, self)
            self.rows.append(row)

        # 底部狀態列
        self.footer = tk.Frame(self.root, padx=18, pady=8)
        self.footer.pack(fill="x")

        monitor_mode = (
            "Windows 原生全局監控 (User32 GetAsyncKeyState)"
            if IS_WINDOWS
            else ("跨平台全局監控 (pynput)" if HAS_PYNPUT else "視窗焦點監控 (建議安裝 pynput 啟用背景監控)")
        )
        self.status_label = tk.Label(
            self.footer,
            text=f"🟢 監控狀態：{monitor_mode}  |  設定檔自動儲存於：{self.CONFIG_FILENAME}",
            font=("Microsoft JhengHei UI", 8),
        )
        self.status_label.pack(side="left")

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme()
        self.save_config()

    def toggle_topmost(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        self.apply_theme()
        self.save_config()

    def reset_all_timers(self):
        for row in self.rows:
            row.reset_to_standby()

    def apply_theme(self):
        t = THEMES[self.current_theme]
        self.root.config(bg=t["bg"])
        self.header.config(bg=t["bg"])
        self.title_box.config(bg=t["bg"])
        self.ctrl_box.config(bg=t["bg"])
        self.list_container.config(bg=t["bg"])
        self.footer.config(bg=t["bg"])

        self.title_label.config(bg=t["bg"], fg=t["text_primary"])
        self.subtitle_label.config(bg=t["bg"], fg=t["text_secondary"])
        self.status_label.config(bg=t["bg"], fg=t["text_secondary"])

        self.theme_btn.config(
            text="☀️ 切換淺色" if self.current_theme == "dark" else "🌙 切換深色",
            bg=t["accent"],
            fg=t["accent_fg"],
            activebackground=t["btn_hover"],
        )
        self.topmost_btn.config(
            text="📌 置頂: 開啟" if self.always_on_top else "📌 置頂: 關閉",
            bg=t["btn_bg"],
            fg=t["accent"] if self.always_on_top else t["text_secondary"],
            activebackground=t["btn_hover"],
        )
        self.reset_all_btn.config(
            bg=t["btn_bg"],
            fg=t["btn_fg"],
            activebackground=t["btn_hover"],
        )

        for row in self.rows:
            row.update_visuals()

    # ==========================================================================
    # 按鍵綁定與全局鍵盤監控邏輯
    # ==========================================================================
    def start_listening_for_row(self, row: TimerRow):
        prev = self.listening_row
        self.listening_row = row
        if prev and prev is not row:
            prev.update_visuals()
        row.update_visuals()

    def _normalize_tk_event_key(self, event) -> str:
        ks = event.keysym
        if ks in TK_KEYSYM_NORMALIZE:
            return TK_KEYSYM_NORMALIZE[ks]
        upper = ks.upper()
        if upper in VK_MAP:
            return upper
        return ""

    def _on_tk_key_press(self, event):
        key_name = self._normalize_tk_event_key(event)
        if not key_name:
            return

        # 若正在綁定按鍵模式
        if self.listening_row is not None:
            target_row = self.listening_row
            self.listening_row = None
            if key_name != "ESC":
                target_row.set_bound_key(key_name)
            else:
                target_row.update_visuals()
            return

        # 若在非 Windows 且未安裝 pynput 環境下，提供視窗內按鍵觸發
        if not IS_WINDOWS and not HAS_PYNPUT:
            self._handle_global_key_trigger(key_name)

    def _handle_global_key_trigger(self, key_name: str):
        """當偵測到按鍵按下時，觸發所有綁定該按鍵且啟用中的計時器"""
        if self.listening_row is not None:
            target_row = self.listening_row
            self.listening_row = None
            if key_name != "ESC":
                target_row.set_bound_key(key_name)
            else:
                target_row.update_visuals()
            return

        for row in self.rows:
            if row.enabled_var.get() and row.vk_name == key_name:
                row.trigger_or_restart()

    def _start_global_keyboard_monitor(self):
        """
        啟動全局鍵盤監聽：
        - Windows: 使用內建 ctypes.windll.user32.GetAsyncKeyState 進行高頻率邊緣偵測 (60Hz)，
          不攔截遊戲封包、不吃鍵，且免安裝第三方套件。
        - macOS / Linux: 若有安裝 pynput 則啟動 pynput.keyboard.Listener。
        """
        if IS_WINDOWS:
            self._poll_windows_keys()
        elif HAS_PYNPUT:
            listener = pynput_keyboard.Listener(
                on_press=self._on_pynput_press,
                on_release=self._on_pynput_release,
            )
            listener.daemon = True
            listener.start()

    def _poll_windows_keys(self):
        """Windows 專用全局按鍵輪詢 (每 20ms 檢查一次按鍵按下瞬間)"""
        user32 = ctypes.windll.user32
        # 若正在綁定新按鍵，掃描全部支援的按鍵；否則只掃描目前已啟用計時器綁定的按鍵以節省 CPU
        if self.listening_row is not None:
            keys_to_check = VK_MAP.items()
        else:
            active_names = {
                row.vk_name for row in self.rows if row.enabled_var.get()
            }
            keys_to_check = [
                (k, VK_MAP[k]) for k in active_names if k in VK_MAP
            ]

        currently_down = set()
        for key_name, vk_code in keys_to_check:
            state = user32.GetAsyncKeyState(vk_code)
            if state & 0x8000:
                currently_down.add(key_name)
                if key_name not in self._pressed_keys_state:
                    self._handle_global_key_trigger(key_name)

        self._pressed_keys_state = currently_down
        self.root.after(20, self._poll_windows_keys)

    def _normalize_pynput_key(self, key) -> str:
        try:
            if hasattr(key, "char") and key.char:
                ch = key.char.upper()
                if ch in VK_MAP:
                    return ch
            if hasattr(key, "name") and key.name:
                name = key.name.upper()
                mapping = {
                    "PAGE_UP": "PAGEUP",
                    "PAGE_DOWN": "PAGEDOWN",
                    "SHIFT_L": "SHIFT",
                    "SHIFT_R": "SHIFT",
                    "CTRL_L": "CTRL",
                    "CTRL_R": "CTRL",
                    "ALT_L": "ALT",
                    "ALT_R": "ALT",
                    "ALT_GR": "ALT",
                    "CAPS_LOCK": "CAPSLOCK",
                }
                name = mapping.get(name, name)
                if name in VK_MAP:
                    return name
        except Exception:
            pass
        return ""

    def _on_pynput_press(self, key):
        key_name = self._normalize_pynput_key(key)
        if key_name and key_name not in self._pressed_keys_state:
            self._pressed_keys_state.add(key_name)
            self.root.after(0, self._handle_global_key_trigger, key_name)

    def _on_pynput_release(self, key):
        key_name = self._normalize_pynput_key(key)
        if key_name in self._pressed_keys_state:
            self._pressed_keys_state.discard(key_name)

    def _schedule_tick(self):
        now = time.monotonic()
        for row in self.rows:
            row.tick(now)
        self.root.after(50, self._schedule_tick)

    def _on_close(self):
        self.save_config()
        self.root.destroy()


def main():
    # Windows 高 DPI 清晰字體支援
    if IS_WINDOWS:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    root = tk.Tk()
    MapleBuffTimerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()