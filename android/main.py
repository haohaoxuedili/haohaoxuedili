# -*- coding: utf-8 -*-

import os
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
        height: dp(80)
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

    Label:
        id: folder_lbl
        text: '请将 .ncm 文件放入手机主目录的 NCM转换 文件夹，然后点击扫描。'
        font_name: ZH_FONT
        color: TEXT_COLOR
        font_size: dp(12)
        size_hint_y: None
        height: dp(58)
        halign: 'left'
        text_size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(8)
        Button:
            text: '创建/查看文件夹'
            font_name: ZH_FONT
            on_press: root.prepare_convert_folder()
        Button:
            text: '扫描转换文件夹'
            font_name: ZH_FONT
            on_press: root.scan_convert_folder()

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
        self._convert_folder_path = None
        Clock.schedule_once(lambda _dt: self.request_storage_permissions(), 0.2)
        Clock.schedule_once(lambda _dt: self.check_core(), 0.5)
        Clock.schedule_once(lambda _dt: self.prepare_convert_folder(show_toast=False), 0.8)

    def _load_core(self):
        import ncm2mp3
        return ncm2mp3

    def request_storage_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            perms = [
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ]
            if hasattr(Permission, 'READ_MEDIA_AUDIO'):
                perms.append(Permission.READ_MEDIA_AUDIO)
            request_permissions(perms)
        except Exception as exc:
            print('request storage permissions failed:', exc)
        self._request_manage_all_files_permission()

    def _request_manage_all_files_permission(self):
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            if Build.VERSION.SDK_INT < 30:
                return

            Environment = autoclass('android.os.Environment')
            if Environment.isExternalStorageManager():
                return

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            Uri = autoclass('android.net.Uri')

            activity = PythonActivity.mActivity
            package_name = activity.getPackageName()
            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            intent.setData(Uri.parse('package:' + package_name))
            activity.startActivity(intent)
            self._toast('请开启“允许管理所有文件”，返回后再扫描')
        except Exception as exc:
            print('request manage all files failed:', exc)

    def check_core(self):
        try:
            core = self._load_core()
            if core.has_ffmpeg():
                self.ids.ffmpeg_lbl.text = '核心模块正常，FFmpeg 已就绪。'
            else:
                self.ids.ffmpeg_lbl.text = '核心模块正常，未检测到 FFmpeg；建议选择 FLAC 输出。'
        except Exception as exc:
            self.ids.ffmpeg_lbl.text = '核心模块异常: ' + repr(exc)

    def _convert_folder_candidates(self):
        candidates = [
            Path('/sdcard/NCM转换'),
            Path('/storage/emulated/0/NCM转换'),
            Path('/sdcard/Download/NCM转换'),
            Path('/storage/emulated/0/Download/NCM转换'),
        ]
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            if activity is not None:
                ext_dir = activity.getExternalFilesDir(None)
                if ext_dir is not None:
                    candidates.append(Path(ext_dir.getAbsolutePath()) / 'NCM转换')
        except Exception as exc:
            print('get external files dir failed:', exc)
        return candidates

    def _convert_folder(self):
        for folder in self._convert_folder_candidates():
            try:
                if folder.exists() or folder.mkdir(parents=True, exist_ok=True) is None:
                    if folder.exists():
                        return folder
            except Exception:
                continue
        return Path('/sdcard/Download/NCM转换')

    def prepare_convert_folder(self, show_toast=True):
        folder = self._convert_folder()
        if folder.exists():
            self._convert_folder_path = folder
            self.ids.folder_lbl.text = (
                '请将 .ncm 文件放入下面这个文件夹，然后点击“扫描转换文件夹”。\n路径: ' + str(folder)
            )
            if show_toast:
                self._toast('转换文件夹已准备好: ' + str(folder))
        else:
            self.ids.folder_lbl.text = '创建转换文件夹失败，请手动创建: /sdcard/Download/NCM转换'
            if show_toast:
                self._toast('创建文件夹失败，请检查存储权限')

    def scan_convert_folder(self):
        folder = self._convert_folder_path
        if folder is None or not folder.exists():
            self.prepare_convert_folder(show_toast=False)
            folder = self._convert_folder_path
        if folder is None or not folder.exists():
            self._toast('转换文件夹不存在，请先点击“创建/查看文件夹”')
            return
        self._add_path(str(folder))

    def _add_path(self, value):
        p = Path(value)
        found = []
        if p.is_file() and self._is_ncm_file(p):
            found.append(str(p))
        elif p.is_dir():
            for root, _dirs, names in os.walk(str(p)):
                for name in names:
                    file_path = Path(root) / name
                    if self._is_ncm_file(file_path):
                        found.append(str(file_path))
        else:
            self._toast('路径不存在或不是 .ncm 文件')
            return
        if not found:
            preview = ''
            if p.is_dir():
                try:
                    names = os.listdir(str(p))[:5]
                    if names:
                        preview = '，当前看到: ' + ', '.join(names)[:60]
                except Exception:
                    pass
            self._toast('没有找到 .ncm 文件，请确认放入: ' + str(p) + preview)
            return
        self._toast(f'找到 {len(found)} 个 .ncm 文件')
        self._add_files(found)

    def _is_ncm_file(self, path):
        try:
            if not Path(path).is_file():
                return False
            with open(path, 'rb') as f:
                return f.read(8) == b'CTENFDAM'
        except Exception:
            return False

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
                    Clock.schedule_once(lambda _dt, i=idx, e=exc: self._set_status(children[i], '失败: ' + str(e)[:80]))
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
