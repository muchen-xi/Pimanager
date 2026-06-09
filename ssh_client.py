"""
PiManager SSH 客户端 - 基于 paramiko 的轻量 SSH 管理
支持密钥认证、命令执行、SFTP 文件传输、自动重连、连接保活
"""
import threading
import time
import os
import stat
import logging
from typing import Callable, Optional
import paramiko

logger = logging.getLogger(__name__)


class StreamingCommand:
    """流式命令执行句柄 — 支持取消和状态查询。

    由 exec_command_streaming 返回，通过 .cancel() 可中止正在运行的远程命令。
    """

    def __init__(self):
        self._running = False
        self._cancelled = False
        self._channel = None

    @property
    def is_running(self) -> bool:
        return self._running

    def send_ctrl_c(self):
        """发送 Ctrl+C (SIGINT) 给远程进程（通过 PTY 的 stdin）。

        优雅终止：先发 Ctrl+C，远程进程可以做清理工作（如 Python 的 finally 块）。
        不设置 _cancelled 标志，保留 readline 循环继续读取进程退出前的最后输出。
        如果进程不响应，再调用 cancel() 强制关闭通道。
        """
        if self._channel and not self._channel.closed:
            try:
                self._channel.send('\x03')  # Ctrl+C
            except Exception:
                pass

    def cancel(self):
        """强制关闭 SSH 通道（硬终止）。"""
        self._cancelled = True
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass


