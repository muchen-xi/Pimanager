"""
PiManager SSH 客户端 - 基于 paramiko 的轻量 SSH 管理
支持密钥认证、命令执行、SFTP 文件传输、自动重连、连接保活
"""
import threading
import time
import os
import stat
import socket
import ipaddress
import paramiko


def _sort_dir_key(item):
    """目录排序键：目录优先，再按名称字母序排列。"""
    return (not item['is_dir'], item['name'].lower())


# 流式命令执行句柄 — 支持取消和状态查询
class StreamingCommand:
    """由 exec_command_streaming 返回，通过 .cancel() 可中止正在运行的远程命令。"""

    def __init__(self):
        self._running = False
        self._cancelled = False
        self._channel = None

    @property
    def is_running(self):
        return self._running

    def send_ctrl_c(self):
        """发送 Ctrl+C (SIGINT) 给远程进程（通过 PTY 的 stdin）。

        优雅终止：先发 Ctrl+C，远程进程可以做清理工作（如 Python 的 finally 块）。
        不设置 _cancelled 标志，保留 readline 循环继续读取进程退出前的最后输出。
        如果进程不响应，再调用 cancel() 强制关闭通道。
        """
        if self._channel and not self._channel.closed:
            try:
                self._channel.send('\x03')
            except Exception as e:
                print(f"发送 Ctrl+C 失败: {e}")

    def cancel(self):
        """强制关闭 SSH 通道（硬终止）。"""
        self._cancelled = True
        if self._channel:
            try:
                self._channel.close()
            except Exception as e:
                print(f"关闭通道失败: {e}")


