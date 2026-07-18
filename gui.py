# -*- coding: utf-8 -*-
"""NCM 转 MP3 图形界面 (PyQt5)。

特性:
  - 拖拽/选择添加 NCM 文件或目录
  - 选择输出目录
  - 后台线程转换, 不卡 UI
  - 列表实时显示状态 (等待/转换中/成功/失败)
  - 现代扁平化亮色配色 + 圆角按钮
"""

import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QProgressBar, QFrame, QSplitter, QStyleFactory, QMessageBox,
    QComboBox, QCheckBox,
)

from ncm2mp3 import decrypt_ncm, has_ffmpeg, FFmpegNotFoundError, _find_ffmpeg


# ---------- 主题色 ----------
COLOR_BG = "#f5f7fa"
COLOR_CARD = "#ffffff"
COLOR_PRIMARY = "#FF3A55"  # 网易红
COLOR_PRIMARY_HOVER = "#E62E48"
COLOR_PRIMARY_PRESSED = "#C92640"
COLOR_SUCCESS = "#27C93F"
COLOR_FAIL = "#FF5F57"
COLOR_WAIT = "#9AA0A6"
COLOR_TEXT = "#1f1f1f"
COLOR_TEXT_SUB = "#8a8a8a"
COLOR_BORDER = "#e6e8eb"


