"""
PiManager 配置管理 — 支持版本迁移、验证、备份恢复
"""
import json
import os
import shutil
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / 'pimanager.json'
CONFIG_BACKUP_DIR = CONFIG_DIR / 'config_backups'

# 配置版本号（用于迁移）
CONFIG_VERSION = 3

DEFAULT_CONFIG = {
    'version': CONFIG_VERSION,
    'connections': [
        {
            'name': "树莓派 Zero W",
            'host': 'raspberrypi.local',
            'port': 22,
            'username': 'pi',
            'key_path': str(Path.home() / '.ssh' / 'id_ed25519'),
            'use_key': True,
            'auto_rediscover': False,
            'last_resolved_ip': '',
        }
    ],
    'appearance': {
        'theme': 'dark',
        'color_theme': 'green',
        'background_path': '',
        'background_opacity': 0.15,
        'background_fit_mode': 'cover',
        'font_scale': 1.0,
    },
    'behavior': {
        'auto_connect': False,
        'refresh_interval': 3,
        'confirm_before_delete': True,
        'terminal_history_size': 500,
        'ip_drift_detection': True,
    }
}

# 配置迁移规则：version → 迁移函数
_MIGRATIONS = {}


def _migrate_v1_to_v2(config):
    """V1 → V2: 添加 version 字段，behavior 增加 terminal_history_size。"""
    config['version'] = 2
    if 'behavior' not in config:
        config['behavior'] = {}
    if 'terminal_history_size' not in config['behavior']:
        config['behavior']['terminal_history_size'] = 500
    return config


_MIGRATIONS[1] = _migrate_v1_to_v2


def _migrate_v2_to_v3(config):
    """V2 → V3: 添加 IP 漂移检测配置"""
    config['version'] = 3
    config.setdefault('behavior', {})
    config['behavior'].setdefault('ip_drift_detection', True)
    for conn in config.get('connections', []):
        conn.setdefault('auto_rediscover', False)
        conn.setdefault('last_resolved_ip', '')
    return config


_MIGRATIONS[2] = _migrate_v2_to_v3


def _migrate_and_merge(config):
    """对配置执行版本迁移 + 默认值合并，返回新字典。"""
    loaded_version = config.get('version', 1)
    while loaded_version < CONFIG_VERSION:
        migrator = _MIGRATIONS.get(loaded_version)
        if migrator:
            config = migrator(config)
            print(f"配置已迁移: v{loaded_version} → v{loaded_version + 1}")
        loaded_version += 1
    merged = DEFAULT_CONFIG.copy()
    _deep_merge(merged, config)
    merged['version'] = CONFIG_VERSION
    return merged


def load_config():
    """加载配置（自动迁移旧版本）。"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return _migrate_and_merge(config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"配置文件损坏: {e}，尝试恢复备份")
            # 尝试从备份恢复
            restored = _try_restore_backup()
            if restored:
                return _migrate_and_merge(restored)
            print("无可用备份，使用默认配置")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置。"""
    config['version'] = CONFIG_VERSION
    # 保存前自动备份
    if CONFIG_FILE.exists():
        backup_config()

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("配置已保存")


def validate_config(config):
    """验证配置合法性，返回错误列表。"""
    errors = []

    # 验证连接配置
    connections = config.get('connections', [])
    for i, conn in enumerate(connections):
        port = conn.get('port', 22)
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append(f"连接[{i}]端口无效: {port} (应在 1-65535 之间)")
        if not conn.get('host', '').strip():
            errors.append(f"连接[{i}]主机地址为空")

    # 验证外观配置
    appearance = config.get('appearance', {})
    opacity = appearance.get('background_opacity', 0.15)
    if not isinstance(opacity, (int, float)) or opacity < 0 or opacity > 1:
        errors.append(f"背景透明度无效: {opacity} (应在 0-1 之间)")
    fit_mode = appearance.get('background_fit_mode', 'cover')
    if fit_mode not in ('cover', 'contain', 'fill', 'tile'):
        errors.append(f"背景适配模式无效: {fit_mode} (应为 cover/contain/fill/tile)")
    font_scale = appearance.get('font_scale', 1.0)
    if not isinstance(font_scale, (int, float)) or font_scale < 0.5 or font_scale > 3.0:
        errors.append(f"字体缩放无效: {font_scale} (应在 0.5-3.0 之间)")

    # 验证行为配置
    behavior = config.get('behavior', {})
    interval = behavior.get('refresh_interval', 3)
    if not isinstance(interval, (int, float)) or interval < 1 or interval > 60:
        errors.append(f"刷新间隔无效: {interval} (应在 1-60 秒之间)")

    return errors


def backup_config():
    """备份当前配置文件，返回备份路径。"""
    if not CONFIG_FILE.exists():
        return ''
    try:
        CONFIG_BACKUP_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = CONFIG_BACKUP_DIR / f'pimanager_{ts}.json'
        shutil.copy2(CONFIG_FILE, backup_path)
        print(f"配置已备份到 {backup_path}")

        # 只保留最近 10 个备份
        backups = sorted(CONFIG_BACKUP_DIR.glob('pimanager_*.json'))
        for old in backups[:-10]:
            old.unlink()
            print(f"已删除旧备份 {old}")

        return str(backup_path)
    except Exception as e:
        print(f"备份配置失败: {e}")
        return ''


def _try_restore_backup():
    """尝试从最近的备份恢复配置。"""
    try:
        if not CONFIG_BACKUP_DIR.exists():
            return None
        backups = sorted(CONFIG_BACKUP_DIR.glob('pimanager_*.json'), reverse=True)
        for backup in backups:
            try:
                with open(backup, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"从备份恢复配置: {backup}")
                return config
            except (json.JSONDecodeError, IOError):
                continue
        return None
    except Exception:
        return None


def restore_config(backup_path=None):
    """从备份恢复配置。不指定路径则使用最新备份。"""
    try:
        if backup_path:
            src = Path(backup_path)
        else:
            backups = sorted(CONFIG_BACKUP_DIR.glob('pimanager_*.json'), reverse=True)
            if not backups:
                return False
            src = backups[0]
        shutil.copy2(src, CONFIG_FILE)
        print(f"配置已从 {src} 恢复")
        return True
    except Exception as e:
        print(f"恢复配置失败: {e}")
        return False


def get_connection(name=None):
    """获取连接配置。"""
    config = load_config()
    connections = config.get('connections', [])
    if name:
        for conn in connections:
            if conn['name'] == name:
                return conn
    return connections[0] if connections else {}


def reset_to_defaults():
    """重置为默认配置。"""
    save_config(DEFAULT_CONFIG.copy())
    return DEFAULT_CONFIG.copy()


def _deep_merge(base, override):
    """深度合并字典。"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
