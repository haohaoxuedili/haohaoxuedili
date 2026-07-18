# -*- coding: utf-8 -*-
"""
NCM 转 MP3 / FLAC - Android 版主程序 (Kivy)

目 标:
- 在 Android 手机上将 .ncm 文件一键解密为 FL AC / MP3
- 复用项目根目录的 ncm2mp3.py 核心解密模块
- 主界面: 文件选择器 -> 输出格式选项 -> 开始转换 -> 列表显示进度
- 后台线程转换, UI 不阻塞

打包:
- 与 ncm2mp3.py 一起由 Buildozer 打包成 apk
- main.py 同目录放 ncm2mp3.py 即可被 import
"""

import os
import sys
from pathlib import Path
from threading import Thread

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton

# 让 Buildozer 打包的私有目录在 sys.path 中, 以便 import ncm2mp3
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import ncm2mp3  # noqa: E402  (复用根目录核心模块)


KV = """
#:kivy 2.2.0
#:set PRIMARY (1, 0.227, 0.333, 1)    # #FF3A55
#:set BG (0.96, 0.97, 0.98, 1)        # #f5f7fa
#:set CARD (1, 1, 1, 1)
#:set INK (0.12, 0.13, 0.16, 1)
#:set MUTE (0.4, 0.42, 0.46, 1)

<RootWidget>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(12)
    canvas.before:
        Color: rgba: BG
        Rectangle: pos: self.pos; size: self.size

    # ---- 顶部品牌区 ----
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        spacing: dp(10)
        Widget:
            size_hint_x: 0.05
        Label:
            text: '♫'
            font_size: dp(32)
            color: PRIMARY
            size_hint_x: None
            width: dp(40)
        Label:
            text: 'NCM 转 MP3 / FLAC'
            font_size: dp(22)
            bold: True
            color: INK
            size_hint_x: 1
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Widget:
            size_hint_x: 0.05

    # ---- 输出格式选择 ----
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(96)
        padding: dp(14)
        spacing: dp(8)
        canvas.before:
            Color: rgba: CARD
            RoundedRectangle: pos: self.pos; size: self.size; radius: [dp(10)]
        Label:
            text: '输出格式'
            font_size: dp(14)
            color: MUTE
            size_hint_y: None
            height: dp(20)
            halign: 'left'
            text_size: self.size
        BoxLayout:
            spacing: dp(8)
            ToggleButton:
                id: fmt_auto
                text: '自动(按原格式)'
                group: 'fmt'
                state: 'down'
                font_size: dp(13)
            ToggleButton:
                id: fmt_flac
                text: 'FLAC (无损)'
                group: 'fmt'
                state: 'normal'
                font_size: dp(13)
            ToggleButton:
                id: fmt_mp3
                text: 'MP3 (320k)'
                group: 'fmt'
                state: 'normal'
                font_size: dp(13)

    # ---- FFmpeg 状态 ----
    Label:
        id: ffmpeg_lbl
        text: '● 正在检测 FFmpeg...'
        font_size: dp(13)
        color: MUTE
        size_hint_y: None
        height: dp(24)
        halign: 'left'
        text_size: self.size

    # ---- 添加文件按钮 ----
    BoxLayout:
        size_hint_y: None
        height: dp(58)
        spacing: dp(8)
        Button:
            text: '+ 添加 NCM 文件'
            font_size: dp(16)
            bold: True
            background_color: PRIMARY
            on_press: root.choose_files()
        Button:
            text: '从文件夹扫描'
            font_size: dp(14)
            background_color: (0.3, 0.34, 0.4, 1)
            on_press: root.choose_dir()

    # ---- 文件列表 ----
    ScrollView:
        canvas.before:
            Color: rgba: CARD
            RoundedRectangle: pos: self.pos; size: self.size; radius: [dp(10)]
        BoxLayout:
            id: file_list
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(10)
            spacing: dp(6)

    # ---- 进度条 ----
    ProgressBar:
        id: progress
        size_hint_y: None
        height: dp(10)
        value: 0
        max: 100

    # ---- 开始按钮 ----
    Button:
        id: start_btn
        text: '开始转换'
        font_size: dp(18)
        bold: True
        size_hint_y: None
        height: dp(54)
        background_color: PRIMARY
        on_press: root.start_convert()
        disabled: True

<StatusItem@BoxLayout>:
    size_hint_y: None
    height: dp(56)
    canvas.before:
        Color: rgba: (0.98, 0.99, 1, 1)
        RoundedRectangle: pos: self.pos; size: self.size; radius: [dp(6)]
    Label:
        id: status_icon
        text: '○'
        color: (0.6, 0.6, 0.6, 1)
        font_size: dp(20)
        size_hint_x: None
        width: dp(36)
    Label:
        id: filename
        text: ''
        color: INK
        font_size: dp(13)
        halign: 'left'
        valign: 'middle'
        text_size: self.size
        size_hint_x: 0.7
    Label:
        id: status_text
        text: '等待中'
        color: MUTE
        font_size: dp(12)
        halign: 'right'
        text_size: self.size
"""


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._files = []  # list[str]  待转换的 ncm 路径
        self._converting = False
        Clock.schedule_once(self._init_ffmpeg_label, 0.1)

    # ---------- FFmpeg 状态 ----------
    def _init_ffmpeg_label(self, _dt):
        ok = ncm2mp3.has_ffmpeg()
        lbl = self.ids.ffmpeg_lbl
        if ok:
            lbl.text = '● FFmpeg 已就绪 (支持 MP3 转码)'
            lbl.color = (0.18, 0.7, 0.36, 1)
        else:
            lbl.text = '● 未检测到 FFmpeg (仅能输出 FLAC, MP3 会失败)'
            lbl.color = (0.9, 0.35, 0.35, 1)

    # ---------- 选择文件/文件夹 ----------
    def choose_files(self):
        # 默认起点: Android 外部存储 /sdcard 或 PC 用户家目录
        start = '/sdcard' if os.path.isdir('/sdcard') else os.path.expanduser('~')
        fc = FileChooserListView(path=start, filters=['*.ncm'], multiselect=True)
        popup = Popup(title='选择 NCM 文件', content=fc, size_hint=(0.95, 0.9))
        fc.bind(on_submit=lambda inst, vals, _t: (self._add_files(vals), popup.dismiss()))
        # 加一个底部确定按钮 — Kivy FileChooser 双击也会 on_submit
        popup.open()

    def choose_dir(self):
        start = '/sdcard' if os.path.isdir('/sdcard') else os.path.expanduser('~')
        fc = FileChooserListView(path=start, dirselect=True)
        popup = Popup(title='选择文件夹 (含子目录)', content=fc, size_hint=(0.95, 0.9))

        def _pick(inst, vals):
            if not vals:
                return
            d = vals[0]
            ncm_files = []
            for root, _dirs, names in os.walk(d):
                for nm in names:
                    if nm.lower().endswith('.ncm'):
                        ncm_files.append(os.path.join(root, nm))
            if ncm_files:
                self._add_files(ncm_files)
            popup.dismiss()

        fc.bind(on_submit=lambda inst, vals, _t: _pick(inst, vals))
        popup.open()

    def _add_files(self, paths):
        for p in paths:
            if p not in self._files:
                self._files.append(p)
        self._refresh_list()
        self.ids.start_btn.disabled = (len(self._files) == 0) or self._converting

    def _refresh_list(self):
        lst = self.ids.file_list
        lst.clear_widgets()
        for p in self._files:
            item = StatusItem()
            item.ids.filename.text = os.path.basename(p)
            lst.add_widget(item)

    # ---------- 转换 ----------
    def _selected_format(self):
        if self.ids.fmt_flac.state == 'down':
            return 'flac'
        if self.ids.fmt_mp3.state == 'down':
            return 'mp3'
        return 'auto'

    def start_convert(self):
        if self._converting or not self._files:
            return
        fmt = self._selected_format()
        if fmt == 'mp3' and not ncm2mp3.has_ffmpeg():
            self._toast('未检测到 FFmpeg, 无法转 MP3, 请选 FLAC')
            return
        self._converting = True
        self.ids.start_btn.disabled = True
        self.ids.start_btn.text = '转换中...'
        Thread(target=self._convert_worker, args=(list(self._files), fmt), daemon=True).start()

    def _convert_worker(self, files, fmt):
        # Android 输出目录: /sdcard/NCM2MP3_Output (Android 11+ 通常可写)
        out_dir = '/sdcard/NCM2MP3_Output'
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            # 沙箱回退
            from android.permissions import request_permissions, Permission  # noqa
            out_dir = os.path.join(os.environ.get('EXTERNAL_STORAGE', '/sdcard'), 'NCM2MP3_Output')
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError:
                out_dir = None  # 让 decrypt_ncm 用输入同目录
        total = len(files)
        for i, p in enumerate(files, 1):
            token = {'ok': False, 'msg': ''}
            # 同步更新进度到主线程
            Clock.schedule_once(lambda _dt, idx=i, pp=p: self._set_status(pp, 'run', '转换中...'), 0)
            try:
                out = ncm2mp3.decrypt_ncm(p, output_dir=out_dir,
                                          output_format=fmt, keep_intermediate=False)
                token['ok'] = True
                token['msg'] = os.path.basename(out)
            except Exception as e:
                token['msg'] = f'失败: {e}'[:60]
            Clock.schedule_once(
                lambda _dt, pp=p, ok=token['ok'], msg=token['msg']:
                    self._set_status(pp, 'ok' if ok else 'fail', msg),
                0,
            )
            Clock.schedule_once(lambda _dt, idx=i: self._set_progress(idx * 100 // total), 0)
        Clock.schedule_once(lambda _dt: self._finish(), 0)

    def _set_status(self, path, state, msg=''):
        """state: 'run' / 'ok' / 'fail'"""
        idx = self._files.index(path)
        lst = self.ids.file_list
        if idx >= len(lst.children):
            return
        item = lst.children[len(lst.children) - 1 - idx]
        if state == 'run':
            item.ids.status_icon.text = '◐'
            item.ids.status_icon.color = (0.1, 0.55, 0.95, 1)
            item.ids.status_text.text = '转换中...'
            item.ids.status_text.color = (0.1, 0.55, 0.95, 1)
        elif state == 'ok':
            item.ids.status_icon.text = '✓'
            item.ids.status_icon.color = (0.2, 0.75, 0.4, 1)
            item.ids.status_text.text = '完成'
            item.ids.status_text.color = (0.2, 0.75, 0.4, 1)
        elif state == 'fail':
            item.ids.status_icon.text = '✗'
            item.ids.status_icon.color = (0.95, 0.3, 0.3, 1)
            item.ids.status_text.text = msg or '失败'
            item.ids.status_text.color = (0.95, 0.3, 0.3, 1)

    def _set_progress(self, val):
        self.ids.progress.value = val

    def _finish(self):
        self._converting = False
        self.ids.start_btn.disabled = False
        self.ids.start_btn.text = '重新开始'

    def _toast(self, msg):
        popup = Popup(title='提示', content=Label(text=msg), size_hint=(0.7, 0.2))
        popup.open()
        Clock.schedule_once(lambda _dt: popup.dismiss(), 2)


class StatusItem(BoxLayout):
    pass


class NcmApp(App):
    def build(self):
        Window.clearcolor = (0.96, 0.97, 0.98, 1)
        return Builder.load_string(KV)


if __name__ == '__main__':
    NcmApp().run()
