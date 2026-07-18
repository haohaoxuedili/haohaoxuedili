# -*- coding: utf-8 -*-

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout

KV = """
#:kivy 2.2.0

<RootWidget>:
    orientation: 'vertical'
    padding: dp(20)
    spacing: dp(12)

    Label:
        text: 'NCM 转 MP3 / FLAC'
        font_size: dp(24)
        bold: True
        size_hint_y: None
        height: dp(56)

    Label:
        id: status
        text: '应用已启动，正在检测核心模块...'
        font_size: dp(15)
        halign: 'center'
        valign: 'middle'
        text_size: self.size

    Button:
        text: '检测核心模块'
        size_hint_y: None
        height: dp(52)
        on_press: root.check_core()
"""


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(lambda _dt: self.check_core(), 0.5)

    def check_core(self):
        try:
            import ncm2mp3
            ok = ncm2mp3.has_ffmpeg()
            if ok:
                self.ids.status.text = '核心模块正常，FFmpeg 已就绪。'
            else:
                self.ids.status.text = '核心模块正常，未检测到 FFmpeg。'
        except Exception as exc:
            self.ids.status.text = '核心模块异常: ' + repr(exc)


class NcmApp(App):
    def build(self):
        Window.clearcolor = (0.96, 0.97, 0.98, 1)
        self.icon = 'app.png'
        Builder.load_string(KV)
        return RootWidget()


if __name__ == '__main__':
    NcmApp().run()