class SSHClient:
    """SSH 连接管理器 — 支持自动重连、连接保活、并发命令执行。"""

    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._connected = False
        self._host = ""
        self._port = 22
        self._username = ""
        self._key_path: Optional[str] = None
        self._password: Optional[str] = None
        self._shell: Optional[paramiko.Channel] = None
        self._lock = threading.RLock()  # ★ 可重入锁
        self._cmd_lock = threading.Lock()  # ★ 命令执行独立锁
        self._keep_alive_job = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def host(self) -> str:
        return self._host

    def connect(self, host: str, port: int = 22, username: str = "pi",
                key_path: str = None, password: str = None,
                timeout: int = 10) -> tuple[bool, str]:
        """建立SSH连接。"""
        with self._lock:
            if self._connected:
                self.disconnect()

            # ★ 保存连接参数用于自动重连
            self._host = host
            self._port = port
            self._username = username
            self._key_path = key_path
            self._password = password

            result = self._do_connect(host, port, username, key_path, password, timeout)
            if result[0]:
                self._reconnect_attempts = 0
            return result

    def _do_connect(self, host, port, username, key_path, password, timeout):
        """内部连接实现。"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 密钥认证
            if key_path and os.path.exists(key_path):
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(key_path)
                except paramiko.SSHException:
                    try:
                        key = paramiko.RSAKey.from_private_key_file(key_path)
                    except paramiko.SSHException:
                        key = None

                if key:
                    client.connect(host, port=port, username=username,
                                  pkey=key, timeout=timeout,
                                  banner_timeout=timeout,
                                  auth_timeout=timeout)
                else:
                    return False, "密钥格式不支持或无效"
            elif password:
                client.connect(host, port=port, username=username,
                              password=password, timeout=timeout,
                              banner_timeout=timeout,
                              auth_timeout=timeout)
            else:
                return False, "请提供密钥或密码"

            self._client = client
            self._sftp = client.open_sftp()
            self._connected = True
            self._host = host
            self._port = port
            logger.info(f"SSH 连接成功: {username}@{host}:{port}")
            return True, "连接成功"

        except paramiko.AuthenticationException:
            logger.error(f"认证失败: {username}@{host}")
            return False, "认证失败：密钥或密码错误"
        except paramiko.SSHException as e:
            logger.error(f"SSH错误: {e}")
            return False, f"SSH错误: {str(e)}"
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False, f"连接失败: {str(e)}"

    def disconnect(self) -> None:
        """断开连接。"""
        with self._lock:
            self._stop_keep_alive()
            if self._shell:
                try:
                    self._shell.close()
                except Exception:
                    pass
                self._shell = None
            if self._sftp:
                try:
                    self._sftp.close()
                except Exception:
                    pass
                self._sftp = None
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            self._connected = False
            logger.info("SSH 连接已断开")

    def reconnect(self) -> tuple[bool, str]:
        """使用上次的连接参数自动重连。"""
        if not self._host:
            return False, "无可用连接参数"
        logger.info(f"尝试重连 {self._username}@{self._host} (第 {self._reconnect_attempts + 1} 次)")
        return self.connect(
            self._host, self._port, self._username,
            self._key_path, self._password)

    def _auto_reconnect(self) -> bool:
        """自动重连（带退避策略）。"""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"已达最大重连次数 ({self._max_reconnect_attempts})")
            return False
        self._reconnect_attempts += 1
        # 指数退避：1s, 2s, 4s
        delay = 2 ** (self._reconnect_attempts - 1)
        logger.info(f"等待 {delay}s 后重连...")
        time.sleep(delay)
        ok, msg = self.reconnect()
        if ok:
            self._reconnect_attempts = 0
        return ok

    def exec_command(self, command: str, timeout: int = 30) -> tuple[int, str, str]:
        """执行远程命令，返回 (exit_code, stdout, stderr)。

        如果连接断开，自动尝试重连一次。
        """
        with self._cmd_lock:
            if not self._connected or not self._client:
                return -1, "", "未连接"

            try:
                stdin, stdout, stderr = self._client.exec_command(
                    command, timeout=timeout)
                exit_code = stdout.channel.recv_exit_status()
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                return exit_code, out, err
            except paramiko.SSHException as e:
                logger.warning(f"命令执行失败 (SSH错误): {e}")
                # ★ 尝试自动重连
                if self._auto_reconnect():
                    # 重试一次
                    try:
                        stdin, stdout, stderr = self._client.exec_command(
                            command, timeout=timeout)
                        exit_code = stdout.channel.recv_exit_status()
                        out = stdout.read().decode("utf-8", errors="replace")
                        err = stderr.read().decode("utf-8", errors="replace")
                        return exit_code, out, err
                    except Exception as e2:
                        return -1, "", f"重连后执行失败: {str(e2)}"
                else:
                    self._connected = False
                    return -1, "", f"连接已断开，重连失败: {str(e)}"
            except Exception as e:
                return -1, "", str(e)

    def exec_command_batch(self, commands: list[str], timeout: int = 30) -> list[tuple[int, str, str]]:
        """批量执行命令（合并为一个 SSH 调用减少往返）。"""
        if not commands:
            return []
        combined = "; echo '---CMD_SPLIT---'; ".join(commands)
        code, out, err = self.exec_command(combined, timeout)
        if code != 0:
            return [(code, out, err)]

        results = []
        parts = out.split("---CMD_SPLIT---")
        for i, cmd in enumerate(commands):
            results.append((0, parts[i].strip() if i < len(parts) else "", err))
        return results

    def exec_command_streaming(self, command, on_stdout=None, on_stderr=None,
                                on_done=None, timeout=None):
        """执行远程命令并实时流式返回输出（不阻塞等待进程结束）。

        与 exec_command 不同，此方法立即返回 StreamingCommand 句柄，
        输出通过回调函数逐行推送，适合长时间运行的命令。

        Args:
            command: 要执行的 Shell 命令
            on_stdout: 回调 on_stdout(line) — 每行 stdout 输出时调用
            on_stderr: 回调 on_stderr(line) — 每行 stderr 输出时调用
            on_done: 回调 on_done(exit_code, error_message) — 命令完成时调用
            timeout: 通道创建超时秒数（None=默认）

        Returns:
            StreamingCommand 句柄（支持 .cancel()）
        """
        handle = StreamingCommand()

        if not self._connected or not self._client:
            if on_done:
                on_done(-1, "未连接")
            return handle

        def _stream():
            try:
                # ★ get_pty=True 分配伪终端 — 远程进程以为自己在真实终端里，
                #   自动切换为行缓冲，print() 立即送出，不再积压。
                #   副作用：stdout 和 stderr 合并到 stdout 一个流。
                stdin, stdout, stderr = self._client.exec_command(
                    command, timeout=timeout, get_pty=True)
                handle._channel = stdout.channel
                handle._running = True

                # ★ PTY 模式下 stdout/stderr 已合并，直接读 stdout 即可
                for line in iter(stdout.readline, ""):
                    if handle._cancelled:
                        break
                    if line and on_stdout:
                        on_stdout(line)

                # 获取退出码
                try:
                    exit_code = stdout.channel.recv_exit_status()
                except Exception:
                    exit_code = -1

                handle._running = False
                if on_done:
                    on_done(exit_code, None)

            except Exception as e:
                handle._running = False
                if on_done:
                    on_done(-1, str(e))

        thread = threading.Thread(target=_stream, daemon=True)
        thread.start()
        return handle

    # ========== 连接保活 ==========

    def start_keep_alive(self, interval: int = 30):
        """启动连接保活（每 interval 秒发送轻量命令）。"""
        self._stop_keep_alive()
        self._do_keep_alive(interval)

    def _do_keep_alive(self, interval: int):
        """执行保活检测。"""
        if not self._connected:
            return
        try:
            code, _, _ = self.exec_command("echo 'keepalive'", timeout=5)
            if code != 0:
                logger.warning("保活检测失败，尝试重连...")
                self._auto_reconnect()
        except Exception:
            pass
        # 使用 threading.Timer 而非 after（因为这是非 GUI 模块）
        self._keep_alive_job = threading.Timer(interval, self._do_keep_alive, [interval])
        self._keep_alive_job.daemon = True
        self._keep_alive_job.start()

    def _stop_keep_alive(self):
        """停止保活。"""
        if self._keep_alive_job:
            self._keep_alive_job.cancel()
            self._keep_alive_job = None

    # ========== 文件操作 ==========

    def list_dir(self, remote_path: str, limit: int = None, offset: int = 0) -> list[dict]:
        """列出远程目录。支持分页（limit/offset）。"""
        with self._lock:
            if not self._sftp:
                return []
            try:
                items = []
                for entry in self._sftp.listdir_attr(remote_path):
                    item = {
                        "name": entry.filename,
                        "size": entry.st_size,
                        "mtime": entry.st_mtime,
                        "is_dir": stat.S_ISDIR(entry.st_mode),
                        "is_link": stat.S_ISLNK(entry.st_mode),
                        "permissions": entry.st_mode,
                    }
                    items.append(item)
                # 排序：目录在前，按名称
                items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
                # ★ 分页支持
                if limit is not None:
                    items = items[offset:offset + limit]
                return items
            except Exception as e:
                logger.warning(f"列出目录失败 {remote_path}: {e}")
                return []

    def get_file_info(self, remote_path: str) -> Optional[dict]:
        """获取单个文件/目录信息。"""
        with self._lock:
            if not self._sftp:
                return None
            try:
                attr = self._sftp.stat(remote_path)
                return {
                    "name": os.path.basename(remote_path),
                    "size": attr.st_size,
                    "mtime": attr.st_mtime,
                    "is_dir": stat.S_ISDIR(attr.st_mode),
                    "permissions": attr.st_mode,
                }
            except Exception:
                return None

    def download_file(self, remote_path: str, local_path: str,
                      progress_callback: Callable = None) -> tuple[bool, str]:
        """下载文件（含大小校验）。"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.get(remote_path, local_path, callback=progress_callback)
                # ★ 传输后校验文件大小
                remote_size = self._sftp.stat(remote_path).st_size
                local_size = os.path.getsize(local_path)
                if remote_size != local_size:
                    logger.warning(
                        f"文件大小不匹配: 远程={remote_size}, 本地={local_size}")
                    return False, f"文件大小不匹配: {remote_size} vs {local_size}"
                logger.info(f"下载完成: {os.path.basename(remote_path)}")
                return True, "下载完成"
            except Exception as e:
                logger.error(f"下载失败 {remote_path}: {e}")
                return False, f"下载失败: {str(e)}"

    def upload_file(self, local_path: str, remote_path: str,
                    progress_callback: Callable = None) -> tuple[bool, str]:
        """上传文件（含大小校验）。"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.put(local_path, remote_path, callback=progress_callback)
                # ★ 传输后校验文件大小
                local_size = os.path.getsize(local_path)
                remote_size = self._sftp.stat(remote_path).st_size
                if local_size != remote_size:
                    logger.warning(
                        f"文件大小不匹配: 本地={local_size}, 远程={remote_size}")
                    return False, f"文件大小不匹配: {local_size} vs {remote_size}"
                logger.info(f"上传完成: {os.path.basename(local_path)}")
                return True, "上传完成"
            except Exception as e:
                logger.error(f"上传失败 {local_path}: {e}")
                return False, f"上传失败: {str(e)}"

    def delete_remote(self, remote_path: str) -> tuple[bool, str]:
        """删除远程文件/目录。"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                info = self.get_file_info(remote_path)
                if info is None:
                    return False, "文件不存在"
                if info["is_dir"]:
                    self._rmdir_recursive(remote_path)
                else:
                    self._sftp.remove(remote_path)
                logger.info(f"已删除: {remote_path}")
                return True, "删除成功"
            except Exception as e:
                logger.error(f"删除失败 {remote_path}: {e}")
                return False, f"删除失败: {str(e)}"

    def create_remote_dir(self, remote_path: str) -> tuple[bool, str]:
        """创建远程目录。"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.mkdir(remote_path)
                return True, "创建成功"
            except Exception as e:
                return False, f"创建失败: {str(e)}"

    def rename_remote(self, old_path: str, new_path: str) -> tuple[bool, str]:
        """重命名远程文件。"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.rename(old_path, new_path)
                return True, "重命名成功"
            except Exception as e:
                return False, f"重命名失败: {str(e)}"

    def _rmdir_recursive(self, path: str) -> None:
        """★ 迭代删除目录（避免大目录栈溢出）。"""
        # 使用栈实现迭代删除
        stack = [(path, False)]
        while stack:
            current_path, should_delete = stack.pop()
            if should_delete:
                try:
                    self._sftp.rmdir(current_path)
                except Exception as e:
                    logger.warning(f"删除目录失败 {current_path}: {e}")
                continue

            # 先处理子项，再删除当前目录
            stack.append((current_path, True))
            try:
                for item in self._sftp.listdir_attr(current_path):
                    item_path = f"{current_path}/{item.filename}"
                    if stat.S_ISDIR(item.st_mode):
                        stack.append((item_path, False))
                    else:
                        try:
                            self._sftp.remove(item_path)
                        except Exception as e:
                            logger.warning(f"删除文件失败 {item_path}: {e}")
            except Exception as e:
                logger.warning(f"列举目录失败 {current_path}: {e}")

    # ========== 系统状态 ==========

    @staticmethod
    def _parse_kv_lines(text: str) -> list[tuple[str, str]]:
        """解析 KEY:VALUE 行输出，返回 [(key, value), ...] 列表。"""
        pairs = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            pairs.append((key.strip(), val.strip()))
        return pairs

    def get_system_status(self) -> dict:
        """获取树莓派系统状态（合并为 1 次 SSH 往返，大幅优化响应时间）。"""
        status = {
            "hostname": self._host,
            "cpu_percent": 0.0, "cpu_temp": 0.0,
            "memory_total": 0, "memory_used": 0, "memory_percent": 0.0,
            "disk_total": 0, "disk_used": 0, "disk_percent": 0.0,
            "uptime": "", "load_avg": "", "os_version": "", "kernel": "",
            "error": "",
        }

        # ★ 一次 SSH 调用获取所有数据，每行一个字段
        script = (
            "echo CPU_TEMP:$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0);"
            "echo CPU_PCT:$(top -bn1 | head -5 | grep '%Cpu' | sed 's/,/ /g' | awk '{for(i=1;i<=NF;i++) if($i~/^id$/){print 100-$(i-1);exit}}');"
            "echo MEM:$(free -m | grep Mem | awk '{print $2,$3}');"
            "echo DISK:$(df -BM / | tail -1 | awk '{print $2,$3,$5}' | tr -d '%');"
            "echo UPTIME:$(uptime -p 2>/dev/null || uptime);"
            "echo LOAD:$(uptime | awk -F'load average:' '{print $2}' | xargs);"
            "echo OS:$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"');"
            "echo KERNEL:$(uname -r)"
        )
        code, out, err = self.exec_command(script, timeout=15)

        if code != 0 or not out.strip():
            return status

        for key, val in self._parse_kv_lines(out):
            try:
                if key == "CPU_TEMP":
                    status["cpu_temp"] = float(val) / 1000.0
                elif key == "CPU_PCT":
                    status["cpu_percent"] = float(val)
                elif key == "MEM":
                    parts = val.split()
                    if len(parts) >= 2:
                        status["memory_total"] = int(parts[0])
                        status["memory_used"] = int(parts[1])
                        status["memory_percent"] = (int(parts[1]) / int(parts[0]) * 100) if int(parts[0]) > 0 else 0
                elif key == "DISK":
                    parts = val.split()
                    if len(parts) >= 3:
                        status["disk_total"] = int(parts[0].replace("M", ""))
                        status["disk_used"] = int(parts[1].replace("M", ""))
                        status["disk_percent"] = float(parts[2])
                elif key == "UPTIME":
                    status["uptime"] = val
                elif key == "LOAD":
                    status["load_avg"] = val
                elif key == "OS":
                    status["os_version"] = val
                elif key == "KERNEL":
                    status["kernel"] = val
            except (ValueError, IndexError):
                pass

        return status

    def get_sidebar_stats(self) -> dict:
        """获取侧边栏精简状态（1 次 SSH 往返）。"""
        script = (
            "echo CPU_PCT:$(top -bn1 | head -5 | grep '%Cpu' | sed 's/,/ /g' | awk '{for(i=1;i<=NF;i++) if($i~/^id$/){print 100-$(i-1);exit}}');"
            "echo MEM:$(free -m | grep Mem | awk '{print $2,$3}');"
            "echo IP:$(hostname -I 2>/dev/null | awk '{print $1}');"
            "echo TEMP:$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)"
        )
        code, out, err = self.exec_command(script, timeout=10)
        result = {"cpu": 0.0, "mem_total": 0, "mem_used": 0, "mem_pct": 0.0,
                   "ip": "--", "temp": 0.0}

        if code != 0 or not out.strip():
            return result

        for key, val in self._parse_kv_lines(out):
            try:
                if key == "CPU_PCT":
                    result["cpu"] = float(val)
                elif key == "MEM":
                    parts = val.split()
                    if len(parts) >= 2:
                        result["mem_total"] = int(parts[0])
                        result["mem_used"] = int(parts[1])
                        result["mem_pct"] = (int(parts[1]) / int(parts[0]) * 100) if int(parts[0]) > 0 else 0
                elif key == "IP":
                    result["ip"] = val if val else "--"
                elif key == "TEMP":
                    result["temp"] = float(val) / 1000.0
            except (ValueError, IndexError):
                pass

        return result

    def test_connection(self) -> bool:
        """测试连接是否存活。"""
        if not self._connected:
            return False
        try:
            code, _, _ = self.exec_command("echo 'alive'", timeout=5)
            return code == 0
        except Exception:
            return False
