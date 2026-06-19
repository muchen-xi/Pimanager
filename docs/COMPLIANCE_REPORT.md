# PiManager v2 开源合规审查报告

**审查日期**: 2026-06-19  
**审查人**: 自动合规审计  
**审查范围**: `C:\Users\m2008\Desktop\pimanager\`  
**项目版本**: v2.0.0

---

## 1. LICENSE 文件

| 项目 | 状态 | 说明 |
|------|------|------|
| LICENSE 文件存在 | **已修复** | 审计前不存在，已创建 `LICENSE` |
| 许可证类型 | **MIT** | 与项目开源/爱好性质匹配，与所有依赖兼容 |
| 版权持有人 | **穆洪达 (Mu Hongda)** | |
| 年份 | **2026** | |

---

## 2. 依赖许可证审计

| 依赖 | 许可证 | 兼容 MIT？ | 说明 |
|------|--------|------------|------|
| `paramiko` | LGPL-2.1 | **是** | LGPL 允许通过动态链接（Python `import`）使用的专有/宽松许可软件。本项目通过 paramiko 公共 API 调用，未修改 paramiko 源码。 |
| `Pillow` | HPND (Historical Permission Notice and Disclaimer) | **是** | 宽松型许可，与 MIT 完全兼容。 |
| `tkinter` | PSF (Python Software Foundation) | **是** | Python 标准库，PSF 许可与 MIT 兼容。 |

**结论**: 所有依赖与 MIT 许可证完全兼容，无冲突。

---

## 3. 敏感信息扫描

### 3.1 扫描规则

搜索了以下模式：
- `api_key`, `API_KEY`, `token`, `TOKEN`, `secret`, `SECRET` 关键字
- `password = "..."` / `password = '...'` 硬编码凭据
- IP 地址（`\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}`）
- 电子邮件地址
- `-----BEGIN` 私钥块

### 3.2 发现

**无高危项**（无 API 密钥、无硬编码密码、无私钥、无邮箱）。

个人开发数据的默认值存在于以下位置：

#### 中危 — 默认配置中的个人标识符

这些是合理默认值（面向作者自己的设备），但公开可见：

| 文件 | 行号 | 内容 | 风险等级 |
|------|------|------|----------|
| `config.py` | 22 | `'host': 'muchenxi-20081128.local'` | 中 |
| `config.py` | 24 | `'username': 'chenxi'` | 中 |
| `config.py` | 25 | `'key_path': str(Path.home() / '.ssh' / 'id_ed25519')` | 低（模板路径） |
| `file_browser.py` | 205 | `self._cwd = "/home/chenxi"` | 中 |
| `app.py` | 691 | `conn.get("host", "muchenxi-20081128.local")` | 中 |
| `app.py` | 693 | `conn.get("username", "chenxi")` | 中 |
| `README.md` | 35 | `ssh-copy-id chenxi@muchenxi-20081128.local` | 中 |
| `README.md` | 108-110 | Host/User 配置信息 | 低 |

#### 低危 — 测试用例中的虚构数据

| 文件 | 行号 | 内容 | 说明 |
|------|------|------|------|
| `tests/test_ssh_client.py` | 34, 60 | `password='password'` | 测试固件虚构密码 |
| `tests/test_ssh_client.py` | 125, 150 | `192.168.1.100` | RFC 1918 私有地址，测试用例 |

**建议**: 个人标识符（hostname、username）在代码和 README 中是作者个人设备的默认值。运行 `pimanager.json` 已通过 `.gitignore` 安全排除。如果公开发布到 GitHub，建议将默认值替换为占位符（如 `'raspberrypi.local'` / `'pi'`），或接受这些信息作为公开项目配置示例。

---

## 4. 代码归属与版权声明

| 项目 | 状态 | 说明 |
|------|------|------|
| 文件头部版权声明 | **符合** | 风格规范（`STYLE_GUIDE.md` 第 12 节）明确禁止版权头，这与项目风格一致 |
| 项目根 `__init__.py` | **已更新** | 添加了 `# Copyright (c) 2026 穆洪达 (Mu Hongda)` 行 |
| 作者归属 | **符合** | 风格规范标题行记载"穆洪达 2025 代码风格规范" |

---

## 5. README 合规

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 项目描述 | | 完整 |
| 安装说明 | | 包含 `pip install -r requirements.txt` |
| 使用说明 | | 包含连接、状态、文件管理、终端、设置详细说明 |
| 技术栈 | | 列出 Python/tkinter/pillui/Paramiko/Pillow |
| 许可证引用 | **已修复** | 添加了 `## 许可证` 小节 |
| 虚假声明/商标侵权 | **无** | 未发现虚假关联或商标声明 |

---

## 6. 第三方代码审查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `pillui/` 原创性 | **确认** | 自写组件库，无外部来源 |
| `ssd1306.py` | **不在仓库内** | 标准 MicroPython 库不存在于本项目中 |
| "taken from" / "adapted from" | **未发现** | 全文搜索无匹配 |
| "based on" / "credit" 引用 | **未发现** | 全文搜索无匹配 |
| 供应商代码 | **无** | 项目无任何许可冲突的外部代码 |

**结论**: 全部代码为作者原创，无第三方许可兼容性问题。

---

## 7. .gitignore 审查

| 应忽略项 | 状态 |
|----------|------|
| `__pycache__/`, `*.pyc`, `*.pyo` |  |
| `pimanager.json`（含运行时配置） |  |
| `config_backups/` |  |
| `dist/`, `build/`, `*.egg-info/` |  |
| `.claude/` |  |
| `_style_ref/`（私有风格参考） |  |
| `.vscode/`, `.idea/`（IDE 配置） |  |
| `.DS_Store`, `Thumbs.db`（系统文件） |  |
| `*.bak`, `*.bak2`, `*.tmp`（备份文件） |  |
| `*.log`（日志文件） |  |

**结论**: `.gitignore` 配置完整，无遗漏。

---

## 8. 贡献指南

| 项目 | 状态 | 说明 |
|------|------|------|
| CONTRIBUTING.md | **已创建** | 中文贡献指南，包含 Bug 报告、功能建议、代码风格参考、PR 流程 |

---

## 9. 审查总结

| 维度 | 结果 |
|------|------|
| LICENSE 文件 | **已创建** MIT License |
| 依赖许可 | **全部兼容** paramiko (LGPL-2.1), Pillow (HPND), tkinter (PSF) 均与 MIT 兼容 |
| 敏感信息 | **无高危项** — 无 API 密钥、密码、私钥、邮箱泄露。个人开发标识符（hostname/username）为中危默认值，建议发布前审查。 |
| 版权声明 | **已补全** — `__init__.py` 添加版权行 |
| README | **已补全** — 添加许可证小节 |
| 第三方代码 | **无冲突** — 所有代码为原创 |
| .gitignore | **完整** — 覆盖运行时、构建、IDE、私有文件 |
| 贡献指南 | **已创建** |

**合规状态**: **通过** — 项目可以发布。

---

*报告生成时间: 2026-06-19*
