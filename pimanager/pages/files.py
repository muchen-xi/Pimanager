"""
PiManager 文件管理页面（NiceGUI 版）
- 本地/远程双面板文件浏览
- 上传、下载、删除、重命名、新建目录、运行文件
"""
import os
import threading
import stat as stat_module
from datetime import datetime
from pathlib import Path

from nicegui import ui

from pimanager.state import AppState


class FilesPage:
    """文件管理页面。"""

    def __init__(self):
        self.state = AppState.get()
        self._dual_pane = True

        # 远程文件状态
        self._remote_path = '/'
        self._remote_items = []
        self._remote_selected = None

        # 本地文件状态
        self._local_path = str(Path.home())
        self._local_items = []
        self._local_selected = None

        # UI 引用
        self._remote_list = None
        self._local_list = None
        self._remote_path_lbl = None
        self._local_path_lbl = None
        self._dual_btn = None

    def build(self):
        with ui.column().classes('w-full q-pa-md'):
            ui.label('文件管理').classes('text-h5')

            # ── 工具栏 ──
            with ui.row().classes('w-full items-center q-mt-sm'):
                self._dual_btn = ui.button(
                    '',
                    icon='view_column',
                    on_click=self._toggle_dual_pane
                ).props('flat')
                ui.separator().props('vertical')
                ui.button('上传', icon='upload_file', on_click=self._upload_file)
                ui.button('下载', icon='download', on_click=self._download_file)
                ui.button('运行', icon='play_arrow', on_click=self._run_file)
                ui.separator().props('vertical')
                ui.button('新建目录', icon='create_new_folder', on_click=self._mkdir)
                ui.button('重命名', icon='drive_file_rename_outline', on_click=self._rename)
                ui.button('删除', icon='delete', on_click=self._delete).props('color=negative')

            # ── 双面板 ──
            with ui.row().classes('w-full') as self._pane_row:
                self._build_remote_pane()
                self._build_local_pane()

            # ── 连接后自动加载 ──
            if self.state.connected:
                self._load_remote()

        self._update_dual_btn_text()

    # ─── 远程面板 ──────────────────────────────────

    def _build_remote_pane(self):
        with ui.column().classes('col') as self._remote_col:
            ui.label('远程 (树莓派)').classes('text-subtitle2')
            self._remote_path_lbl = ui.label('/').classes('text-caption text-grey')
            ui.separator()
            self._remote_list = ui.column().classes('w-full')

    def _load_remote(self, path: str = None):
        """加载远程目录列表。"""
        if path:
            self._remote_path = path
        if not self.state.connected:
            return

        self._remote_path_lbl.set_text(self._remote_path)
        self._remote_list.clear()

        def _fetch():
            try:
                items = self.state.ssh.list_dir(self._remote_path)
                ui.timer(0, lambda: self._render_remote_list(items), once=True)
            except Exception as e:
                ui.timer(0, lambda: ui.notify(f'列出远程目录失败: {e}', type='negative'), once=True)

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_remote_list(self, items: list):
        self._remote_list.clear()
        self._remote_items = items
        self._remote_selected = None

        with self._remote_list:
            # 返回上级
            if self._remote_path != '/':
                with ui.row().classes('w-full items-center cursor-pointer hover:bg-grey-8'):
                    ui.icon('arrow_upward').classes('text-green')
                    ui.label('..').on('click',
                        lambda: self._load_remote(str(Path(self._remote_path).parent)))

            for item in items:
                name = item['name']
                is_dir = item['is_dir']
                size = item.get('size', 0)
                icon = 'folder' if is_dir else 'insert_drive_file'
                icon_class = 'text-yellow-8' if is_dir else 'text-blue'

                with ui.row().classes('w-full items-center cursor-pointer hover:bg-grey-8') as row:
                    ui.icon(icon).classes(icon_class)
                    lbl = ui.label(name).classes('text-caption')
                    if is_dir:
                        lbl.on('click', lambda n=name: self._remote_enter_dir(n))
                    else:
                        lbl.on('click', lambda n=name: self._remote_select(n))
                        ui.label(self._format_size(size)).classes(
                            'text-caption text-grey text-right')

    def _remote_enter_dir(self, name: str):
        path = self._remote_path.rstrip('/') + '/' + name
        self._load_remote(path)

    def _remote_select(self, name: str):
        self._remote_selected = name

    # ─── 本地面板 ──────────────────────────────────

    def _build_local_pane(self):
        with ui.column().classes('col') as self._local_col:
            ui.label('本机').classes('text-subtitle2')
            self._local_path_lbl = ui.label(self._local_path).classes('text-caption text-grey')
            ui.separator()
            self._local_list = ui.column().classes('w-full')

        self._load_local()

    def _load_local(self, path: str = None):
        """加载本地目录列表。"""
        if path:
            self._local_path = path

        self._local_path_lbl.set_text(self._local_path)
        self._local_list.clear()

        try:
            items = []
            with os.scandir(self._local_path) as it:
                for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
                    try:
                        items.append({
                            'name': entry.name,
                            'path': entry.path,
                            'is_dir': entry.is_dir(),
                            'size': entry.stat().st_size if entry.is_file() else 0,
                        })
                    except OSError:
                        continue
            self._render_local_list(items)
        except Exception as e:
            ui.notify(f'读取本地目录失败: {e}', type='negative', position='top')

    def _render_local_list(self, items: list):
        self._local_list.clear()
        self._local_items = items
        self._local_selected = None

        with self._local_list:
            # 返回上级
            parent = str(Path(self._local_path).parent)
            if self._local_path != str(Path(self._local_path).anchor):
                with ui.row().classes('w-full items-center cursor-pointer hover:bg-grey-8'):
                    ui.icon('arrow_upward').classes('text-green')
                    ui.label('..').on('click', lambda p=parent: self._load_local(p))

            for item in items:
                name = item['name']
                is_dir = item['is_dir']
                icon = 'folder' if is_dir else 'insert_drive_file'
                icon_class = 'text-yellow-8' if is_dir else 'text-blue'

                with ui.row().classes('w-full items-center cursor-pointer hover:bg-grey-8'):
                    ui.icon(icon).classes(icon_class)
                    lbl = ui.label(name).classes('text-caption')
                    if is_dir:
                        lbl.on('click', lambda n=name: self._local_enter_dir(n))
                    else:
                        lbl.on('click', lambda n=name: self._local_select(n))
                        ui.label(self._format_size(item['size'])).classes(
                            'text-caption text-grey text-right')

    def _local_enter_dir(self, name: str):
        path = os.path.join(self._local_path, name)
        self._load_local(path)

    def _local_select(self, name: str):
        self._local_selected = name

    # ─── 双面板切换 ────────────────────────────────

    def _toggle_dual_pane(self):
        self._dual_pane = not self._dual_pane
        self._update_dual_btn_text()
        if self._dual_pane:
            self._local_col.set_visibility(True)
        else:
            self._local_col.set_visibility(False)

    def _update_dual_btn_text(self):
        self._dual_btn.set_text('单栏' if self._dual_pane else '双栏')

    # ─── 文件操作 ──────────────────────────────────

    def _upload_file(self):
        """上传文件到远程。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return

        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(title='选择要上传的文件')
        root.destroy()
        if not path:
            return

        remote_name = os.path.basename(path)
        remote_dst = self._remote_path.rstrip('/') + '/' + remote_name

        def _do():
            def cb(transferred, total):
                pass  # 可添加进度条
            ok, msg = self.state.ssh.upload_file(path, remote_dst, cb)
            ui.timer(0, lambda: self._on_transfer_result(ok, msg, '上传'), once=True)

        threading.Thread(target=_do, daemon=True).start()

    def _download_file(self):
        """下载远程文件到本地。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return
        if not self._remote_selected:
            ui.notify('请先选择远程文件', type='warning', position='top')
            return

        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        save_path = filedialog.asksaveasfilename(
            title='保存到',
            initialfile=self._remote_selected)
        root.destroy()
        if not save_path:
            return

        remote_src = self._remote_path.rstrip('/') + '/' + self._remote_selected

        def _do():
            ok, msg = self.state.ssh.download_file(remote_src, save_path)
            ui.timer(0, lambda: self._on_transfer_result(ok, msg, '下载'), once=True)

        threading.Thread(target=_do, daemon=True).start()

    def _on_transfer_result(self, ok: bool, msg: str, action: str):
        if ok:
            ui.notify(f'{action}成功', type='positive', position='top')
            self._load_remote()
        else:
            ui.notify(f'{action}失败: {msg}', type='negative', position='top')

    def _run_file(self):
        """运行选中的远程文件。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return
        if not self._remote_selected:
            ui.notify('请先选择文件', type='warning', position='top')
            return

        name = self._remote_selected
        remote_path = self._remote_path.rstrip('/') + '/' + name

        # 自动检测解释器
        if name.endswith('.py'):
            cmd = f'python3 {remote_path}'
        elif name.endswith('.sh'):
            cmd = f'bash {remote_path}'
        else:
            cmd = f'chmod +x {remote_path} && {remote_path}'

        def _do():
            code, out, err = self.state.ssh.exec_command(cmd, timeout=30)
            ui.timer(0, lambda: self._show_run_result(name, code, out, err), once=True)

        threading.Thread(target=_do, daemon=True).start()

    def _show_run_result(self, name: str, code: int, out: str, err: str):
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            ui.label(f'运行结果: {name}').classes('text-h6')
            if out:
                ui.label('标准输出:').classes('text-caption')
                ui.log().classes('w-full pm-terminal').push(out)
            if err:
                ui.label('错误输出:').classes('text-caption text-red')
                ui.log().classes('w-full pm-terminal').push(err)
            ui.label(f'退出码: {code}').classes('text-caption')
            ui.button('关闭', on_click=dialog.close)
        dialog.open()

    def _mkdir(self):
        """新建远程目录。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return

        with ui.dialog() as dialog, ui.card():
            ui.label('新建目录').classes('text-h6')
            name = ui.input('目录名称')
            with ui.row():
                def _do_create():
                    if not name.value:
                        return
                    path = self._remote_path.rstrip('/') + '/' + name.value

                    def _do():
                        ok, msg = self.state.ssh.create_remote_dir(path)
                        ui.timer(0, lambda: self._on_mkdir_result(ok, msg), once=True)

                    threading.Thread(target=_do, daemon=True).start()
                    dialog.close()

                ui.button('创建', on_click=_do_create)
                ui.button('取消', on_click=dialog.close)
        dialog.open()

    def _on_mkdir_result(self, ok: bool, msg: str):
        if ok:
            ui.notify('目录已创建', type='positive', position='top')
            self._load_remote()
        else:
            ui.notify(f'创建失败: {msg}', type='negative', position='top')

    def _rename(self):
        """重命名远程文件。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return
        if not self._remote_selected:
            ui.notify('请先选择文件', type='warning', position='top')
            return

        old_name = self._remote_selected
        with ui.dialog() as dialog, ui.card():
            ui.label('重命名').classes('text-h6')
            new_name = ui.input('新名称', value=old_name)
            with ui.row():
                def _do_rename():
                    if not new_name.value:
                        return
                    old_path = self._remote_path.rstrip('/') + '/' + old_name
                    new_path = self._remote_path.rstrip('/') + '/' + new_name.value

                    def _do():
                        ok, msg = self.state.ssh.rename_remote(old_path, new_path)
                        ui.timer(0, lambda: self._on_rename_result(ok, msg), once=True)

                    threading.Thread(target=_do, daemon=True).start()
                    dialog.close()

                ui.button('重命名', on_click=_do_rename)
                ui.button('取消', on_click=dialog.close)
        dialog.open()

    def _on_rename_result(self, ok: bool, msg: str):
        if ok:
            ui.notify('重命名成功', type='positive', position='top')
            self._remote_selected = None
            self._load_remote()
        else:
            ui.notify(f'重命名失败: {msg}', type='negative', position='top')

    def _delete(self):
        """删除远程文件。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return
        if not self._remote_selected:
            ui.notify('请先选择文件', type='warning', position='top')
            return

        confirm = self.state.get_behavior('confirm_before_delete', True)
        if confirm:
            with ui.dialog() as dialog, ui.card():
                ui.label(f'确认删除 "{self._remote_selected}"？').classes('text-h6')
                with ui.row():
                    def _confirm_del():
                        dialog.close()
                        self._do_delete()

                    ui.button('删除', color='negative', on_click=_confirm_del)
                    ui.button('取消', on_click=dialog.close)
            dialog.open()
        else:
            self._do_delete()

    def _do_delete(self):
        name = self._remote_selected
        path = self._remote_path.rstrip('/') + '/' + name

        def _do():
            ok, msg = self.state.ssh.delete_remote(path)
            ui.timer(0, lambda: self._on_delete_result(ok, msg), once=True)

        threading.Thread(target=_do, daemon=True).start()

    def _on_delete_result(self, ok: bool, msg: str):
        if ok:
            ui.notify('已删除', type='positive', position='top')
            self._remote_selected = None
            self._load_remote()
        else:
            ui.notify(f'删除失败: {msg}', type='negative', position='top')

    # ─── 工具方法 ──────────────────────────────────

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f'{size} B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f} KB'
        elif size < 1024 * 1024 * 1024:
            return f'{size / 1024 / 1024:.1f} MB'
        else:
            return f'{size / 1024 / 1024 / 1024:.1f} GB'
