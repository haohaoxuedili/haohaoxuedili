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

# Android 上 Kivy 默认字体不支持中文，注册内置中文字体
_BUNDLED_FONT = os.path.join(os.path.dirname(__file__), 'DroidSansFallback.ttf')
if os.path.isfile(_BUNDLED_FONT):
    try:
        LabelBase.register(name='AndroidFallback', fn_regular=_BUNDLED_FONT)
    except Exception as _exc:
        print('font register failed:', _exc)


KV = """
#:kivy 2.2.0
#:set ZH_FONT 'AndroidFallback'
#:set TEXT_COLOR (0.12, 0.12, 0.12, 1)

<RootWidget>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(12)

    Label:
        text: 'NCM 转 MP3 / FLAC'
        font_name: ZH_FONT
        color: TEXT_COLOR
        font_size: dp(24)
        bold: True
        size_hint_y: None
        height: dp(52)

    Label:
        id: ffmpeg_lbl
        text: '正在检测核心模块...'
        font_name: ZH_FONT
        color: TEXT_COLOR
        font_size: dp(11)
        size_hint_y: None
        height: dp(150)
        halign: 'left'
        text_size: self.size

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(124)
        spacing: dp(8)
        Label:
            text: '输出格式'
            font_name: ZH_FONT
            color: TEXT_COLOR
            font_size: dp(14)
            size_hint_y: None
            height: dp(24)
            halign: 'left'
            text_size: self.size
        BoxLayout:
            spacing: dp(8)
            ToggleButton:
                id: fmt_auto
                text: '自动'
                font_name: ZH_FONT
                group: 'fmt'
                state: 'down'
            ToggleButton:
                id: fmt_flac
                text: 'FLAC'
                font_name: ZH_FONT
                group: 'fmt'
            ToggleButton:
                id: fmt_mp3
                text: 'MP3'
                font_name: ZH_FONT
                group: 'fmt'

    TextInput:
        id: path_input
        hint_text: '输入或粘贴 .ncm 文件路径，或文件夹路径'
        font_name: ZH_FONT
        multiline: False
        size_hint_y: None
        height: dp(48)

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(8)
        Button:
            text: '添加路径'
            font_name: ZH_FONT
            on_press: root.add_input_path()
        Button:
            text: '扫描下载目录'
            font_name: ZH_FONT
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

    Button:
        id: start_btn
        text: '开始转换'
        font_name: ZH_FONT
        size_hint_y: None
        height: dp(54)
        disabled: True
        on_press: root.start_convert()

<StatusItem>:
    size_hint_y: None
    height: dp(42)
    Label:
        id: filename
        text: ''
        font_name: ZH_FONT
        color: TEXT_COLOR
        font_size: dp(12)
        halign: 'left'
        valign: 'middle'
        text_size: self.size
    Label:
        id: status_text
        text: '等待中'
        font_name: ZH_FONT
        color: TEXT_COLOR
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
        # 临时自动测试：启动后填充测试目录并触发转换
        Clock.schedule_once(lambda _dt: self._auto_test(), 2.0)

    def _auto_test(self):
        try:
            self.ids.ffmpeg_lbl.text = '自动测试中...'
            # 先测试 subprocess 能否直接执行 ffmpeg
            core = self._load_core()
            ffmpeg = core._find_ffmpeg()
            try:
                import subprocess, shlex
                # 测试 A: 直接列表参数
                try:
                    p1 = subprocess.run([ffmpeg, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    r1 = f'list code={p1.returncode}'
                except Exception as e1:
                    r1 = f'list error={repr(e1)}'
                # 测试 B: 通过 sh -c
                try:
                    p2 = subprocess.run(['sh', '-c', f'{shlex.quote(ffmpeg)} -version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    r2 = f'shell code={p2.returncode} err={p2.stderr.decode()[:200]}'
                except Exception as e2:
                    r2 = f'shell error={repr(e2)}'
                # 测试 C: 检查文件属性
                try:
                    p3 = subprocess.run(['sh', '-c', f'ls -lZ {shlex.quote(ffmpeg)}; id; pwd; echo $PATH'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    r3 = f'ls code={p3.returncode}\n{p3.stdout.decode()[:400]}'
                except Exception as e3:
                    r3 = f'ls error={repr(e3)}'
                with open('/sdcard/Android/data/io.github.idoknow.ncm2mp3/files/ncm_test/ffmpeg_test.log', 'w', encoding='utf-8') as f:
                    f.write(f'ffmpeg={ffmpeg}\n{r1}\n{r2}\n{r3}\n')
            except Exception as e:
                with open('/sdcard/Android/data/io.github.idoknow.ncm2mp3/files/ncm_test/ffmpeg_test.log', 'w', encoding='utf-8') as f:
                    f.write(f'ffmpeg={ffmpeg}\nerror={repr(e)}\n')
            # 使用应用外部存储私有目录，避免 Android 10+ Scoped Storage 限制
            self.ids.path_input.text = '/sdcard/Android/data/io.github.idoknow.ncm2mp3/files/ncm_test'
            # 选择 MP3 格式以测试 FFmpeg 转码
            self.ids.fmt_mp3.state = 'down'
            self.ids.fmt_auto.state = 'normal'
            self.ids.fmt_flac.state = 'normal'
            self.add_input_path()
            Clock.schedule_once(lambda _dt: self.start_convert(), 0.5)
        except Exception as exc:
            self.ids.ffmpeg_lbl.text = '自动测试异常: ' + repr(exc)

    def _load_core(self):
        import ncm2mp3
        return ncm2mp3

    def check_core(self):
        try:
            core = self._load_core()
            # 调试: 显示 ffmpeg 搜索路径信息
            import os, sys
            from pathlib import Path
            app_dir = Path(getattr(sys, '_APP_DIR', '') or os.environ.get('ANDROID_APP_PATH', ''))
            file_dir = Path(__file__).resolve().parent if '__file__' in globals() else Path('.')
            core_app_dir = core._android_app_dir()
            cands = core._candidate_ffmpeg_paths()
            cand_status = '\n'.join(f'{p} -> exists={p.is_file()}' for p in cands[:3])
            try:
                ffmpeg_path = core._find_ffmpeg()
            except Exception as e:
                ffmpeg_path = f'ERROR: {e}'
            info = (f'app_dir={app_dir}\nfile_dir={file_dir}\n'
                    f'core_app_dir={core_app_dir}\n'
                    f'ffmpeg_path={ffmpeg_path}\n'
                    f'has_ffmpeg={core.has_ffmpeg()}\n{cand_status}')
            if core.has_ffmpeg():
                self.ids.ffmpeg_lbl.text = '核心模块正常，FFmpeg 已就绪。\n' + info
            else:
                self.ids.ffmpeg_lbl.text = '核心模块正常，未检测到 FFmpeg；建议输出 FLAC。\n' + info
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
        candidates = [
            '/sdcard/Android/data/io.github.idoknow.ncm2mp3/files',
            '/sdcard/Download',
            '/sdcard/Music',
            '/storage/emulated/0/Download',
        ]
        for folder in candidates:
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
                    result = core.decrypt_ncm(path, output_format=out_fmt, keep_intermediate=False)
                    Clock.schedule_once(lambda _dt, i=idx: self._set_status(children[i], '完成: ' + os.path.basename(result)))
                except Exception as exc:
                    err_text = repr(exc)
                    # 临时：把完整异常写到文件便于调试
                    try:
                        with open('/sdcard/Android/data/io.github.idoknow.ncm2mp3/files/ncm_test/error.log', 'a', encoding='utf-8') as f:
                            f.write(err_text + '\n')
                    except Exception:
                        pass
                    Clock.schedule_once(lambda _dt, i=idx, e=exc: self._set_status(children[i], '失败: ' + str(e)[:200]))
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
        popup = Popup(
            title='提示',
            title_color=(0.12, 0.12, 0.12, 1),
            content=Label(text=msg, font_name='AndroidFallback', color=(0.12, 0.12, 0.12, 1)),
            size_hint=(0.78, 0.22)
        )
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
