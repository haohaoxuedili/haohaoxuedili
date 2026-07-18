# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from threading import Thread

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

# Android 上 Kivy 默认字体不支持中文，注册内置中文字体并通过自定义组件默认使用
if sys.platform.startswith('linux') and 'ANDROID_ROOT' in os.environ:
    _bundled_font = os.path.join(os.path.dirname(__file__), 'DroidSansFallback.ttf')
    if os.path.isfile(_bundled_font):
        try:
            LabelBase.register(name='AndroidFallback', fn_regular=_bundled_font)
        except Exception as _exc:
            print('font register failed:', _exc)


class ZhLabel(Label):
    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'AndroidFallback')
        super().__init__(**kwargs)


class ZhButton(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'AndroidFallback')
        super().__init__(**kwargs)


class ZhTextInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'AndroidFallback')
        super().__init__(**kwargs)


class ZhToggleButton(ToggleButton):
    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'AndroidFallback')
        super().__init__(**kwargs)


KV = """
#:kivy 2.2.0

<RootWidget>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(12)

    ZhLabel:
        text: 'NCM 转 MP3 / FLAC'
        font_size: dp(24)
        bold: True
        size_hint_y: None
        height: dp(52)

    ZhLabel:
        id: ffmpeg_lbl
        text: '正在检测核心模块...'
        font_size: dp(14)
        size_hint_y: None
        height: dp(28)
        halign: 'left'
        text_size: self.size

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(124)
        spacing: dp(8)
        ZhLabel:
            text: '输出格式'
            font_size: dp(14)
            size_hint_y: None
            height: dp(24)
            halign: 'left'
            text_size: self.size
        BoxLayout:
            spacing: dp(8)
            ZhToggleButton:
                id: fmt_auto
                text: '自动'
                group: 'fmt'
                state: 'down'
            ZhToggleButton:
                id: fmt_flac
                text: 'FLAC'
                group: 'fmt'
            ZhToggleButton:
                id: fmt_mp3
                text: 'MP3'
                group: 'fmt'

    ZhTextInput:
        id: path_input
        hint_text: '输入或粘贴 .ncm 文件路径，或文件夹路径'
        multiline: False
        size_hint_y: None
        height: dp(48)

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(8)
        ZhButton:
            text: '添加路径'
            on_press: root.add_input_path()
        ZhButton:
            text: '扫描下载目录'
            on_press: root.scan_downloads()

    ScrollView:
        BoxLayout:
            id: file_list
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(6)

    ProgressBar:
        id: progress
        size_hint_y: None
        height: dp(10)
        max: 100
        value: 0

    ZhButton:
        id: start_btn
        text: '开始转换'
        size_hint_y: None
        height: dp(54)
        disabled: True
        on_press: root.start_convert()

<StatusItem>:
    size_hint_y: None
    height: dp(42)
    ZhLabel:
        id: filename
        text: ''
        font_size: dp(12)
        halign: 'left'
        valign: 'middle'
        text_size: self.size
    ZhLabel:
        id: status_text
        text: '等待中'
        font_size: dp(12)
        size_hint_x: 0.35
        halign: 'right'
        text_size: self.size
"""


class StatusItem(BoxLayout):
    pass


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._files = []
        self._converting = False
        Clock.schedule_once(lambda _dt: self.check_core(), 0.5)

    def _load_core(self):
        import ncm2mp3
        return ncm2mp3

    def check_core(self):
        try:
            core = self._load_core()
            if core.has_ffmpeg():
                self.ids.ffmpeg_lbl.text = '核心模块正常，FFmpeg 已就绪。'
            else:
                self.ids.ffmpeg_lbl.text = '核心模块正常，未检测到 FFmpeg；建议输出 FLAC。'
        except Exception as exc:
            self.ids.ffmpeg_lbl.text = '核心模块异常: ' + repr(exc)

    def add_input_path(self):
        value = self.ids.path_input.text.strip().strip('"')
        if not value:
            self._toast('请先输入路径')
            return
        self._add_path(value)
        self.ids.path_input.text = ''

    def scan_downloads(self):
        for folder in ['/sdcard/Download', '/sdcard/Music', '/storage/emulated/0/Download']:
            if os.path.isdir(folder):
                self._add_path(folder)
                return
        self._toast('没有找到下载目录')

    def _add_path(self, value):
        p = Path(value)
        found = []
        if p.is_file() and p.suffix.lower() == '.ncm':
            found.append(str(p))
        elif p.is_dir():
            for root, _dirs, names in os.walk(str(p)):
                for name in names:
                    if name.lower().endswith('.ncm'):
                        found.append(os.path.join(root, name))
        else:
            self._toast('路径不存在或不是 .ncm 文件')
            return
        self._add_files(found)

    def _add_files(self, files):
        added = 0
        for path in files:
            if path not in self._files:
                self._files.append(path)
                row = StatusItem()
                row.ids.filename.text = os.path.basename(path)
                row.ids.status_text.text = '等待中'
                self.ids.file_list.add_widget(row)
                added += 1
        self.ids.start_btn.disabled = not self._files
        self._toast(f'已添加 {added} 个文件')

    def _selected_format(self):
        if self.ids.fmt_mp3.state == 'down':
            return 'mp3'
        if self.ids.fmt_flac.state == 'down':
            return 'flac'
        return 'auto'

    def start_convert(self):
        if self._converting or not self._files:
            return
        self._converting = True
        self.ids.start_btn.disabled = True
        Thread(target=self._run_convert, daemon=True).start()

    def _run_convert(self):
        try:
            core = self._load_core()
            total = len(self._files)
            out_fmt = self._selected_format()
            children = list(reversed(self.ids.file_list.children))
            for idx, path in enumerate(self._files):
                Clock.schedule_once(lambda _dt, i=idx: self._set_status(children[i], '转换中'))
                try:
                    result = core.decrypt_ncm_file(path, output_format=out_fmt, keep_intermediate=False)
                    Clock.schedule_once(lambda _dt, i=idx: self._set_status(children[i], '完成: ' + os.path.basename(result)))
                except Exception as exc:
                    Clock.schedule_once(lambda _dt, i=idx, e=exc: self._set_status(children[i], '失败: ' + str(e)[:40]))
                Clock.schedule_once(lambda _dt, v=(idx + 1) * 100 / total: setattr(self.ids.progress, 'value', v))
        finally:
            Clock.schedule_once(lambda _dt: self._finish_convert())

    def _set_status(self, row, text):
        row.ids.status_text.text = text

    def _finish_convert(self):
        self._converting = False
        self.ids.start_btn.disabled = False
        self.ids.start_btn.text = '重新开始'

    def _toast(self, msg):
        popup = Popup(title='提示', content=ZhLabel(text=msg), size_hint=(0.78, 0.22))
        popup.open()
        Clock.schedule_once(lambda _dt: popup.dismiss(), 2)


class NcmApp(App):
    def build(self):
        Window.clearcolor = (0.96, 0.97, 0.98, 1)
        self.icon = 'app.png'
        Builder.load_string(KV)
        return RootWidget()


if __name__ == '__main__':
    NcmApp().run()