# SSH 连接管理器 — 支持自动重连、连接保活、并发命令执行
class SSHClient:

    def __init__(self):
        self._client = None
        self._sftp = None
        self._connected = False
        self._host = ''
        self._port = 22
        self._username = ''
        self._key_path = None
        self._password = None
        self._shell = None
        self._lock = threading.RLock()
        self._cmd_lock = threading.Lock()
        self._keep_alive_job = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._auto_rediscover = False
        self._original_hostname = ''  # 保存原始主机名，IP漂移时始终从此解析

    @property
    def connected(self):
        return self._connected

    @property
    def host(self):
        return self._host

    def set_auto_rediscover(self, enabled):
        """启用/禁用IP漂移自动修复"""
        self._auto_rediscover = bool(enabled)

    def _resolve_hostname(self, host, port=22):
        """
        解析主机名到IP地址
        :param host: 主机名或IP
        :param port: 端口
        :return: (ip地址, 原始主机名) 或 (None, host) 解析失败时
        """
        try:
            ipaddress.ip_address(host)
            return host, None
        except ValueError:
            pass

        try:
            addrinfo = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            if addrinfo:
                return addrinfo[0][4][0], host
        except socket.gaierror:
            pass
        return None, host

    def connect(self, host, port=22, username='pi',
                key_path=None, password=None, timeout=10):
        """建立SSH连接。
        :param host: 远程主机地址
        :param port: SSH 端口
        :param username: 登录用户名
        :param key_path: 私钥文件路径
        :param password: 登录密码
        :param timeout: 连接超时秒数
        :return: (成功标志, 消息)
        """
        with self._lock:
            if self._connected:
                self.disconnect()

            # 保存连接参数用于自动重连
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
                elif password:
                    client.connect(host, port=port, username=username,
                                  password=password, timeout=timeout,
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
            # 保存原始主机名用于IP漂移检测（IP地址不覆盖）
            try:
                ipaddress.ip_address(host)
            except ValueError:
                self._original_hostname = host
            print(f"SSH 连接成功: {username}@{host}:{port}")
            return True, "连接成功"

        except paramiko.AuthenticationException:
            print(f"认证失败: {username}@{host}")
            return False, "认证失败：密钥或密码错误"
        except paramiko.SSHException as e:
            print(f"SSH错误: {e}")
            return False, f"SSH错误: {str(e)}"
        except Exception as e:
            print(f"连接失败: {e}")
            return False, f"连接失败: {str(e)}"

    def disconnect(self):
        """断开连接。"""
        with self._lock:
            self._stop_keep_alive()
            if self._shell:
                try:
                    self._shell.close()
                except Exception as e:
                    print(f"关闭 Shell 通道失败: {e}")
                self._shell = None
            if self._sftp:
                try:
                    self._sftp.close()
                except Exception as e:
                    print(f"关闭 SFTP 失败: {e}")
                self._sftp = None
            if self._client:
                try:
                    self._client.close()
                except Exception as e:
                    print(f"关闭 SSH 客户端失败: {e}")
                self._client = None
            self._connected = False
            print("SSH 连接已断开")

    def reconnect(self):
        """使用上次的连接参数自动重连。
        :return: (成功标志, 消息)
        """
        if not self._host:
            return False, "无可用连接参数"
        print(f"尝试重连 {self._username}@{self._host} (第 {self._reconnect_attempts + 1} 次)")
        return self.connect(
            self._host, self._port, self._username,
            self._key_path, self._password)

    def _auto_reconnect(self):
        """自动重连（带退避策略 + IP漂移检测）。"""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            print(f"已达最大重连次数 ({self._max_reconnect_attempts})")
            return False
        self._reconnect_attempts += 1

        actual_host = self._host
        if self._auto_rediscover:
            # 始终从原始主机名解析，避免_host被IP覆盖后无法再检测漂移
            resolve_from = self._original_hostname or self._host
            resolved, _ = self._resolve_hostname(resolve_from, self._port)
            if resolved and resolved != self._host:
                actual_host = resolved
                print(f"IP漂移修复 ({self._reconnect_attempts}/{self._max_reconnect_attempts}): "
                      f"{self._host} -> {actual_host}")

        # 指数退避：1s, 2s, 4s
        delay = 2 ** (self._reconnect_attempts - 1)
        time.sleep(delay)
        ok, msg = self.connect(actual_host, self._port, self._username,
                               self._key_path, self._password)
        if ok:
            self._reconnect_attempts = 0
            self._host = actual_host
        return ok

    def exec_command(self, command, timeout=30):
        """执行远程命令。
        :param command: 要执行的 Shell 命令
        :param timeout: 超时秒数
        :return: (exit_code, stdout, stderr) 元组
        """
        with self._cmd_lock:
            if not self._connected or not self._client:
                return -1, '', "未连接"

            try:
                stdin, stdout, stderr = self._client.exec_command(
                    command, timeout=timeout)
                exit_code = stdout.channel.recv_exit_status()
                out = stdout.read().decode('utf-8', errors='replace')
                err = stderr.read().decode('utf-8', errors='replace')
                return exit_code, out, err
            except paramiko.SSHException as e:
                print(f"命令执行失败 (SSH错误): {e}")
                # 尝试自动重连
                if self._auto_reconnect():
                    # 重试一次
                    try:
                        stdin, stdout, stderr = self._client.exec_command(
                            command, timeout=timeout)
                        exit_code = stdout.channel.recv_exit_status()
                        out = stdout.read().decode('utf-8', errors='replace')
                        err = stderr.read().decode('utf-8', errors='replace')
                        return exit_code, out, err
                    except Exception as e2:
                        return -1, '', f"重连后执行失败: {str(e2)}"
                else:
                    self._connected = False
                    return -1, '', f"连接已断开，重连失败: {str(e)}"
            except Exception as e:
                return -1, '', str(e)

    def exec_command_batch(self, commands, timeout=30):
        """批量执行命令（合并为一个 SSH 调用减少往返）。
        :param commands: 命令列表
        :param timeout: 超时秒数
        :return: [(exit_code, stdout, stderr), ...] 结果列表
        """
        if not commands:
            return []
        combined = "; echo '---CMD_SPLIT---'; ".join(commands)
        code, out, err = self.exec_command(combined, timeout)
        if code != 0:
            return [(code, out, err)]

        results = []
        parts = out.split('---CMD_SPLIT---')
        for i, cmd in enumerate(commands):
            results.append((0, parts[i].strip() if i < len(parts) else '', err))
        return results

    def exec_command_streaming(self, command, on_stdout=None, on_stderr=None,
                                on_done=None, timeout=None):
        """执行远程命令并实时流式返回输出（不阻塞等待进程结束）。

        与 exec_command 不同，此方法立即返回 StreamingCommand 句柄，
        输出通过回调函数逐行推送，适合长时间运行的命令。
        :param command: 要执行的 Shell 命令
        :param on_stdout: 回调 on_stdout(line) — 每行 stdout 输出时调用
        :param on_stderr: 回调 on_stderr(line) — 每行 stderr 输出时调用
        :param on_done: 回调 on_done(exit_code, error_message) — 命令完成时调用
        :param timeout: 通道创建超时秒数（None=默认）
        :return: StreamingCommand 句柄（支持 .cancel()）
        """
        handle = StreamingCommand()

        if not self._connected or not self._client:
            if on_done:
                on_done(-1, "未连接")
            return handle

        def _stream():
            try:
                # get_pty=True 分配伪终端 — 远程进程以为自己在真实终端里，
                # 自动切换为行缓冲，print() 立即送出，不再积压。
                # 副作用：stdout 和 stderr 合并到 stdout 一个流。
                with self._cmd_lock:
                    stdin, stdout, stderr = self._client.exec_command(
                        command, timeout=timeout, get_pty=True)
                handle._channel = stdout.channel
                handle._running = True

                # PTY 模式下 stdout/stderr 已合并，直接读 stdout 即可
                for line in iter(stdout.readline, ''):
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

    def start_keep_alive(self, interval=30):
        """启动连接保活（每 interval 秒发送轻量命令）。"""
        self._stop_keep_alive()
        self._do_keep_alive(interval)

    def _do_keep_alive(self, interval):
        """执行保活检测。exec_command() 内部已处理 SSHException→自动重连，
        此处只做探测，不重复调用 _auto_reconnect() 避免浪费重试配额。"""
        if not self._connected:
            return
        try:
            code, _, _ = self.exec_command('echo "keepalive"', timeout=5)
            if code != 0:
                print("保活检测失败")
        except Exception as e:
            print(f"保活检测异常: {e}")
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

    def list_dir(self, remote_path, limit=None, offset=0):
        """列出远程目录。支持分页（limit/offset）。
        :param remote_path: 远程目录路径
        :param limit: 返回条目数上限
        :param offset: 分页偏移量
        :return: 文件/目录信息列表
        """
        with self._lock:
            if not self._sftp:
                return []
            try:
                items = []
                for entry in self._sftp.listdir_attr(remote_path):
                    item = {
                        'name': entry.filename,
                        'size': entry.st_size,
                        'mtime': entry.st_mtime,
                        'is_dir': stat.S_ISDIR(entry.st_mode),
                        'is_link': stat.S_ISLNK(entry.st_mode),
                        'permissions': entry.st_mode,
                    }
                    items.append(item)
                # 排序：目录在前，按名称
                items.sort(key=_sort_dir_key)
                # 分页支持
                if limit is not None:
                    items = items[offset:offset + limit]
                return items
            except Exception as e:
                print(f"列出目录失败 {remote_path}: {e}")
                return []

    def get_file_info(self, remote_path):
        """获取单个文件/目录信息。
        :param remote_path: 远程路径
        :return: 文件信息字典或 None
        """
        with self._lock:
            if not self._sftp:
                return None
            try:
                attr = self._sftp.stat(remote_path)
                return {
                    'name': os.path.basename(remote_path),
                    'size': attr.st_size,
                    'mtime': attr.st_mtime,
                    'is_dir': stat.S_ISDIR(attr.st_mode),
                    'permissions': attr.st_mode,
                }
            except Exception:
                return None

    def download_file(self, remote_path, local_path, progress_callback=None):
        """下载文件（含大小校验）。
        :param remote_path: 远程文件路径
        :param local_path: 本地保存路径
        :param progress_callback: 进度回调
        :return: (成功标志, 消息)
        """
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.get(remote_path, local_path, callback=progress_callback)
                # 传输后校验文件大小
                remote_size = self._sftp.stat(remote_path).st_size
                local_size = os.path.getsize(local_path)
                if remote_size != local_size:
                    print(
                        f"文件大小不匹配: 远程={remote_size}, 本地={local_size}")
                    return False, f"文件大小不匹配: {remote_size} vs {local_size}"
                print(f"下载完成: {os.path.basename(remote_path)}")
                return True, "下载完成"
            except Exception as e:
                print(f"下载失败 {remote_path}: {e}")
                return False, f"下载失败: {str(e)}"

    def upload_file(self, local_path, remote_path, progress_callback=None):
        """上传文件（含大小校验）。
        :param local_path: 本地文件路径
        :param remote_path: 远程保存路径
        :param progress_callback: 进度回调
        :return: (成功标志, 消息)
        """
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.put(local_path, remote_path, callback=progress_callback)
                # 传输后校验文件大小
                local_size = os.path.getsize(local_path)
                remote_size = self._sftp.stat(remote_path).st_size
                if local_size != remote_size:
                    print(
                        f"文件大小不匹配: 本地={local_size}, 远程={remote_size}")
                    return False, f"文件大小不匹配: {local_size} vs {remote_size}"
                print(f"上传完成: {os.path.basename(local_path)}")
                return True, "上传完成"
            except Exception as e:
                print(f"上传失败 {local_path}: {e}")
                return False, f"上传失败: {str(e)}"

    def delete_remote(self, remote_path):
        """删除远程文件/目录。
        :param remote_path: 远程路径
        :return: (成功标志, 消息)
        """
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                info = self.get_file_info(remote_path)
                if info is None:
                    return False, "文件不存在"
                if info['is_dir']:
                    self._rmdir_recursive(remote_path)
                else:
                    self._sftp.remove(remote_path)
                print(f"已删除: {remote_path}")
                return True, "删除成功"
            except Exception as e:
                print(f"删除失败 {remote_path}: {e}")
                return False, f"删除失败: {str(e)}"

    def create_remote_dir(self, remote_path):
        """创建远程目录。
        :param remote_path: 远程目录路径
        :return: (成功标志, 消息)
        """
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.mkdir(remote_path)
                return True, "创建成功"
            except Exception as e:
                return False, f"创建失败: {str(e)}"

    def rename_remote(self, old_path, new_path):
        """重命名远程文件。
        :param old_path: 原始路径
        :param new_path: 新路径
        :return: (成功标志, 消息)
        """
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.rename(old_path, new_path)
                return True, "重命名成功"
            except Exception as e:
                return False, f"重命名失败: {str(e)}"

    def _rmdir_recursive(self, path):
        """迭代删除目录（避免大目录栈溢出）。"""
        # 使用栈实现迭代删除
        stack = [(path, False)]
        while stack:
            current_path, should_delete = stack.pop()
            if should_delete:
                try:
                    self._sftp.rmdir(current_path)
                except Exception as e:
                    print(f"删除目录失败 {current_path}: {e}")
                continue

            # 先处理子项，再删除当前目录
            stack.append((current_path, True))
            try:
                for item in self._sftp.listdir_attr(current_path):
                    item_path = current_path + '/' + item.filename
                    if stat.S_ISDIR(item.st_mode):
                        stack.append((item_path, False))
                    else:
                        try:
                            self._sftp.remove(item_path)
                        except Exception as e:
                            print(f"删除文件失败 {item_path}: {e}")
            except Exception as e:
                print(f"列举目录失败 {current_path}: {e}")

    # ========== 系统状态 ==========

    @staticmethod
    def _parse_kv_lines(text):
        """解析 KEY:VALUE 行输出。
        :param text: 原始文本
        :return: [(key, value), ...] 键值对列表
        """
        pairs = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if ':' not in line:
                continue
            key, _, val = line.partition(':')
            pairs.append((key.strip(), val.strip()))
        return pairs

    def get_system_status(self):
        """获取树莓派系统状态（合并为 1 次 SSH 往返，大幅优化响应时间）。
        :return: 系统状态字典
        """
        status = {
            'hostname': self._host,
            'cpu_percent': 0.0, 'cpu_temp': 0.0,
            'memory_total': 0, 'memory_used': 0, 'memory_percent': 0.0,
            'disk_total': 0, 'disk_used': 0, 'disk_percent': 0.0,
            'uptime': '', 'load_avg': '', 'os_version': '', 'kernel': '',
            'error': '',
        }

        # 一次 SSH 调用获取所有数据，每行一个字段
        script = (
            "echo CPU_TEMP:$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0);"
            "echo CPU_PCT:$(top -bn2 -d 0.3 | grep '%Cpu' | tail -1 | sed 's/,/ /g' | awk '{p=0;for(i=1;i<=NF;i++){if($i~/^id$/){print 100-p;exit};p=$i}}');"
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
                if key == 'CPU_TEMP':
                    status['cpu_temp'] = float(val) / 1000.0
                elif key == 'CPU_PCT':
                    status['cpu_percent'] = float(val)
                elif key == 'MEM':
                    parts = val.split()
                    if len(parts) >= 2:
                        status['memory_total'] = int(parts[0])
                        status['memory_used'] = int(parts[1])
                        status['memory_percent'] = (int(parts[1]) / int(parts[0]) * 100) if int(parts[0]) > 0 else 0
                elif key == 'DISK':
                    parts = val.split()
                    if len(parts) >= 3:
                        status['disk_total'] = int(parts[0].replace('M', ''))
                        status['disk_used'] = int(parts[1].replace('M', ''))
                        status['disk_percent'] = float(parts[2])
                elif key == 'UPTIME':
                    status['uptime'] = val
                elif key == 'LOAD':
                    status['load_avg'] = val
                elif key == 'OS':
                    status['os_version'] = val
                elif key == 'KERNEL':
                    status['kernel'] = val
            except (ValueError, IndexError):
                pass

        return status

    def get_sidebar_stats(self):
        """获取侧边栏精简状态（1 次 SSH 往返）。
        :return: 精简状态字典
        """
        script = (
            "echo CPU_PCT:$(top -bn2 -d 0.3 | grep '%Cpu' | tail -1 | sed 's/,/ /g' | awk '{p=0;for(i=1;i<=NF;i++){if($i~/^id$/){print 100-p;exit};p=$i}}');"
            "echo MEM:$(free -m | grep Mem | awk '{print $2,$3}');"
            "echo IP:$(hostname -I 2>/dev/null | awk '{print $1}');"
            "echo TEMP:$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)"
        )
        code, out, err = self.exec_command(script, timeout=10)
        result = {'cpu': 0.0, 'mem_total': 0, 'mem_used': 0, 'mem_pct': 0.0,
                   'ip': '--', 'temp': 0.0}

        if code != 0 or not out.strip():
            return result

        for key, val in self._parse_kv_lines(out):
            try:
                if key == 'CPU_PCT':
                    result['cpu'] = float(val)
                elif key == 'MEM':
                    parts = val.split()
                    if len(parts) >= 2:
                        result['mem_total'] = int(parts[0])
                        result['mem_used'] = int(parts[1])
                        result['mem_pct'] = (int(parts[1]) / int(parts[0]) * 100) if int(parts[0]) > 0 else 0
                elif key == 'IP':
                    result['ip'] = val if val else '--'
                elif key == 'TEMP':
                    result['temp'] = float(val) / 1000.0
            except (ValueError, IndexError):
                pass

        return result

    def test_connection(self):
        """测试连接是否存活。"""
        if not self._connected:
            return False
        try:
            code, _, _ = self.exec_command('echo "alive"', timeout=5)
            return code == 0
        except Exception:
            return False
