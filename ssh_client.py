"""
PiManager SSH 客户端 - 基于 paramiko 的轻量 SSH 管理
支持密钥认证、命令执行、SFTP 文件传输
"""
import threading
import time
import os
import stat
from typing import Callable, Optional
import paramiko


class SSHClient:
    """SSH 连接管理器"""

    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._connected = False
        self._host = ""
        self._port = 22
        self._shell: Optional[paramiko.Channel] = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def host(self) -> str:
        return self._host

    def connect(self, host: str, port: int = 22, username: str = "pi",
                key_path: str = None, password: str = None,
                timeout: int = 10) -> tuple[bool, str]:
        """建立SSH连接"""
        with self._lock:
            if self._connected:
                self.disconnect()

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
                return True, "连接成功"

            except paramiko.AuthenticationException:
                return False, "认证失败：密钥或密码错误"
            except paramiko.SSHException as e:
                return False, f"SSH错误: {str(e)}"
            except Exception as e:
                return False, f"连接失败: {str(e)}"

    def disconnect(self) -> None:
        """断开连接"""
        with self._lock:
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

    def exec_command(self, command: str, timeout: int = 30) -> tuple[int, str, str]:
        """执行远程命令，返回 (exit_code, stdout, stderr)"""
        with self._lock:
            if not self._connected or not self._client:
                return -1, "", "未连接"

            try:
                stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
                exit_code = stdout.channel.recv_exit_status()
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                return exit_code, out, err
            except Exception as e:
                return -1, "", str(e)

    # ========== 文件操作 ==========

    def list_dir(self, remote_path: str) -> list[dict]:
        """列出远程目录"""
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
                return items
            except Exception:
                return []

    def get_file_info(self, remote_path: str) -> Optional[dict]:
        """获取单个文件/目录信息"""
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
        """下载文件"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.get(remote_path, local_path, callback=progress_callback)
                return True, "下载完成"
            except Exception as e:
                return False, f"下载失败: {str(e)}"

    def upload_file(self, local_path: str, remote_path: str,
                    progress_callback: Callable = None) -> tuple[bool, str]:
        """上传文件"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.put(local_path, remote_path, callback=progress_callback)
                return True, "上传完成"
            except Exception as e:
                return False, f"上传失败: {str(e)}"

    def delete_remote(self, remote_path: str) -> tuple[bool, str]:
        """删除远程文件/目录"""
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
                return True, "删除成功"
            except Exception as e:
                return False, f"删除失败: {str(e)}"

    def create_remote_dir(self, remote_path: str) -> tuple[bool, str]:
        """创建远程目录"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.mkdir(remote_path)
                return True, "创建成功"
            except Exception as e:
                return False, f"创建失败: {str(e)}"

    def rename_remote(self, old_path: str, new_path: str) -> tuple[bool, str]:
        """重命名远程文件"""
        with self._lock:
            if not self._sftp:
                return False, "未连接"
            try:
                self._sftp.rename(old_path, new_path)
                return True, "重命名成功"
            except Exception as e:
                return False, f"重命名失败: {str(e)}"

    def _rmdir_recursive(self, path: str) -> None:
        """递归删除目录"""
        for item in self._sftp.listdir_attr(path):
            item_path = f"{path}/{item.filename}"
            if stat.S_ISDIR(item.st_mode):
                self._rmdir_recursive(item_path)
            else:
                self._sftp.remove(item_path)
        self._sftp.rmdir(path)

    # ========== 系统状态 ==========

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
            "echo CPU_PCT:$(top -bn1 | grep 'CPU' | head -1 | awk '{print $2+$4}');"
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

        for line in out.strip().split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            val = val.strip()
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
            "echo CPU_PCT:$(top -bn1 | grep 'CPU' | head -1 | awk '{print $2+$4}');"
            "echo MEM:$(free -m | grep Mem | awk '{print $2,$3}');"
            "echo IP:$(hostname -I 2>/dev/null | awk '{print $1}');"
            "echo TEMP:$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)"
        )
        code, out, err = self.exec_command(script, timeout=10)
        result = {"cpu": 0.0, "mem_total": 0, "mem_used": 0, "mem_pct": 0.0,
                   "ip": "--", "temp": 0.0}

        if code != 0 or not out.strip():
            return result

        for line in out.strip().split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            val = val.strip()
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
        """测试连接是否存活"""
        if not self._connected:
            return False
        try:
            code, _, _ = self.exec_command("echo 'alive'", timeout=5)
            return code == 0
        except Exception:
            return False
