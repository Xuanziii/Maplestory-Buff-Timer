#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
楓之谷懷舊服 Buff 技能倒數提醒工具 (MapleStory Classic Buff Timer)
==================================================================
功能特點：
1. 現代極簡扁平化 UI (CustomTkinter)，微圓角卡片設計，支援「深色模式」與「淺色模式」即時切換，並支援視窗置頂。
2. 內建 6 組獨立計時器，每組皆可隨時切換「啟用 / 停用」。
3. 自訂技能名稱、觸發按鍵（支援點擊後直接按鍵綁定）、倒數秒數（支援秒數或 分:秒）、提醒音效（內建 4 種合成音效 + 支援自選 .wav/.mp3 檔案）。
4. 開啟程式即自動全局監控鍵盤：
   - 首次按下綁定按鍵：開始倒數計時。
   - 計時途中再次按下該按鍵：自動重置並重新開始倒數。
   - 支援多個啟用中的計時器綁定同一個按鍵（例如遊戲內組合技宏）。
5. 所有設定變更時自動儲存至同目錄下的 `buff_timer_config.json`，下次開啟自動還原。
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
from tkinter import filedialog

import customtkinter as ctk

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
# 現代極簡扁平化配色 (Light, Dark) Tuple
# ==============================================================================
PALETTE = {
    "bg": ("#F4F5F7", "#111827"),
    "surface": ("#FFFFFF", "#1F2937"),
    "surface_active": ("#F0F9FF", "#172554"),
    "surface_expired": ("#FEF2F2", "#450A0A"),
    "border": ("#E5E7EB", "#374151"),
    "border_active": ("#0284C7", "#38BDF8"),
    "border_warning": ("#D97706", "#F59E0B"),
    "border_expired": ("#DC2626", "#EF4444"),
    "text_primary": ("#111827", "#F9FAFB"),
    "text_secondary": ("#6B7280", "#9CA3AF"),
    "text_muted": ("#9CA3AF", "#6B7280"),
    "input_bg": ("#F9FAFB", "#111827"),
    "control_bg": ("#F3F4F6", "#374151"),
    "control_hover": ("#E5E7EB", "#4B5563"),
    "accent": ("#0284C7", "#38BDF8"),
    "accent_hover": ("#0369A1", "#0EA5E9"),
    "accent_text": ("#FFFFFF", "#0F172A"),
    "success": ("#16A34A", "#22C55E"),
    "warning": ("#D97706", "#F59E0B"),
    "danger": ("#DC2626", "#EF4444"),
    "progress_track": ("#E5E7EB", "#111827"),
}


