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
from kivy.uix.textinput import TextInput

# Android 文件选择器回调标识
_PICK_FILES_REQUEST = 42

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

    TextInput:
        id: path_input
        hint_text: '输入或粘贴 .ncm 文件/文件夹路径（或点击下方选择文件）'
        font_name: ZH_FONT
        multiline: False
        size_hint_y: None
        height: dp(48)

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(8)
        Button:
            text: '选择文件'
            font_name: ZH_FONT
            on_press: root.pick_files()
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
        self._activity = None
        self._register_activity_callback()
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
                self.ids.ffmpeg_lbl.text = '核心模块正常，未检测到 FFmpeg；建议选择 FLAC 输出。'
        except Exception as exc:
            self.ids.ffmpeg_lbl.text = '核心模块异常: ' + repr(exc)

    def _register_activity_callback(self):
        try:
            from android.activity import bind
            bind(on_activity_result=self._on_activity_result)
        except Exception as exc:
            print('bind activity callback failed:', exc)

    def add_input_path(self):
        value = self.ids.path_input.text.strip().strip('"')
        if not value:
            self._toast('请先输入路径')
            return
        self._add_path(value)
        self.ids.path_input.text = ''

    def pick_files(self):
        """调用 Android 原生文件选择器（支持多选 .ncm）。"""
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')

            activity = PythonActivity.mActivity
            if activity is None:
                self._toast('无法获取 Activity')
                return
            self._activity = activity

            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType('*/*')
            # 仅允许选择 .ncm 文件
            mime_types = ['audio/*', 'application/octet-stream']
            intent.putExtra(Intent.EXTRA_MIME_TYPES, mime_types)
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
            intent.putExtra(Intent.EXTRA_LOCAL_ONLY, True)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

            activity.startActivityForResult(intent, _PICK_FILES_REQUEST)
            self._toast('请选择 .ncm 文件（可多选）')
        except Exception as exc:
            self._toast('打开文件选择器失败: ' + str(exc)[:80])

    def _on_activity_result(self, request_code, result_code, intent):
        self._toast(f'收到回调 request={request_code} result={result_code}')
        if request_code != _PICK_FILES_REQUEST:
            return
        if result_code != -1:  # Activity.RESULT_OK == -1
            self._toast('未选择文件')
            return
        if intent is None:
            self._toast('回调 intent 为空')
            return

        try:
            uris = []
            clip_data = intent.getClipData()
            if clip_data:
                self._toast(f'多选 {clip_data.getItemCount()} 个文件')
                for i in range(clip_data.getItemCount()):
                    item = clip_data.getItemAt(i)
                    uris.append(item.getUri())
            else:
                data = intent.getData()
                if data:
                    uris.append(data)
                    self._toast('单选 1 个文件')

            if not uris:
                self._toast('未获取到文件')
                return

            self._toast(f'开始复制 {len(uris)} 个文件...')
            Thread(target=self._copy_uris_background, args=(uris,), daemon=True).start()
        except Exception as exc:
            self._toast('处理选择结果失败: ' + str(exc)[:80])

    def _copy_uris_background(self, uris):
        """后台线程复制 URI，避免阻塞 UI。"""
        copied = []
        errors = []
        for uri in uris:
            try:
                local_path = self._copy_uri_to_temp(uri)
                if local_path:
                    copied.append(local_path)
                else:
                    errors.append('copy returned None')
            except Exception as exc:
                errors.append(str(exc)[:60])

        def _finish(_dt):
            if copied:
                self._add_files(copied)
            if errors:
                self._toast(f'{len(errors)} 个文件复制失败: {errors[0]}')

        Clock.schedule_once(_finish, 0)

    def _copy_uri_to_temp(self, uri):
        """把 content:// URI 复制到 App 私有缓存目录，返回本地路径。"""
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        ctx = activity.getApplicationContext()
        content_resolver = ctx.getContentResolver()

        # 查询原始文件名
        cursor = content_resolver.query(uri, None, None, None, None)
        display_name = None
        if cursor:
            try:
                if cursor.moveToFirst():
                    idx = cursor.getColumnIndex('_display_name')
                    if idx >= 0:
                        display_name = cursor.getString(idx)
            finally:
                cursor.close()

        if not display_name:
            import uuid
            display_name = 'unknown_' + uuid.uuid4().hex[:8] + '.ncm'
        if not display_name.lower().endswith('.ncm'):
            display_name += '.ncm'

        cache_dir = Path(ctx.getCacheDir().getAbsolutePath()) / 'picked_ncm'
        cache_dir.mkdir(parents=True, exist_ok=True)
        dst = cache_dir / display_name

        # 通过 content resolver 打开输入流并复制
        FileOutputStream = autoclass('java.io.FileOutputStream')

        ins = content_resolver.openInputStream(uri)
        if ins is None:
            raise RuntimeError('openInputStream returned None')
        try:
            fos = FileOutputStream(str(dst))
            try:
                buffer = bytearray(8192)
                total = 0
                while True:
                    n = ins.read(buffer)
                    if n == -1:
                        break
                    fos.write(buffer, 0, n)
                    total += n
            finally:
                fos.close()
        finally:
            ins.close()

        return str(dst)

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