STYLE = f"""
QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget#RootWidget {{
    background-color: {COLOR_BG};
}}
QFrame#Card {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
}}
QLabel#AppName {{
    color: {COLOR_TEXT};
    font-size: 22px;
    font-weight: 600;
}}
QLabel#AppHint {{
    color: {COLOR_TEXT_SUB};
    font-size: 12px;
}}
QLabel#DropHint {{
    color: {COLOR_TEXT_SUB};
    font-size: 14px;
}}
QPushButton {{
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
}}
QPushButton:hover {{ background-color: #eef0f3; }}
QPushButton:pressed {{ background-color: #dfe2e6; }}
QPushButton#Primary {{
    background-color: {COLOR_PRIMARY};
    color: white;
    font-weight: 600;
    padding: 10px 22px;
}}
QPushButton#Primary:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }}
QPushButton#Primary:pressed {{ background-color: {COLOR_PRIMARY_PRESSED}; }}
QPushButton#Primary:disabled {{
    background-color: #ffc7cf; color: #fff;
}}
QPushButton#Ghost {{
    background-color: transparent;
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT};
}}
QPushButton#Ghost:hover {{
    background-color: {COLOR_BG};
    border-color: {COLOR_PRIMARY};
    color: {COLOR_PRIMARY};
}}
QProgressBar {{
    background-color: {COLOR_BG};
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {COLOR_PRIMARY};
    border-radius: 6px;
}}
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    border-bottom: 1px solid #eef0f3;
    padding: 6px 4px;
}}
QListWidget::item:selected {{
    background-color: #fff0f2;
    color: {COLOR_TEXT};
}}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #cfd2d6; border-radius: 5px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def _make_icon(color: str) -> QPixmap:
    """生成一个圆形状态图标。"""
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 12, 12)
    p.end()
    return QIcon(pix)


ICON_WAIT = None
ICON_RUN = None
ICON_OK = None
ICON_FAIL = None

def _init_icons():
    global ICON_WAIT, ICON_RUN, ICON_OK, ICON_FAIL
    ICON_WAIT = _make_icon(COLOR_WAIT)
    ICON_RUN = _make_icon(COLOR_PRIMARY)
    ICON_OK = _make_icon(COLOR_SUCCESS)
    ICON_FAIL = _make_icon(COLOR_FAIL)


# ---------- 后台转换线程 ----------
class ConvertWorker(QThread):
    progress = pyqtSignal(int, int)   # index, total
    item_done = pyqtSignal(int, bool, str)  # index, ok, message

    def __init__(self, files, output_dir, output_format="auto", keep_intermediate=False):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.output_format = output_format
        self.keep_intermediate = keep_intermediate

    def run(self):
        total = len(self.files)
        for i, path in enumerate(self.files):
            self.progress.emit(i, total)
            try:
                out = decrypt_ncm(path, self.output_dir,
                                  output_format=self.output_format,
                                  keep_intermediate=self.keep_intermediate)
                self.item_done.emit(i, True, f"OK: {Path(out).name}")
            except FFmpegNotFoundError as e:
                self.item_done.emit(i, False, "需要 FFmpeg 才能转 MP3")
            except FileNotFoundError as e:
                self.item_done.emit(i, False, f"跳过: {e}")
            except ValueError as e:
                self.item_done.emit(i, False, f"忽略: {e}")
            except Exception as e:
                self.item_done.emit(i, False, f"失败: {e}")
        self.progress.emit(total, total)


# ---------- 自定义可拖拽列表 ----------
class DropList(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        files = []
        for u in urls:
            local = u.toLocalFile()
            p = Path(local)
            if p.is_dir():
                files.extend(str(x) for x in p.rglob("*.ncm"))
            elif p.suffix.lower() == ".ncm":
                files.append(str(p))
        if files:
            self.files_dropped.emit(files)


# ---------- 主窗口 ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCM 转 MP3")
        self.resize(760, 560)
        self.setMinimumSize(620, 480)
        self.output_dir = None
        self.worker = None
        self._ok_count = 0
        self._build_ui()
        self._update_stats()

    def _build_ui(self):
        root = QWidget(); root.setObjectName("RootWidget")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 24, 24, 20)
        outer.setSpacing(14)

        # 顶部标题
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        logo = QLabel("🎵")
        logo.setStyleSheet("font-size: 26px;")
        title_row.addWidget(logo)
        col = QVBoxLayout(); col.setSpacing(0)
        name = QLabel("NCM 转 MP3")
        name.setObjectName("AppName")
        hint = QLabel("网易云音乐加密格式一键转换为 MP3 / FLAC")
        hint.setObjectName("AppHint")
        col.addWidget(name); col.addWidget(hint)
        title_row.addLayout(col)
        title_row.addStretch()
        self.btn_about = QPushButton("关于")
        self.btn_about.setObjectName("Ghost")
        self.btn_about.setCursor(Qt.PointingHandCursor)
        self.btn_about.clicked.connect(self._show_about)
        title_row.addWidget(self.btn_about)
        outer.addLayout(title_row)

        # 卡片1: 添加文件
        add_card = QFrame(); add_card.setObjectName("Card")
        add_l = QVBoxLayout(add_card)
        add_l.setContentsMargins(18, 16, 18, 16); add_l.setSpacing(10)

        add_row = QHBoxLayout()
        self.btn_add_file = QPushButton("  + 添加 NCM 文件")
        self.btn_add_file.setObjectName("Primary")
        self.btn_add_file.setCursor(Qt.PointingHandCursor)
        self.btn_add_file.clicked.connect(self._pick_files)
        self.btn_add_dir = QPushButton("  + 添加文件夹")
        self.btn_add_dir.setObjectName("Ghost")
        self.btn_add_dir.setCursor(Qt.PointingHandCursor)
        self.btn_add_dir.clicked.connect(self._pick_dir)
        add_row.addWidget(self.btn_add_file)
        add_row.addWidget(self.btn_add_dir)
        add_row.addStretch()
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_list)
        add_row.addWidget(self.btn_clear)
        add_l.addLayout(add_row)

        self.drop_hint = QLabel("或将 .ncm 文件 / 文件夹 拖拽到下方列表")
        self.drop_hint.setStyleSheet(
            f"color: {COLOR_TEXT_SUB}; font-size: 12px; padding-left: 2px;"
        )
        add_l.addWidget(self.drop_hint)
        outer.addWidget(add_card)

        # 卡片2: 文件列表
        list_card = QFrame(); list_card.setObjectName("Card")
        list_l = QVBoxLayout(list_card)
        list_l.setContentsMargins(18, 12, 18, 16); list_l.setSpacing(8)

        head = QHBoxLayout()
        head.addStretch()
        self.stats_label = QLabel("0 项")
        self.stats_label.setStyleSheet(f"color: {COLOR_TEXT_SUB}; font-size: 12px;")
        head.addWidget(self.stats_label)
        list_l.addLayout(head)

        self.list = DropList()
        self.list.files_dropped.connect(self._add_files)
        list_l.addWidget(self.list)

        # 整体进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        list_l.addWidget(self.progress)
        outer.addWidget(list_card, 1)

        # 卡片3: 输出 & 开始
        out_card = QFrame(); out_card.setObjectName("Card")
        out_l = QVBoxLayout(out_card)
        out_l.setContentsMargins(18, 14, 18, 14); out_l.setSpacing(10)

        row_out = QHBoxLayout()
        self.lbl_out = QLabel("输出目录：与源文件同目录")
        self.lbl_out.setStyleSheet(f"color: {COLOR_TEXT_SUB};")
        row_out.addWidget(self.lbl_out)
        row_out.addStretch()
        self.btn_out = QPushButton("选择输出目录")
        self.btn_out.setObjectName("Ghost")
        self.btn_out.setCursor(Qt.PointingHandCursor)
        self.btn_out.clicked.connect(self._pick_output)
        row_out.addWidget(self.btn_out)
        out_l.addLayout(row_out)

        # 输出格式选择 + FFmpeg 状态 + 保留中间文件
        row_fmt = QHBoxLayout()
        row_fmt.setSpacing(10)
        lbl_fmt = QLabel("输出格式：")
        lbl_fmt.setStyleSheet(f"color: {COLOR_TEXT};")
        row_fmt.addWidget(lbl_fmt)
        self.combo_fmt = QComboBox()
        self.combo_fmt.addItem("自动（按原格式, FLAC→FLAC / MP3→MP3）", "auto")
        self.combo_fmt.addItem("FLAC（无损, 不转码）", "flac")
        self.combo_fmt.addItem("MP3（320kbps, 需 FFmpeg）", "mp3")
        self.combo_fmt.setCurrentIndex(0)
        self.combo_fmt.currentIndexChanged.connect(self._on_fmt_changed)
        row_fmt.addWidget(self.combo_fmt, 1)

        self.ffmpeg_label = QLabel("")
        self.ffmpeg_label.setStyleSheet(f"color: {COLOR_TEXT_SUB}; font-size: 11px;")
        row_fmt.addWidget(self.ffmpeg_label)
        out_l.addLayout(row_fmt)

        self.chk_keep = QCheckBox("转 MP3 时保留中间的 FLAC 文件")
        self.chk_keep.setStyleSheet(f"color: {COLOR_TEXT_SUB}; font-size: 12px;")
        out_l.addWidget(self.chk_keep)

        row_start = QHBoxLayout()
        row_start.addStretch()
        self.btn_start = QPushButton("▶ 开始转换")
        self.btn_start.setObjectName("Primary")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setMinimumWidth(180)
        self.btn_start.clicked.connect(self._start_convert)
        row_start.addWidget(self.btn_start)
        row_start.addStretch()
        out_l.addLayout(row_start)
        outer.addWidget(out_card)

        # 初始化 FFmpeg 状态显示
        self._refresh_ffmpeg_status()

    # ----- 操作 -----
    def _add_files(self, files):
        existing = {self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())}
        for f in files:
            if f in existing:
                continue
            item = QListWidgetItem()
            item.setText(Path(f).name)
            item.setIcon(ICON_WAIT)
            item.setToolTip(f)
            item.setData(Qt.UserRole, f)
            self.list.addItem(item)
        self._update_stats()

    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择 NCM 文件", "", "NCM 文件 (*.ncm);;所有文件 (*)"
        )
        if files:
            self._add_files(files)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择包含 NCM 的文件夹")
        if d:
            ncm_files = [str(x) for x in Path(d).rglob("*.ncm")]
            if ncm_files:
                self._add_files(ncm_files)
            else:
                QMessageBox.information(self, "提示", "该文件夹下未发现 .ncm 文件")

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.output_dir = d
            self.lbl_out.setText(f"输出目录：{d}")

    def _clear_list(self):
        if self.worker and self.worker.isRunning():
            return
        self.list.clear()
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self._update_stats()

    def _refresh_ffmpeg_status(self):
        """根据当前选择的格式与 FFmpeg 是否可用, 刷新状态提示。"""
        fmt = self.combo_fmt.currentData()
        if fmt == "mp3":
            path = _find_ffmpeg()
            if path:
                is_bundled = "bundled" in path or getattr(__import__("sys"), "frozen", False)
                tag = "内置" if is_bundled else "系统"
                self.ffmpeg_label.setText(f"● {tag} FFmpeg 已就绪")
                self.ffmpeg_label.setStyleSheet(
                    f"color: {COLOR_SUCCESS}; font-size: 11px; font-weight: 600;"
                )
            else:
                self.ffmpeg_label.setText("● 未检测到 FFmpeg, 转 MP3 会失败")
                self.ffmpeg_label.setStyleSheet(
                    f"color: {COLOR_FAIL}; font-size: 11px; font-weight: 600;"
                )
        else:
            self.ffmpeg_label.setText("")
        self.chk_keep.setVisible(fmt == "mp3")

    def _on_fmt_changed(self):
        self._refresh_ffmpeg_status()

    def _update_stats(self):
        n = self.list.count()
        self.stats_label.setText(f"{n} 项")

    def _start_convert(self):
        if self.worker and self.worker.isRunning():
            return
        total = self.list.count()
        if total == 0:
            QMessageBox.information(self, "提示", "请先添加 NCM 文件")
            return
        fmt = self.combo_fmt.currentData()
        if fmt == "mp3" and not has_ffmpeg():
            ret = QMessageBox.warning(
                self, "FFmpeg 未安装",
                "你选择了输出 MP3, 但未检测到 FFmpeg。内层为 FLAC 的文件将转换失败。\n\n"
                "是否继续？(建议先安装 FFmpeg)\n"
                "Windows 下载: https://www.gyan.dev/ffmpeg/builds/",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret == QMessageBox.No:
                return
        files = [self.list.item(i).data(Qt.UserRole) for i in range(total)]
        # 重置状态
        for i in range(total):
            self.list.item(i).setIcon(ICON_WAIT)
            self.list.item(i).setText(Path(files[i]).name)
        self.progress.setRange(0, total)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.btn_start.setEnabled(False)
        self._ok_count = 0

        self.worker = ConvertWorker(
            files, self.output_dir,
            output_format=fmt,
            keep_intermediate=self.chk_keep.isChecked(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.item_done.connect(self._on_item_done)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, i, total):
        self.progress.setValue(i)
        if i < total:
            it = self.list.item(i)
            if it:
                it.setIcon(ICON_RUN)
                it.setText(f"{Path(self.list.item(i).data(Qt.UserRole)).name}  (转换中...)")

    def _on_item_done(self, i, ok, msg):
        it = self.list.item(i)
        if not it:
            return
        path = it.data(Qt.UserRole)
        it.setIcon(ICON_OK if ok else ICON_FAIL)
        it.setText(f"{Path(path).name}  —  {msg}")
        if ok:
            self._ok_count += 1

    def _on_finished(self):
        self.progress.setValue(self.progress.maximum())
        self.btn_start.setEnabled(True)
        QMessageBox.information(
            self, "转换完成",
            f"已完成 {self.list.count()} 个文件。\n成功 {self._ok_count} 个。"
        )

    def _show_about(self):
        QMessageBox.information(
            self, "关于 NCM 转 MP3",
            "NCM 转 MP3 / FLAC 工具\n\n"
            "· 支持单文件/批量/文件夹拖拽\n"
            "· 输出格式可选: 自动 / FLAC / MP3(320kbps)\n"
            "· 转 MP3 需要系统安装 FFmpeg (加到 PATH)\n"
            "· 自动写入标题、歌手、专辑、封面等标签\n"
            "· 后台线程转换, 界面不卡顿\n\n"
            "仅供个人合法使用，请勿用于侵犯版权。"
        )


def main():
    QApplication.setStyle(QStyleFactory.create("Fusion"))
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    _init_icons()
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