# ==============================================================================
# 內建提醒音效合成器 (自動生成高音質 WAV 音效，免外部檔案依賴)
# ==============================================================================
BUILTIN_SOUNDS = {
    "bell": "🔔 清脆雙響鈴",
    "chime": "✨ 柔和上升和弦",
    "beep": "⚡ 高頻急促提示",
    "horn": "📯 渾厚低音號角",
    "custom": "🎵 自訂音效檔案...",
}
LABEL_TO_SOUND_KEY = {label: key for key, label in BUILTIN_SOUNDS.items()}


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
                            envelope = math.exp(-3.5 * (i / num_samples))
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
            alias = f"sound_{int(time.time() * 1000) % 100000}"
            try:
                mci = ctypes.windll.winmm.mciSendStringW
                mci(f'open "{filepath}" type mpegvideo alias {alias}', None, 0, 0)
                mci(f"play {alias} wait", None, 0, 0)
                mci(f"close {alias}", None, 0, 0)
            except Exception:
                winsound.MessageBeep(winsound.MB_OK)
        else:
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
# 單一計時器卡片元件 (TimerCard)
# ==============================================================================
class TimerCard:
    def __init__(self, parent, index: int, data: dict, app):
        self.parent = parent
        self.index = index
        self.app = app

        self.enabled_var = ctk.BooleanVar(value=bool(data.get("enabled", False)))
        self.name_var = ctk.StringVar(value=str(data.get("name", f"技能 {index + 1}")))
        self.vk_name = str(data.get("vk_name", "F1")).upper()
        self.duration_var = ctk.StringVar(value=str(data.get("duration", 120)))
        self.sound_key = str(data.get("sound", "bell"))
        if self.sound_key not in BUILTIN_SOUNDS:
            self.sound_key = "bell"
        self.custom_sound_path = str(data.get("custom_sound_path", ""))

        # 計時狀態: "standby" | "running" | "expired"
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
        font_ui = ctk.CTkFont(family="Microsoft JhengHei UI", size=12)
        font_ui_bold = ctk.CTkFont(family="Microsoft JhengHei UI", size=12, weight="bold")
        font_mono = ctk.CTkFont(family="Consolas", size=12, weight="bold")
        font_timer = ctk.CTkFont(family="Consolas", size=15, weight="bold")

        # 外層微圓角卡片
        self.card = ctk.CTkFrame(
            self.parent,
            corner_radius=10,
            border_width=1,
            fg_color=PALETTE["surface"],
            border_color=PALETTE["border"],
        )
        self.card.pack(fill="x", pady=4)

        # 上排主控制列
        top_row = ctk.CTkFrame(self.card, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 6))

        # 1. 啟用/停用開關
        self.enable_switch = ctk.CTkSwitch(
            top_row,
            text="",
            variable=self.enabled_var,
            width=38,
            switch_width=34,
            switch_height=18,
            progress_color=PALETTE["success"],
            button_color=("#FFFFFF", "#F9FAFB"),
            fg_color=PALETTE["control_bg"],
            command=self._on_toggle_enable,
        )
        self.enable_switch.pack(side="left", padx=(0, 8))

        # 2. 技能名稱輸入框
        self.name_entry = ctk.CTkEntry(
            top_row,
            textvariable=self.name_var,
            width=155,
            height=30,
            corner_radius=6,
            border_width=1,
            font=font_ui,
            fg_color=PALETTE["input_bg"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text_primary"],
        )
        self.name_entry.pack(side="left", padx=(0, 8))

        # 3. 觸發按鍵綁定按鈕
        self.key_btn = ctk.CTkButton(
            top_row,
            text=self.vk_name,
            width=92,
            height=30,
            corner_radius=6,
            border_width=1,
            font=font_mono,
            fg_color=PALETTE["control_bg"],
            hover_color=PALETTE["control_hover"],
            border_color=PALETTE["border"],
            text_color=PALETTE["accent"],
            command=self.start_key_capture,
        )
        self.key_btn.pack(side="left", padx=(0, 8))

        # 4. 倒數時間輸入 (秒 / 分:秒)
        self.duration_entry = ctk.CTkEntry(
            top_row,
            textvariable=self.duration_var,
            width=60,
            height=30,
            corner_radius=6,
            border_width=1,
            justify="center",
            font=font_mono,
            fg_color=PALETTE["input_bg"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text_primary"],
        )
        self.duration_entry.pack(side="left", padx=(0, 3))

        self.sec_label = ctk.CTkLabel(
            top_row,
            text="秒",
            font=font_ui,
            text_color=PALETTE["text_secondary"],
        )
        self.sec_label.pack(side="left", padx=(0, 10))

        # 5. 音效下拉選單
        self.sound_menu = ctk.CTkOptionMenu(
            top_row,
            values=list(BUILTIN_SOUNDS.values()),
            width=148,
            height=30,
            corner_radius=6,
            font=font_ui,
            dropdown_font=font_ui,
            fg_color=PALETTE["control_bg"],
            button_color=PALETTE["control_bg"],
            button_hover_color=PALETTE["control_hover"],
            text_color=PALETTE["text_primary"],
            command=self._on_sound_selected,
        )
        self.sound_menu.set(self._get_sound_display_name())
        self.sound_menu.pack(side="left", padx=(0, 4))

        # 6. 試聽音效按鈕
        self.test_sound_btn = ctk.CTkButton(
            top_row,
            text="🔊",
            width=32,
            height=30,
            corner_radius=6,
            font=font_ui,
            fg_color=PALETTE["control_bg"],
            hover_color=PALETTE["control_hover"],
            text_color=PALETTE["text_primary"],
            command=self.play_alert_sound,
        )
        self.test_sound_btn.pack(side="left", padx=(0, 8))

        # 7. 右側：重置按鈕 + 倒數狀態與時間顯示
        self.reset_btn = ctk.CTkButton(
            top_row,
            text="重置",
            width=50,
            height=30,
            corner_radius=6,
            font=font_ui_bold,
            fg_color=PALETTE["control_bg"],
            hover_color=PALETTE["control_hover"],
            text_color=PALETTE["text_secondary"],
            command=self.reset_to_standby,
        )
        self.reset_btn.pack(side="right", padx=(8, 0))

        self.timer_display = ctk.CTkLabel(
            top_row,
            text="待命中",
            width=106,
            anchor="e",
            font=font_timer,
            text_color=PALETTE["text_secondary"],
        )
        self.timer_display.pack(side="right")

        # 下排：極簡扁平進度條
        self.progress_bar = ctk.CTkProgressBar(
            self.card,
            height=5,
            corner_radius=3,
            fg_color=PALETTE["progress_track"],
            progress_color=PALETTE["accent"],
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=12, pady=(0, 10))

    def _bind_traces(self):
        self.name_var.trace_add("write", lambda *_: self.app.save_config())
        self.duration_var.trace_add("write", self._on_duration_changed)

    def _on_duration_changed(self, *_):
        self.total_duration = self._parse_duration()
        if self.state == "standby":
            self._update_timer_text_and_bar()
        self.app.save_config()

    def _get_sound_display_name(self) -> str:
        if self.sound_key == "custom" and self.custom_sound_path:
            base = os.path.basename(self.custom_sound_path)
            return f"🎵 {base[:10]}..." if len(base) > 10 else f"🎵 {base}"
        return BUILTIN_SOUNDS.get(self.sound_key, BUILTIN_SOUNDS["bell"])

    def _on_sound_selected(self, selected_label: str):
        key = LABEL_TO_SOUND_KEY.get(selected_label)
        if key is None:
            return
        if key == "custom":
            filepath = filedialog.askopenfilename(
                parent=self.app,
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

        self.sound_menu.set(self._get_sound_display_name())
        self.app.save_config()
        self.play_alert_sound()

    def play_alert_sound(self):
        self.app.sound_manager.play(self.sound_key, self.custom_sound_path)

    def _on_toggle_enable(self):
        if not self.enabled_var.get():
            self.state = "standby"
            self.remaining_seconds = 0.0
        self.app.save_config()
        self.update_visuals()

    def start_key_capture(self):
        """進入按鍵綁定模式"""
        self.app.start_listening_for_row(self)

    def set_bound_key(self, vk_name: str):
        self.vk_name = vk_name.upper()
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
        if not self.enabled_var.get():
            self.timer_display.configure(text="已停用", text_color=PALETTE["text_muted"])
            self.progress_bar.set(0)
            return

        if self.state == "standby":
            self.timer_display.configure(
                text=f"待命 {self._format_time(self.total_duration)}",
                text_color=PALETTE["text_secondary"],
            )
            self.progress_bar.set(0)
        elif self.state == "running":
            ratio = max(0.0, min(1.0, self.remaining_seconds / max(1, self.total_duration)))
            is_warning = self.remaining_seconds <= 10 or ratio <= 0.15
            color = PALETTE["warning"] if is_warning else PALETTE["accent"]
            border_color = PALETTE["border_warning"] if is_warning else PALETTE["border_active"]

            self.timer_display.configure(
                text=self._format_time(self.remaining_seconds),
                text_color=color,
            )
            self.progress_bar.configure(progress_color=color)
            self.progress_bar.set(ratio)
            self.card.configure(border_color=border_color)
        elif self.state == "expired":
            self.timer_display.configure(text="請補放技能!", text_color=PALETTE["danger"])
            self.progress_bar.configure(progress_color=PALETTE["danger"])
            self.progress_bar.set(1.0)

    def update_visuals(self):
        """套用目前狀態樣式"""
        is_enabled = self.enabled_var.get()

        if not is_enabled:
            fg = PALETTE["surface"]
            border = PALETTE["border"]
        elif self.state == "expired":
            fg = PALETTE["surface_expired"]
            border = PALETTE["border_expired"]
        elif self.state == "running":
            fg = PALETTE["surface_active"]
            border = PALETTE["border_active"]
        else:
            fg = PALETTE["surface"]
            border = PALETTE["border"]

        self.card.configure(fg_color=fg, border_color=border)

        text_col = PALETTE["text_primary"] if is_enabled else PALETTE["text_muted"]
        self.name_entry.configure(text_color=text_col)
        self.duration_entry.configure(text_color=text_col)

        if self.app.listening_row is self:
            self.key_btn.configure(
                text="請按任意鍵...",
                fg_color=PALETTE["warning"],
                hover_color=PALETTE["warning"],
                border_color=PALETTE["warning"],
                text_color="#FFFFFF",
            )
        else:
            self.key_btn.configure(
                text=self.vk_name,
                fg_color=PALETTE["control_bg"],
                hover_color=PALETTE["control_hover"],
                border_color=PALETTE["border"],
                text_color=PALETTE["accent"] if is_enabled else PALETTE["text_muted"],
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
class MapleBuffTimerApp(ctk.CTk):
    CONFIG_FILENAME = "buff_timer_config.json"

    def __init__(self):
        super().__init__()

        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(os.path.abspath(sys.executable))
            self.resource_dir = getattr(sys, "_MEIPASS", self.base_dir)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            self.resource_dir = self.base_dir

        self.config_path = os.path.join(self.base_dir, self.CONFIG_FILENAME)
        self.sound_manager = SoundManager()
        self.config_data = self._load_config()

        self.current_theme = self.config_data.get("theme", "dark")
        if self.current_theme not in ("dark", "light"):
            self.current_theme = "dark"

        ctk.set_appearance_mode(self.current_theme)
        ctk.set_default_color_theme("blue")

        self.title("楓之谷懷舊服 Buff 技能計時提醒器")
        self.geometry("860x570")
        self.minsize(800, 530)
        self.configure(fg_color=PALETTE["bg"])

        icon_path = os.path.join(self.resource_dir, "Icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.base_dir, "Icon.ico")
        if IS_WINDOWS and os.path.exists(icon_path):
            try:
                self.iconbitmap(default=icon_path)
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.always_on_top = bool(self.config_data.get("always_on_top", True))
        self.attributes("-topmost", self.always_on_top)

        self.listening_row = None
        self.rows = []
        self._pressed_keys_state = set()

        self._build_main_ui()
        self._update_header_controls()

        self.bind("<KeyPress>", self._on_tk_key_press)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._start_global_keyboard_monitor()
        self._schedule_tick()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and "timers" in loaded:
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
        font_title = ctk.CTkFont(family="Microsoft JhengHei UI", size=17, weight="bold")
        font_sub = ctk.CTkFont(family="Microsoft JhengHei UI", size=11)
        font_ctrl = ctk.CTkFont(family="Microsoft JhengHei UI", size=12, weight="bold")

        # 頂部標題與控制列
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="🍁 楓之谷 Buff 技能計時器",
            font=font_title,
            text_color=PALETTE["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="全局鍵盤監控中 · 按下綁定鍵自動倒數，重複按下自動重置",
            font=font_sub,
            text_color=PALETTE["text_secondary"],
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        # 右上角控制列
        ctrl_box = ctk.CTkFrame(header, fg_color="transparent")
        ctrl_box.pack(side="right", anchor="center")

        self.reset_all_btn = ctk.CTkButton(
            ctrl_box,
            text="全部重置",
            width=76,
            height=30,
            corner_radius=8,
            font=font_ctrl,
            fg_color=PALETTE["control_bg"],
            hover_color=PALETTE["control_hover"],
            text_color=PALETTE["text_primary"],
            command=self.reset_all_timers,
        )
        self.reset_all_btn.pack(side="left", padx=(0, 8))

        self.topmost_btn = ctk.CTkButton(
            ctrl_box,
            text="置頂: 開",
            width=76,
            height=30,
            corner_radius=8,
            border_width=1,
            font=font_ctrl,
            command=self.toggle_topmost,
        )
        self.topmost_btn.pack(side="left", padx=(0, 8))

        self.theme_switch = ctk.CTkSegmentedButton(
            ctrl_box,
            values=["淺色", "深色"],
            height=30,
            corner_radius=8,
            font=font_ctrl,
            fg_color=PALETTE["control_bg"],
            selected_color=PALETTE["accent"],
            selected_hover_color=PALETTE["accent_hover"],
            unselected_color=PALETTE["control_bg"],
            unselected_hover_color=PALETTE["control_hover"],
            text_color=PALETTE["text_primary"],
            command=self._on_theme_segment_changed,
        )
        self.theme_switch.set("深色" if self.current_theme == "dark" else "淺色")
        self.theme_switch.pack(side="left")

        # 6 組計時器卡片容器
        list_container = ctk.CTkFrame(self, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=20, pady=2)

        for idx, timer_cfg in enumerate(self.config_data["timers"]):
            card = TimerCard(list_container, idx, timer_cfg, self)
            card.update_visuals()
            self.rows.append(card)

        # 底部狀態列
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(6, 12))

        monitor_mode = (
            "Windows 原生全局監控 (GetAsyncKeyState)"
            if IS_WINDOWS
            else ("跨平台全局監控 (pynput)" if HAS_PYNPUT else "視窗焦點監控 (建議安裝 pynput)")
        )
        ctk.CTkLabel(
            footer,
            text=f"● {monitor_mode}  ·  設定自動儲存於 {self.CONFIG_FILENAME}",
            font=font_sub,
            text_color=PALETTE["text_secondary"],
            anchor="w",
        ).pack(side="left")

    def _on_theme_segment_changed(self, value: str):
        new_theme = "dark" if value == "深色" else "light"
        if new_theme != self.current_theme:
            self.current_theme = new_theme
            ctk.set_appearance_mode(self.current_theme)
            self.save_config()

    def toggle_topmost(self):
        self.always_on_top = not self.always_on_top
        self.attributes("-topmost", self.always_on_top)
        self._update_header_controls()
        self.save_config()

    def _update_header_controls(self):
        if self.always_on_top:
            self.topmost_btn.configure(
                text="📌 置頂: 開",
                fg_color=PALETTE["surface_active"],
                hover_color=PALETTE["control_hover"],
                border_color=PALETTE["accent"],
                text_color=PALETTE["accent"],
            )
        else:
            self.topmost_btn.configure(
                text="📌 置頂: 關",
                fg_color=PALETTE["control_bg"],
                hover_color=PALETTE["control_hover"],
                border_color=PALETTE["border"],
                text_color=PALETTE["text_secondary"],
            )

    def reset_all_timers(self):
        for row in self.rows:
            row.reset_to_standby()

    # ==========================================================================
    # 按鍵綁定與全局鍵盤監控邏輯
    # ==========================================================================
    def start_listening_for_row(self, row: TimerCard):
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

        if self.listening_row is not None:
            target_row = self.listening_row
            self.listening_row = None
            if key_name != "ESC":
                target_row.set_bound_key(key_name)
            else:
                target_row.update_visuals()
            return

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
        self.after(20, self._poll_windows_keys)

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
            self.after(0, self._handle_global_key_trigger, key_name)

    def _on_pynput_release(self, key):
        key_name = self._normalize_pynput_key(key)
        if key_name in self._pressed_keys_state:
            self._pressed_keys_state.discard(key_name)

    def _schedule_tick(self):
        now = time.monotonic()
        for row in self.rows:
            row.tick(now)
        self.after(50, self._schedule_tick)

    def _on_close(self):
        self.save_config()
        self.destroy()


def main():
    if IS_WINDOWS:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MapleStory.BuffTimer.App"
            )
        except Exception:
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

    app = MapleBuffTimerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
