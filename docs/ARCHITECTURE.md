# PiManager v2 技术架构文档

## 1. 项目概述

### 1.1 项目目标和定位

PiManager v2 是一个轻量级树莓派桌面管理工具，专为树莓派 Zero W 等低资源设备设计。它运行在 Windows 桌面端，通过 SSH 远程管理树莓派的系统状态监控、文件传输、命令终端和配置管理。

核心定位：

- **桌面客户端**：Windows tkinter GUI 应用，非 Web 前端，非树莓派上运行
- **SSH 驱动**：所有远程操作通过 Paramiko SSH/SFTP 实现，无 Agent 依赖
- **Pillow 自绘 UI**：放弃 CustomTkinter，自建 pillui 组件库，用 Pillow 图层合成实现所有 UI 组件
- **深色/浅色双主题**：颜色令牌系统支持一键主题切换，Dark 风格为默认

### 1.2 技术栈总览

| 层次 | 技术 | 用途 |
|------|------|------|
| GUI 框架 | tkinter | 窗口管理、事件循环、原生控件 |
| 图像渲染 | Pillow (PIL) 14.0+ | 所有 UI 组件像素级绘制 + 图层合成 |
| 图像显示 | PIL.ImageTk.PhotoImage | Pillow Image → tk.Canvas 可显示格式 |
| SSH 通信 | Paramiko 3.0+ | SSH 连接、SFTP 文件传输、命令执行 |
| 并发模型 | threading.Thread | 后台 SSH I/O，避免阻塞 GUI 主线程 |
| 配置存储 | JSON 文件 | 项目根目录 `pimanager.json` |
| 测试框架 | unittest | Python 标准库测试框架 |
| 依赖 | 仅 2 个外部库 | paramiko + Pillow |

### 1.3 版本信息

- 版本：`v2.0.0`
- 配置版本：`CONFIG_VERSION = 2`
- 兼容性：Windows 10/11，Python 3.10+
- 入口：`main.py` → `PiManagerApp` → `mainloop()`

---

## 2. 系统架构

### 2.1 分层架构图

```
+====================================================================+
|                        PiManagerApp (tk.Tk)                        |
|  窗口骨架 · 页面路由 · 连接生命周期 · 全局事件调度                    |
+====================================================================+
|                                                                    |
|  +------------------+  +------------------+  +------------------+  |
|  |   StatusPanel    |  |   FileBrowser    |  |  TerminalPage    |  |
|  |   (状态监控页)    |  |   (文件管理页)    |  |  (命令终端页)    |  |
|  |   全 PillUI 渲染  |  |   原生 Canvas    |  |   原生 Canvas    |  |
|  +------------------+  +--+------------+--+  +------------------+  |
|                           |  双栏模式   |                          |
|                           | 远程+本地    |                          |
|                           +------------+                           |
|  +--------------------------------------------------------------+  |
|  |                    SettingsPage (设置页)                       |  |
|  |                    全 PillUI 渲染 + tk.Toplevel 对话框          |  |
|  +--------------------------------------------------------------+  |
|                                                                    |
+====================================================================+
|                                                                    |
|  +--------------------------------------------------------------+  |
|  |                  PillUI 组件库 (pillui/)                       |  |
|  |  PageCanvas · BaseComponent · Button · Label · Card           |  |
|  |  ProgressBar · Slider · CheckBox · OptionMenu · ScrollFrame   |  |
|  |  renderer (字体/图层/颜色) · _draw_utils (圆角/文字)            |  |
|  +--------------------------------------------------------------+  |
|                                                                    |
+====================================================================+
|                                                                    |
|  +------------------+  +------------------+  +------------------+  |
|  |   ThemeColors    |  |     Config       |  |    SSHClient     |  |
|  |   颜色令牌系统     |  |   配置版本迁移    |  |   SSH 连接管理    |  |
|  |   深色/浅色 双主题 |  |   备份恢复验证    |  |   流式命令执行    |  |
|  +------------------+  +------------------+  +------------------+  |
|                                                                    |
+====================================================================+
|                                                                    |
|  +--------------------------------------------------------------+  |
|  |              BackgroundManager (单例背景管理器)                 |  |
|  |    图片加载 · 暗色混合 · 尺寸缓存 · Canvas 注册分发             |  |
|  +--------------------------------------------------------------+  |
|                                                                    |
+====================================================================+
```

### 2.2 各层职责说明

**应用层** (`app.py`)

PiManagerApp 继承 `tk.Tk`，是应用的根窗口。职责：
- 窗口创建 (1100x700)，侧边栏 (240px 固定宽度) + 内容区弹性布局
- 四个功能页面的实例化和路由 (`_show_page`)
- SSH 连接/断开生命周期管理（自动连接、手动切换）
- 侧边栏系统状态定时刷新 (3s 间隔)
- 状态栏时钟更新 (30s 间隔)
- 主题切换时全局 Canvas 刷新协调
- 应用退出资源清理

**页面层** (`status_panel.py`, `file_browser.py`, `terminal_page.py`, `settings_page.py`)

四个页面继承 `tk.Frame`，通过 `grid()` 在内容区切换。每个页面自治管理自己的子组件和后台线程。

**组件层** (`pillui/`)

自研 UI 组件库，8 个核心组件 + 工具模块。纯 Python/Pillow 实现，无第三方 UI 库依赖。

**服务层** (`theme.py`, `config.py`, `ssh_client.py`)

独立于 GUI 框架的可测试服务模块。`ThemeColors` 是类级别单例（所有类方法操作共享状态），`Config` 是模块级函数集合，`SSHClient` 是实例化对象。

**基础设施层** (`app.py::BackgroundManager`)

全局背景管理器，以类方法单例模式运行，管理背景图片的加载、与暗色的混合、尺寸缓存和所有已注册 Canvas 的刷新。

### 2.3 数据流图

```
用户操作 (鼠标/键盘)
    │
    ▼
PageCanvas._on_click / _on_motion / _on_mousewheel
    │
    ▼
hit_test 链 (从上层组件向下遍历)
    │
    ▼
BaseComponent.on_click / on_drag / on_mousewheel
    │
    ├──► 更新组件内部状态 (_pressed, _hovered, _value 等)
    │     │
    │     └──► parent.mark_dirty()
    │             │
    │             └──► after_idle → render()
    │                     │
    │                     ├──► 背景层 (纯色 / 背景图)
    │                     └──► 组件逐层 draw() → alpha_composite → PhotoImage → Canvas
    │
    ├──► command 回调
    │     │
    │     ├──► 触发 SSH 操作
    │     │     └──► threading.Thread → SSHClient.exec_command()
    │     │           └──► self.after(0, callback) → 更新 UI
    │     │
    │     └──► 触发页面切换 (_show_page)
    │
    └──► 触发配置保存 (SettingsPage._save_all)
          └──► config.save_config() → pimanager.json + 自动备份
```

---

## 3. PillUI 组件库设计

### 3.1 渲染管线

```
配置阶段                   渲染阶段                      显示阶段
┌──────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ BaseComponent │    │ PageCanvas.render()  │    │   tk.Canvas 显示     │
│ .draw(cw, ch) │───►│                      │───►│                      │
│  返回 RGBA    │    │ Layer 0: 背景图/纯色  │    │ ImageTk.PhotoImage   │
│  PIL Image    │    │ Layer 1: comp1.draw  │    │ (防 GC 引用持有)     │
│  (透明图层)    │    │ Layer 2: comp2.draw  │    │                      │
│               │    │ ...                  │    │ canvas.create_image  │
│ 完全离屏渲染   │    │ Image.alpha_composite│    │ (0, 0, anchor="nw")  │
│ 无 Canvas API │    │ 逐层叠加             │    │                      │
└──────────────┘    └──────────────────────┘    └──────────────────────┘
```

完整流程：

1. **组件定义**：`PillowButton("文字", x, y, w, h, command=cb)` — 存储几何信息和样式参数
2. **注册到 Canvas**：`canvas.add("comp_id", comp)` — 存入 `_components` 有序字典，设置 `comp._parent`
3. **标记脏区**：`canvas.mark_dirty()` — 防抖机制，取消前一个 `after_idle`，仅当 `_dirty=False` 时重新调度
4. **延迟渲染**：`after_idle` 触发 `render()` — tkinter 空闲时执行，避免高频重绘
5. **图层合成**：从 `_components` 字典按添加顺序遍历，调用 `comp.draw(cw, ch)` 获取 RGBA 图层，用 `Image.alpha_composite` 叠加
6. **显示**：合成后的 PIL Image 转 `ImageTk.PhotoImage`，`canvas.delete('all')` 后 `create_image` 显示

### 3.2 BaseComponent 生命周期

```
实例化 (__init__)
    │  rect=(x, y, x+w, y+h)
    │  visible=True
    │  _parent=None
    │
    ▼
注册 (canvas.add)
    │  comp._parent = canvas
    │  canvas.mark_dirty()
    │
    ▼
渲染 (draw 被 PageCanvas.render 调用)
    │  接收完整 Canvas 尺寸 (cw, ch)
    │  返回等大透明 RGBA 图层
    │  组件内容绘制在 (x, y) 偏移处
    │
    ▼
交互 (事件分发)
    │
    ├──► on_enter()    ← motion 检测进入
    ├──► on_leave()    ← motion 检测离开
    ├──► on_click()    ← Button-1 按下 + hit_test
    ├──► on_release()  ← ButtonRelease-1
    ├──► on_drag()     ← B1-Motion
    └──► on_mousewheel() ← MouseWheel + hover
    │
    ▼
状态更新
    │  comp.set_text(...) / set_color(...) / set(value) 等
    │  → 如果 self._parent: self._parent.mark_dirty()
    │
    ▼
移除 (canvas.remove)
        canvas._components.pop(comp_id)
        canvas.mark_dirty()
```

每个组件的 `draw()` 方法签名统一为 `draw(self, cw, ch)`，接收的是整个 PageCanvas 的宽高。组件在图层上根据自己的 `rect` 坐标绘制内容。所有组件绘制在同一张等大透明图层上，由 PageCanvas 统一合成。

### 3.3 PageCanvas 图层合成引擎

PageCanvas 继承 `tk.Canvas`，核心职责：

- **组件注册表**：`_components` 有序字典 (`{comp_id: BaseComponent}`)，渲染时按插入顺序遍历
- **脏标记防抖**：`mark_dirty()` 使用 `after_idle` 延迟到 tkinter 空闲时渲染，高频调用只触发一次
- **事件分发**：统一的鼠标事件入口，从后往前遍历 `_components` 做 `hit_test`，命中即停
- **Hover 跟踪**：`_on_motion` 比较新旧 hover 组件，自动调用 `on_enter` / `on_leave` / `mark_dirty`
- **窗口 resize**：`_on_resize` → `after(80, mark_dirty)` 做 80ms 防抖
- **背景分离**：支持纯色 (`set_bg_color`) 和图片 (`set_bg_image`)，前者用 `Image.new` 创建，后者 resized 后作为 Layer 0

关键设计决策：

- 组件 `draw()` 返回**等大透明图层**而非局部小图，简化合成逻辑，但增加内存开销
- `Image.alpha_composite` 要求两张图尺寸完全一致，因此组件必须在等大图层上绘制
- 字体缩放因子存储于 `_font_scale` 属性，组件绘制时通过 `get_font()` 获取缩放后的字体

### 3.4 事件分发机制

```
┌─────────────────────────────────────────────────────────────┐
│                  PageCanvas 事件绑定                          │
│                                                             │
│  <Button-1>        → _on_click     → 遍历 _components 逆序   │
│  <B1-Motion>       → _on_drag      → 转发到 _hovered 组件    │
│  <ButtonRelease-1> → _on_release   → 转发到 _hovered 组件    │
│  <Motion>          → _on_motion    → hit_test + hover 跟踪   │
│  <MouseWheel>      → _on_mousewheel → 转发到 _hovered 组件   │
│  <Configure>       → _on_resize    → 延迟 mark_dirty         │
└─────────────────────────────────────────────────────────────┘
```

**hit_test 分派策略**：

- `_on_click`：逆序遍历 `_components`（`reversed(list(self._components.keys()))`），相当于从上到下，遇到第一个 `visible and hit_test` 命中的组件即处理，返回后不再向下传递——这是"最上层吸收"模型
- `_on_motion`：同样逆序遍历，但额外维护 `_hovered` 状态，检测 enter/leave 变化并触发 `mark_dirty`（因为 hover 状态改变需要重绘）
- `_on_drag` / `_on_release` / `_on_mousewheel`：直接使用 `_hovered` 缓存的组件 ID，不重新 hit_test

**特殊 hit_test 覆盖**：

- `PillowSlider.hit_test` 在垂直方向扩展了 8px 的容错区域（`(y1 - 8)` 到 `(y2 + 8)`），方便手指/鼠标定位滑轨
- `PillowCheckBox.hit_test` 限制有效高度为 22px，不受组件 rect 高度的完整约束

### 3.5 各组件设计意图和 API

#### PillowButton — 按钮

**设计意图**：替代 tkinter Button，支持 3 种预设样式 + hover/pressed/disabled 状态切换。

**状态机**：

```
        disabled? ──yes──► fill=#555555, text=#888888, 拦截 click/release
             │no
        pressed? ──yes──► fill=hover_color
             │no
        hovered? ──yes──► fill=hover_color
             │no
        normal: fill=bg_color (transparent 时为 (0,0,0,0))
```

**预设样式**：

| 样式 | bg | hover | text | border |
|------|-----|-------|------|--------|
| `primary` | `#2B5B2B` | `#3A7A3A` | `#FFFFFF` | 无 |
| `danger` | `#8B0000` | `#A00000` | `#FFFFFF` | 无 |
| `transparent` | 透明 | `#333333` | `#C9D1D9` | `#555555` 1px |

**API**：

- `set_text(text)` — 更新按钮文字
- `set_style(style)` — 切换样式 (`"primary"` / `"danger"` / `"transparent"`)
- `set_disabled(bool)` — 启用/禁用
- `command` — 点击回调（在 `on_release` 中触发）

**交互细节**：`on_click` 设置 `_pressed=True` → mark_dirty 重绘为按下态 → `on_release` 重置 `_pressed=False` → mark_dirty → 触发 command。`on_leave` 同时清除 `_hovered` 和 `_pressed`（防止拖出按钮后释放遗漏）。

#### PillowLabel — 文本标签

**设计意图**：替代 tkinter Label，支持多行文本、三种水平对齐、两种字重、两种锚点模式。

**API**：

- `set_text(text)` — 更新文字（相同文字不触发 mark_dirty）
- `set_color(hex_color)` — 更新文字颜色
- 构造函数参数：`text`, `x`, `y`, `w`, `h`, `font_size`, `color`, `align` (`left`/`center`/`right`), `weight` (`normal`/`bold`), `anchor` (`nw`/`center`)

**多行渲染**：按 `\n` 分割，每行 `line_height = font_size + 6`，逐行 `draw.text()` 绘制。

**锚点模式**：
- `nw` (NorthWest)：`(x, y)` 为左上角，文字向右向下展开
- `center`：`(x, y)` 为中心点 → 重新计算 `x = x - w//2`, `y = y - total_h//2`

#### PillowCard — 卡片容器

**设计意图**：纯装饰组件，提供圆角矩形背景 + 可选标题。不承载子组件（子组件由 PageCanvas 独立管理，通过坐标对齐实现"视觉上在卡片内"）。

**API**：构造函数参数 `x`, `y`, `w`, `h`, `title`, `fill`, `border`, `radius`, `title_size`。

**渲染**：`draw.rounded_rectangle` 绘制圆角背景 + 1px 边框 + 左上角标题文字。

#### PillowProgressBar — 进度条

**设计意图**：水平进度条，轨道 + 填充条 + 颜色控制。用于 CPU/内存/磁盘使用率可视化。

**API**：

- `set(value)` — 设置进度 0.0~1.0（自动钳制）
- `set_color(hex_color)` — 设置填充颜色
- `value` — 只读属性，返回当前值

**渲染**：轨道固定色 `#1A1A1A`，填充段当 `fill_w > 3` 时绘制 `rounded_rectangle`。

#### PillowSlider — 水平滑块

**设计意图**：带步长的可拖拽滑块，用于设置页面的字体缩放、背景透明度、刷新间隔等数值参数。

**API**：

- 构造函数：`from_val`, `to_val`, `steps`, `variable` (tk.DoubleVar), `command` (回调函数)
- 支持拖拽 (`on_click` 开始拖拽 → `on_drag` 持续更新 → `on_release` 结束拖拽并触发 command)

**步长舍入**：`step_size = (to_val - from_val) / steps` → `round(val / step_size) * step_size`

**渲染**：轨道底线 (4px 宽) + 绿色填充段 + 椭圆滑块 (拖动时变深色 `#3A7A3A`)。

#### PillowCheckBox — 复选框

**设计意图**：带标签的复选框，绑定 `tk.BooleanVar`。

**API**：

- 构造函数：`text`, `variable` (tk.BooleanVar), `command` (选中状态改变时回调)
- `on_click` 切换 `variable` 值 → mark_dirty → 触发 command

**渲染**：16x16 圆角方块 (选中时 `#4CAF50`，未选中 `#1A1A1A`) + 白色勾号（两条短线组成） + 右侧标签文字。

#### PillowOptionMenu — 下拉选择框

**设计意图**：Pillow 绘制外观 + 原生 `tk.Menu` 做弹窗。用于主题模式、颜色主题等选择。

**API**：

- 构造函数：`values` (选项列表), `variable` (tk.StringVar), `command` (选中回调)
- `on_click` 弹出 `tk.Menu`，用户选择后调用 `_select(value)` → 更新 variable → mark_dirty → 触发 command

**设计权衡**：不自己实现下拉菜单（太复杂），而是借壳 tk.Menu。Pillow 只画选择框的外观（背景 + 当前值 + 箭头），点击时弹原生菜单。

#### PillowScrollFrame — 可滚动容器

**设计意图**：继承 PageCanvas，添加垂直滚动支持。通过坐标偏移实现滚动，不创建真正的可滚动 Canvas。

**核心机制**：

1. 重写 `render()` — 在合成前将所有组件的 y 坐标减去 `_scroll_y`
2. 用 `try/finally` 保证组件原始坐标在渲染后恢复
3. 滚轮事件更新 `_scroll_y`（步长 30px），同步更新 `tk.Scrollbar`

**限制**：当前版本中未在主要页面使用，为未来的长列表设置页预留。

### 3.6 渲染工具模块

#### renderer.py — 颜色/字体/图层

| 函数 | 功能 |
|------|------|
| `hex_to_rgba(hex, alpha)` | `"#1A2B3C"` → `(26, 43, 60, 255)` |
| `hex_to_rgb(hex)` | `"#1A2B3C"` → `(26, 43, 60)` |
| `get_font(family, size)` | 字体加载 + 多平台路径回退 + 结果缓存 |
| `create_layer(w, h)` | 创建透明 RGBA `Image` 图层 |
| `composite_layer(base, layer, x, y)` | 偏移叠加图层 |
| `center_text(draw, rect, text, fill, font)` | 矩形内居中文字 |

**字体搜索路径**：

```
Windows: C:/Windows/Fonts/{family}.ttc / .ttf
Linux:   /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc
         /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
Fallback: ImageFont.load_default()
```

字体加载后存入 `_font_cache` 字典，key 为 `(family, size)` 元组。当前项目中主要使用 `msyh` (微软雅黑) 和 `msyhbd` (微软雅黑粗体)。

#### _draw_utils.py — 圆角矩形/文字对齐

| 函数 | 功能 |
|------|------|
| `draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill, outline, width)` | 圆角矩形（封装 `draw.rounded_rectangle`） |
| `text_bbox(text, font)` | 获取文字包围盒 `(width, height)` |
| `draw_text_aligned(draw, rect, text, fill, font, align)` | 矩形内对齐文字（左/中/右） |

---

## 4. 核心服务层

### 4.1 ThemeColors: 颜色令牌系统

**设计模式**：类级别单例（所有方法 `@classmethod`，共享 `_mode` 和 `_font_scale` 类变量）。

**架构**：

```
ThemeColors
├── _mode: 'Dark' | 'Light'          ← 当前主题模式
├── _dark: dict (31 个颜色令牌)       ← 深色调色板
├── _light: dict (31 个颜色令牌)      ← 浅色调色板
├── _font_scale: float               ← 全局字体缩放因子
│
├── set_mode(mode)                   ← 设置主题
├── get_mode() → 'Dark' | 'Light'
├── toggle_mode()                    ← 切换主题
├── get(key) → hex_color             ← 获取颜色
├── fg_hover(key) → (fg, hover)      ← 获取颜色对
├── set_font_scale(scale)            ← 设置字体缩放
├── get_font_scale() → float
└── scaled_font(family, size) → (family, int(size * scale))
```

**颜色令牌分类**：

| 类别 | 令牌 | 用途 |
|------|------|------|
| 基础色 | `bg`, `bg_card`, `text`, `text_secondary` | 页面/卡片背景、主/次文字色 |
| 语义色 | `accent`, `danger`, `warning`, `status_ok` | 功能状态指示 |
| 交互态 | `accent_hover`, `danger_hover`, `btn_primary_hover` | hover/pressed 反馈 |
| 组件专用 | `btn_primary`, `btn_transparent_hover`, `scrollbar`, `terminal_prompt` | 特定组件颜色 |
| Canvas 专用 | `canvas_bg`, `canvas_text`, `canvas_selection`, `canvas_err` | 原生 Canvas 渲染色 |
| 元组色 | `card_border`, `separator`, `nav_active` | 需要 `(light_val, dark_val)` 对 |

**字体缩放**：`ThemeColors.set_font_scale(1.5)` 后，`scaled_font('msyh', 12)` 返回 `('msyh', 18)`。所有 PageCanvas 持有自己的 `_font_scale` 副本，组件通过 `get_font()` 间接使用全局缩放。

**已知 Bug**：`toggle_mode()` 两种分支都设置 `mode='dark'`，实际无法切换到浅色模式（需通过 SettingsPage 的 OptionMenu 手动切换）。测试文件中已记录此问题。

### 4.2 Config: 配置版本迁移机制

**设计模式**：模块级函数集合，无类封装。

**配置文件路径**：`{项目根}/pimanager.json`

**默认配置结构**：

```json
{
  "version": 2,
  "connections": [{ "name": "...", "host": "...", "port": 22, "username": "...", "key_path": "...", "use_key": true }],
  "appearance": { "theme": "dark", "color_theme": "green", "background_path": "", "background_opacity": 0.15, "font_scale": 1.0 },
  "behavior": { "auto_connect": false, "refresh_interval": 3, "confirm_before_delete": true, "terminal_history_size": 500 }
}
```

**版本迁移流程**：

```
load_config()
    │
    ├──► CONFIG_FILE 存在?
    │     │ yes → json.load → _migrate_and_merge()
    │     │ no  → DEFAULT_CONFIG.copy()
    │
    └──► _migrate_and_merge(config)
          │
          ├──► loaded_version = config.get('version', 1)
          │
          ├──► while loaded_version < CONFIG_VERSION:
          │       migrator = _MIGRATIONS[loaded_version]
          │       config = migrator(config)  # 执行迁移函数
          │       loaded_version += 1
          │
          ├──► merged = DEFAULT_CONFIG.copy()
          ├──► _deep_merge(merged, config)  # 用户值覆盖默认值，缺失字段补全
          └──► 返回 merged
```

**迁移规则注册表**：

```python
_MIGRATIONS = {
    1: _migrate_v1_to_v2,  # V1→V2: 添加 version 字段 + terminal_history_size
}
```

**备份机制**：

- 每次保存前自动备份到 `config_backups/pimanager_{timestamp}.json`
- 保留最近 10 个备份，旧的自动删除
- 配置损坏时自动尝试从最新备份恢复
- `restore_config(backup_path)` 支持手动恢复指定备份

**验证**：`validate_config(config)` 返回错误列表，检查端口范围 (1-65535)、透明度 (0-1)、字体缩放 (0.5-3.0)、刷新间隔 (1-60)。

### 4.3 SSHClient: 连接生命周期、流式执行、线程模型

**设计模式**：实例对象，由 `PiManagerApp._ssh` 持有，传递给所有页面。

**线程安全模型**：

```
┌──────────────────────────────────────────────────────────┐
│                     SSHClient                            │
│                                                          │
│   _lock:    threading.RLock()  ← 保护连接状态和 SFTP     │
│   _cmd_lock: threading.Lock()  ← 串行化命令执行           │
│                                                          │
│   connect / disconnect / list_dir / download / upload    │
│       → with self._lock: ...                             │
│                                                          │
│   exec_command                                           │
│       → with self._cmd_lock: ...                         │
└──────────────────────────────────────────────────────────┘
```

**连接生命周期**：

```
connect(host, port, username, key_path, password)
    │
    ├──► with _lock: 如有旧连接则 disconnect()
    │
    ├──► _do_connect()
    │     ├──► paramiko.SSHClient()
    │     ├──► 密钥认证: Ed25519Key → RSAKey 回退
    │     ├──► 密码认证: password
    │     ├──► client.connect(timeout=10, banner_timeout=10, auth_timeout=10)
    │     ├──► _sftp = client.open_sftp()
    │     └──► _connected = True
    │
    └──► 失败返回 (False, "错误消息")
         成功返回 (True, "连接成功")

disconnect()
    │
    ├──► _stop_keep_alive()
    ├──► 关闭 _shell 通道
    ├──► 关闭 _sftp 通道
    ├──► 关闭 _client 连接
    └──► _connected = False
```

**自动重连**：

```
exec_command 失败 (SSHException)
    │
    ├──► _auto_reconnect()
    │     ├──► 检查重连次数 < 3
    │     ├──► 指数退避: 1s, 2s, 4s
    │     ├──► reconnect() → 使用保存的连接参数
    │     └──► 成功 → 重试原命令一次
    │
    └──► 失败 → 返回 (-1, '', 错误消息)
```

**流式命令执行** (`exec_command_streaming`)：

```
exec_command_streaming(command, on_stdout, on_stderr, on_done, timeout)
    │
    ├──► 创建 StreamingCommand 句柄
    │
    └──► threading.Thread → _stream()
          ├──► client.exec_command(cmd, get_pty=True)
          │     PTY 模式: stdout/stderr 合并 + 行缓冲 → print() 立即送出
          │
          ├──► for line in iter(stdout.readline, ''):
          │       if cancelled: break
          │       on_stdout(line)  # 逐行回调（通过 self.after 跨线程回 GUI）
          │
          ├──► exit_code = stdout.channel.recv_exit_status()
          └──► on_done(exit_code, error)

StreamingCommand 句柄:
    ├──► .is_running → bool
    ├──► .send_ctrl_c() → 发送 \x03 (SIGINT) → 优雅终止
    └──► .cancel() → channel.close() → 硬终止
```

**系统状态获取** (合并 SSH 往返优化)：

`get_system_status()` 和 `get_sidebar_stats()` 将多次命令合并为一个 Shell 脚本，用分号连接，每条输出以 `KEY:value` 格式标记，一次 SSH 往返获取所有数据。

`get_system_status` 一次获取：CPU 温度、CPU 使用率、内存、磁盘、运行时间、负载、OS 版本、内核版本（8 个指标）。

`get_sidebar_stats` 一次获取：CPU、内存、IP、温度（4 个指标，用于侧边栏 3 秒定时刷新）。

**批量命令执行**：`exec_command_batch(commands)` 将多条命令用 `"; echo '---CMD_SPLIT---'; "` 连接，一次 SSH 调用执行，按分隔符拆分结果。

**连接保活**：`start_keep_alive(interval=30)` 使用 `threading.Timer` 定时发送 `echo "keepalive"` 探测，失败时触发自动重连。

**SFTP 文件操作**：

| 方法 | 功能 | 特性 |
|------|------|------|
| `list_dir(path, limit, offset)` | 列出目录 | 分页支持、目录优先排序 |
| `get_file_info(path)` | 获取文件信息 | SFTP stat |
| `download_file(remote, local, cb)` | 下载文件 | 进度回调 + 大小校验 |
| `upload_file(local, remote, cb)` | 上传文件 | 进度回调 + 大小校验 |
| `delete_remote(path)` | 删除文件/目录 | 迭代栈删除（防止大目录栈溢出） |
| `create_remote_dir(path)` | 创建目录 | SFTP mkdir |
| `rename_remote(old, new)` | 重命名 | SFTP rename |

---

## 5. 页面架构

### 5.1 app.py 窗口骨架

**PiManagerApp** 继承 `tk.Tk`，是应用的根窗口。布局结构：

```
PiManagerApp (tk.Tk, 1100x700, minsize 900x600)
├── grid_columnconfigure(0, weight=0)    ← 侧边栏列固定
├── grid_columnconfigure(1, weight=1)    ← 内容区弹性
├── grid_rowconfigure(0, weight=1)       ← 主区弹性
│
├── sidebar_frame (tk.Frame, width=240, grid_propagate=False)
│   └── _sidebar (PageCanvas, 240x700)
│       ├── logo (PillowLabel, 32px emoji)
│       ├── logo_text (PillowLabel, "PiManager")
│       ├── status_card + conn_status + conn_host (连接状态区)
│       ├── btn_connect + btn_settings_conn (连接操作)
│       ├── sys_card (PageCanvas卡片容器, 初始隐藏)
│       │   ├── sidebar_cpu_bar + sidebar_cpu_pct
│       │   ├── sidebar_ram_bar + sidebar_ram_pct
│       │   ├── sidebar_ip
│       │   └── sidebar_temp
│       ├── nav_buttons (4 个导航按钮)
│       ├── reboot_btn + shutdown_btn (电源操作)
│       └── version (版本标签)
│
├── content (tk.Frame)
│   └── _pages (dict: status | files | terminal | settings)
│       ├── StatusPanel   (PageCanvas, 全 PillUI)
│       ├── FileBrowser   (原生 Canvas 双栏)
│       ├── TerminalPage  (原生 Canvas 多标签)
│       └── SettingsPage  (PageCanvas, 全 PillUI)
│
└── status_bar (tk.Frame, height=28, tk.Label × 3)
    ├── _status_label     (连接状态文字)
    ├── _status_duration  (连接持续时间)
    └── _status_clock     (当前时间)
```

**BackgroundManager 单例模式**：

`BackgroundManager` 所有方法为 `@classmethod`，类级别共享状态。全局仅维护一份背景图片、混合结果、尺寸缓存和 Canvas 注册表。

**注册流程**：
- PageCanvas 页面（StatusPanel、SettingsPage、侧边栏）：在页面构造时调用 `BackgroundManager.register(canvas)`
- 原生 Canvas 页面（FileBrowser 的 `_list_container`、TerminalPage 各 Tab 的 `_canvas`）：同样在构造时注册
- 侧边栏不注册背景图（保持纯色），通过 `set_bg_color` 而非 `set_bg_image` 渲染

**刷新策略**：`_refresh()` 遍历所有已注册 Canvas，区分 PageCanvas（调用 `set_bg_image` / `set_bg_color` + `render()`）和原生 Canvas（调用 `apply_to_canvas` 直接用 tk API 创建背景图片）。

### 5.2 StatusPanel — 系统状态监控页

**组件树**：

```
StatusPanel (tk.Frame)
└── _canvas (PageCanvas)
    ├── info_card [PillowCard]  540x70, 标题"系统信息"
    │   ├── _lbl_hostname [PillowLabel] 主机名 16px bold
    │   ├── _lbl_os [PillowLabel] OS 版本 11px
    │   └── _lbl_kernel [PillowLabel] 内核版本 11px right
    ├── cpu_card [PillowCard] 265x100
    │   ├── _cpu_bar [PillowProgressBar]
    │   └── _cpu_pct [PillowLabel] 22px bold right
    ├── temp_card [PillowCard] 265x100
    │   └── _temp_label [PillowLabel] 26px bold
    ├── mem_card [PillowCard] 265x100
    │   ├── _mem_bar [PillowProgressBar]
    │   └── _mem_text [PillowLabel]
    ├── disk_card [PillowCard] 265x100
    │   ├── _disk_bar [PillowProgressBar]
    │   └── _disk_text [PillowLabel]
    ├── info2_card [PillowCard] 540x50
    │   ├── _lbl_uptime [PillowLabel] 运行时间
    │   └── _lbl_load [PillowLabel] 系统负载
    ├── _btn_refresh [PillowButton] 手动刷新
    └── _lbl_update [PillowLabel] 最后更新时间
```

**交互流程**：

1. 连接成功 → `start_auto_refresh()` → `_do_auto_refresh()` 循环 (`self.after` 每 N 秒)
2. 每次刷新：`threading.Thread` → `SSHClient.get_system_status()` (1 次 SSH 往返) → `self.after(0, _update_ui)` → 更新所有 PillowLabel/PillowProgressBar
3. 进度条颜色根据阈值动态切换：<50% 绿色，50-80% 橙色，>80% 红色
4. 断开连接 → `_show_disconnected()` → 所有组件重置为占位符

### 5.3 FileBrowser — 文件管理页（双栏模式）

**架构设计**：这是最复杂的页面，使用**原生 tk.Canvas** 而非 PillUI。原因是文件列表需要逐行虚拟滚动 + 动态选中高亮 + 文件类型颜色区分，Pillow 图层合成模型在此场景性价比低。

**组件树**：

```
FileBrowser (tk.Frame)
├── 工具栏 (tk.Frame, height=38)
│   ├── _btn_mode (单栏/双栏切换)
│   ├── _btn_to_local / _btn_to_remote (跨栏传输，双栏时显示)
│   └── 6 个操作按钮 (上传/下载/运行/新建/重命名/删除)
│
├── _list_container (tk.Frame) ← BackgroundManager 注册此容器
│   ├── _file_list [CanvasFileList, tk.Frame + tk.Canvas]
│   │   远程目录列表，使用原生 Canvas 逐行绘制
│   │     hit_test 行索引 → selected → redraw
│   │     双击目录进入，右键弹出菜单
│   └── _local_list [LocalFileList, tk.Frame + tk.Canvas]
│       本地目录列表（双栏时显示，单栏隐藏）
│         os.scandir → 线程加载 → set_items
│         双击进入子目录，右键上传
│
└── 状态栏 (tk.Frame, height=28)
    ├── _progress (ttk.Progressbar)
    └── _status_label (tk.Label)
```

**_CanvasListBase 虚拟滚动**：

```python
_row_at(y):   return (y + self._scroll_y) // 28   # 行高 28px
_redraw():    遍历 _items，仅绘制可见行 (y in [-28, canvas_height+28])
```

这是最简单的虚拟滚动实现——跳帧绘制。对于几百个文件的目录足够，不适用于数万条记录。

**双栏传输流程**：

```
单栏模式 (默认)                         双栏模式 (_mode='dual')
┌──────────────────────┐      ┌──────────────┬──────────────┐
│                      │      │   远程文件    │   本地文件    │
│   远程文件列表        │      │  CanvasFile  │  LocalFile   │
│   CanvasFileList     │      │    List      │    List      │
│                      │      │              │              │
│   右键→下载           │      │ 选中→下载到本地│ 选中→上传到RP │
│   右键→运行           │      │              │              │
│                      │      │              │              │
└──────────────────────┘      └──────────────┴──────────────┘
```

**文件传输**：`_do_transfer(direction, src, dst)` 创建工作线程，调用 `SSHClient.upload_file` 或 `download_file`，通过 `progress_callback` 更新 ttk.Progressbar。传输完成后校验文件大小。

**远程运行**：根据文件扩展名选择执行器：
- `.py` / `.py3` → `python3 {shlex.quote(path)}`
- `.sh` / `.bash` → `bash {shlex.quote(path)}`
- 其他 → `chmod +x {path} && {path}`

优先推送到 TerminalPage 标签页执行（流式输出可见），兜底使用阻塞执行 + 弹窗显示结果。

**本地文件列表** (`LocalFileList`)：使用 `os.scandir` 遍历本地目录，线程加载（`_load_token` 机制防止过期回调），目录优先排序。

### 5.4 TerminalPage — 命令终端页（多标签）

**架构设计**：也是原生 Canvas 渲染。终端输出需要逐行文本 + 颜色标签 + 虚拟滚动 + 自动滚底，Pillow 图层合成在此场景效率不足。

**组件树**：

```
TerminalPage (tk.Frame)
├── _tab_frame (tk.Frame, height=34) 标签栏
│   ├── _tab_buttons [tk.Button × N] 动态重建
│   └── "＋ 新建" 按钮
├── 快捷命令栏 (tk.Frame, height=60)
│   └── QUICK_COMMANDS [5×2 网格 tk.Button]
│       (状态/列表/磁盘/内存/温度/运行/网络/进程/Python/用户)
│
├── TerminalTab × N (tk.Frame)   ← 同一时刻仅一个 grid 显示
│   ├── _output [CanvasTerminalOutput, tk.Frame + tk.Canvas + tk.Scrollbar]
│   │     _lines: [(text, color), ...]
│   │     _scroll_y: 滚动偏移
│   │     _auto_scroll: 自动滚底标志
│   └── 输入栏 (tk.Frame, height=34)
│       ├── "$ " prompt label
│       ├── _entry [tk.Entry] + history 上下键 + Ctrl+C
│       ├── _btn_stream [tk.Button] 流式:开/关
│       └── _btn_send [tk.Button] 发送/停止
│
└── 底部工具栏 (tk.Frame, height=30)
    ├── 清屏 / 复制全部
    └── "＋ 新终端"
```

**TerminalSession 数据模型**：

```python
class TerminalSession:
    name: str           # 显示名称
    index: int          # 唯一标识
    history: deque      # 命令历史 (maxlen=500)
    history_index: int  # 当前浏览位置 (-1=最新)
```

**双模式命令执行**：

```
_execute(cmd)
    │
    ├──► stream_mode = ON  → _exec_streaming(cmd)
    │       │
    │       ├──► SSHClient.exec_command_streaming(
    │       │       cmd, on_stdout, on_stderr, on_done, timeout=120)
    │       │
    │       ├──► 返回 StreamingCommand 句柄
    │       │     ├──► 点击"停止" → send_ctrl_c() (SIGINT)
    │       │     └──► 1.5s 后未结束 → cancel() (硬关闭)
    │       │
    │       └──► 逐行回调 → self.after(0, insert_output)
    │
    └──► stream_mode = OFF → _exec_blocking(cmd)
            │
            ├──► SSHClient.exec_command(cmd, timeout=30)
            └──► 一次性返回 stdout/stderr → 逐行插入输出
```

**停止机制**：先用 `send_ctrl_c()` 发 SIGINT 尝试优雅终止（给远程进程执行 finally 块的机会），1.5 秒后如果进程仍在运行，则 `cancel()` 强制关闭 SSH channel。

**过时回调保护**：`_exec_generation` 计数器——每次执行命令递增，回调时检查 `generation` 参数是否匹配，防止前一个命令的延迟回调覆盖当前命令的 UI。

**CanvasTerminalOutput 虚拟滚动**：

- 行高 18px
- 自动滚底：新行插入时自动计算 `_scroll_y = max(0, total_h - visible_h + 20)`
- 用户手动滚轮后关闭 `_auto_scroll`
- `_redraw()` 仅绘制可见行（y 在 `[-18, canvas_height+18]` 范围内）
- 滚动条同步：`_scrollbar.set(position_start, position_end)`

### 5.5 SettingsPage — 应用设置页

**组件树**：

```
SettingsPage (tk.Frame)
└── _canvas (PageCanvas)
    ├── appearance_card [PillowCard] 540x170
    │   ├── theme_label + theme_menu [PillowOptionMenu: dark/light]
    │   ├── color_label + color_menu [PillowOptionMenu: green/blue/dark-blue]
    │   └── scale_label + scale_slider [PillowSlider: 0.8~1.5]
    │       + _scale_pct [PillowLabel]
    │
    ├── bg_card [PillowCard] 540x170
    │   ├── _bg_label [PillowLabel] 当前背景路径
    │   ├── btn_choose_bg [PillowButton] 选择图片
    │   ├── btn_clear_bg [PillowButton] 清除背景
    │   └── opacity_label + opacity_slider [PillowSlider: 0.05~0.5]
    │       + _opacity_pct [PillowLabel]
    │
    ├── behavior_card [PillowCard] 540x155
    │   ├── auto_check [PillowCheckBox] 启动时自动连接
    │   ├── refresh_label + refresh_slider [PillowSlider: 1~30秒]
    │   │   + _refresh_pct [PillowLabel]
    │   └── confirm_check [PillowCheckBox] 删除前确认
    │
    ├── about_card [PillowCard] 540x100
    │   ├── about_text [PillowLabel] 版本信息（多行）
    │   └── btn_save [PillowButton] 保存所有设置
```

**交互流程**：

- 主题切换 (`_on_theme_change`)：`ThemeColors.set_mode(theme)` → 等 200ms 重设背景 → 等 300ms 全局刷新所有 Canvas
- 字体缩放 (`_on_scale_change`)：更新 `ThemeColors.set_font_scale()` → 防抖 100ms 后 `refresh_all_canvases`
- 背景透明度 (`_on_opacity_change`)：实时更新 `BackgroundManager.set_background()`（每次拖拽都触发重绘）
- 保存 (`_save_all`)：收集所有 tkinter Variable 值 → 更新 `self._config` → `config.save_config()` → 弹出成功/失败提示

---

## 6. 渲染策略

### 6.1 双轨渲染：PillUI PageCanvas vs 原生 Canvas

项目并非全部使用 PillUI。四个页面采用了两种不同的渲染策略：

| 页面 | 渲染方式 | 理由 |
|------|----------|------|
| StatusPanel | PillUI PageCanvas | 静态卡片布局，组件数量有限 (~25个)，适合图层合成 |
| SettingsPage | PillUI PageCanvas | 静态表单布局，PillUI 组件交互丰富 (Slider/CheckBox/OptionMenu) |
| 侧边栏 | PillUI PageCanvas | 固定布局，PillUI 组件需交互状态 (hover/pressed/disabled) |
| FileBrowser | 原生 tk.Canvas | 文件列表需要逐行虚拟滚动 + 行内颜色变化 + 动态数据 |
| TerminalPage | 原生 tk.Canvas | 终端输出需要逐行文本 + 不定长行 + 颜色标签 + 高速追加 |

### 6.2 为什么文件管理和终端不用 PillUI

**文件列表的虚拟滚动需求**：

Pillow 图层合成模型下，每行文件是一个"组件"的话：
- 100 个文件 = 100 个 `BaseComponent.draw()` 调用 + 100 次 `alpha_composite`
- 每次滚动需要全量重绘所有组件
- 每个组件的 `draw()` 返回等大图层，100 个 800x600 图层 ≈ 48MB 内存

而原生 Canvas 方案：
- 仅绘制可见行 (~25 行)
- `create_text` 是轻量级 Canvas 对象，tkinter 内部管理
- 滚动时仅改变 y 偏移，不创建新对象

**终端输出的动态追加需求**：

- 终端输出是单向追加的数据流，每秒可能新增数十行
- Pillow 全量合成模型意味着每追加一行就要重新合成整个页面
- 原生 Canvas `create_text` 可以直接追加而无需重建已有内容
- 终端需要颜色标签 (`"prompt"`, `"stderr"`)——Canvas `create_text(fill=color)` 原生支持

### 6.3 BackgroundManager 背景图层合成

**合成流程**：

```
BackgroundManager.set_background(path, opacity)
    │
    ├──► path 存在?
    │     yes → Image.open(path).convert("RGBA")
    │           + Image.new("RGBA", size, (13, 17, 23, 255))  ← 暗色遮罩
    │           + Image.blend(dark, bg, opacity)              ← 混合
    │           → 存入 _blended 类变量
    │     no  → _blended = None
    │
    ├──► 清空 _tk_images, _size_cache
    └──► _refresh()
          ├──► PageCanvas: 调用 c.set_bg_image(blended) + c.render()
          └──► 原生 Canvas: 调用 apply_to_canvas(c)

apply_to_canvas(canvas):
    │
    ├──► blended.resize((canvas_width, canvas_height), LANCZOS)
    ├──► ImageTk.PhotoImage(resized) → 存 _tk_images[id(canvas)]
    ├──► canvas.delete("bg_image")
    └──► canvas.create_image(0, 0, anchor="nw", image=tk_img, tags="bg_image")
         canvas.tag_lower("bg_image")
```

**per-size 缓存**：`_size_cache` 字典 `{size_tuple: resized_PIL_Image}`，避免每次 resize 都重新采样。resize 使用 `Image.LANCZOS`（高质量重采样）。

**_tk_images 防 GC**：`ImageTk.PhotoImage` 如果没有 Python 侧引用会被垃圾回收导致图片消失，因此 `_tk_images` 字典持有所有活跃的 PhotoImage 引用（key 为 `id(canvas)`）。

---

## 7. 性能分析

### 7.1 字体缓存机制

`pillui/renderer.py::get_font()` 使用模块级 `_font_cache` 字典，key 为 `(family, size)` 元组：

```python
_font_cache = {}  # {(family, size): ImageFont}

def get_font(family, size):
    cache_key = (family, size)
    if cache_key in _font_cache:
        return _font_cache[cache_key]  # 缓存命中，无 IO
    # ... 搜索字体文件 + ImageFont.truetype() + 缓存 ...
```

每次重绘如果无缓存，每个文字组件都要 `ImageFont.truetype()` 加载字体文件，这是渲染的主要开销之一。缓存后命中率接近 100%（固定使用 msyh/msyhbd 两种字体）。

### 7.2 mark_dirty 防抖

```python
def mark_dirty(self):
    if self._idle_id is not None:
        self.after_cancel(self._idle_id)  # 取消前一个待执行的渲染
        self._idle_id = None
    if not self._dirty:
        self._dirty = True
    self._idle_id = self.after_idle(self.render)  # 推迟到空闲
```

机制分析：
- 连续多次 `mark_dirty()` 只会产生一次 `render()` 调用
- `after_idle` 意味着渲染在 tkinter 事件循环空闲时执行，不会阻塞用户交互
- `_dirty` 标志防止渲染期间的重入
- 但如果在渲染完成前又有新的 mark_dirty，会延迟到下一次 idle

### 7.3 BackgroundManager per-size 缓存

```python
_size_cache = {}  # {(width, height): resized_PIL_Image}

def get_blended(self, size=None):
    if size:
        if size not in self._size_cache:
            self._size_cache[size] = self._blended.resize(size, Image.LANCZOS)
        return self._size_cache[size]
```

背景图 resize 使用 LANCZOS（高质量但较慢），缓存避免了每次 PageCanvas 渲染或 apply_to_canvas 时重复 resize。窗口大小不变时，resize 仅发生一次。

### 7.4 Canvas 虚拟滚动

**FileBrowser 虚拟滚动**：

```python
def _redraw(self):
    y0 = -self._scroll_y
    for i, item in enumerate(self._items):
        y = y0 + i * 28
        if y < -28 or y > c.winfo_height() + 28:
            continue  # 跳过不可见行
        # ... 绘制可见行 ...
```

**TerminalPage 虚拟滚动**：

```python
def _redraw(self):
    y0 = -self._scroll_y
    for i, (text, color) in enumerate(self._lines):
        y = y0 + i * 18
        if y < -18 or y > c.winfo_height() + 18:
            continue
        # ... 绘制可见行 ...
```

两者都采用"全量遍历 + 跳过不可见行"策略。对于数百条记录足够，但如果文件量或终端输出量达到数万行，O(n) 遍历会成为瓶颈。改进方向：使用二分查找定位起始可见行索引，仅遍历可见行。

### 7.5 已知瓶颈和改进方向

| 瓶颈 | 影响 | 改进方向 |
|------|------|----------|
| 组件 draw() 返回等大图层 | 每个组件创建一个与 Canvas 等大的 RGBA Image，N 个组件 ≈ N × W × H × 4 bytes 临时内存 | 改为返回裁剪后的小图层 + 偏移量组合 |
| PageCanvas 全量重绘 | 任何组件状态变化都触发全页面合成，即使只有一个小按钮 hover 改变 | 引入脏矩形 (dirty rect) 追踪，仅重绘变化区域 |
| 文件列表全量遍历 | 1000+ 文件时，每次滚动仍遍历所有行（尽管只绘制 ~25 行） | 二分查找 + 仅遍历可见行范围 |
| 终端逐行 after(0) | 流式模式下，每行输出都通过 `self.after(0, lambda)` 跨线程，高频输出时产生大量待处理事件 | 批量合并：累积 N 行或每 100ms 批量插入 |
| 字体缩放防抖 100ms | 拖拽滑块时产生滞后感 | 降低防抖到 50ms 或仅重绘关键元素 |
| 背景 opacity 拖拽实时重绘 | 每次拖动滑块像素都触发 BackgroundManager._refresh → 所有 Canvas 重绘 | 加防抖或仅在释放时应用 |

---

## 8. 设计决策记录

### 8.1 为什么选 Pillow 而非 CustomTkinter

**背景**：PiManager v1 使用了 CustomTkinter，遇到以下问题：
- CustomTkinter 的组件外观定制受限，无法完全实现设计需求
- 主题系统与 tkinter 组件生命周期耦合，调试困难
- 部分组件在 Windows 高 DPI 下渲染异常
- 包依赖重，与树莓派跨平台目标冲突

**PillUI 方案优势**：
- 完全控制每个像素，不受系统主题/WPF 渲染器影响
- 仅依赖 Pillow（已在依赖中用于背景图处理），无额外 UI 库
- 图层合成模型天然支持透明效果和复杂视觉设计
- 组件纯 Python 实现，行为完全可预测可测试

**代价**：
- 需要手动实现完整的 UI 组件库（~1000 行代码）
- 文字渲染、字体加载、多行布局需要自行处理
- 交互状态机（hover/pressed/disabled）需逐个组件实现
- 渲染性能需要主动优化（防抖、缓存）

### 8.2 为什么不选 Web 前端 (Electron/Flask)

**考虑过的替代方案**：
1. Electron + React/Vue：完整的跨平台桌面框架
2. Flask + 浏览器：本地 Web 服务 + 浏览器作为 UI

**否决原因**：
- Electron 包体积巨大 (~150MB)，与"轻量级"定位严重冲突
- Flask + 浏览器需要管理 HTTP 服务生命周期和端口冲突
- Web 方案的 SSH 通信需要额外的 WebSocket 桥接层
- 项目目标用户是单个开发者，不需要 Web 的多用户/远程访问能力
- tkinter 是 Python 标准库，零额外安装，Windows 原生支持

### 8.3 为什么线程 SSH 而非 async

**当前模型**：`threading.Thread` + `self.after(0, callback)` 跨线程回 GUI

**考虑过 async/await + asyncio**：
- Paramiko 是同步库，不支持 asyncio
- `asyncssh` 是异步替代，但 API 不兼容、文档较少
- 项目整体不使用 asyncio（风格指南明确禁止 async/await）
- 线程模型简单直接：后台线程做 I/O，主线程做 GUI，`after(0)` 桥接

**线程安全保证**：
- `SSHClient._lock` (RLock) 保护连接状态和 SFTP 操作
- `SSHClient._cmd_lock` (Lock) 串行化命令执行
- `after(0)` 保证 GUI 更新在主线程执行（tkinter 线程安全要求）
- 流式执行使用 `_exec_generation` 计数器防过期回调

### 8.4 为什么 unittest 而非 pytest

**项目使用**：Python 标准库 `unittest`，通过 `tests/run_all.py` 的 `TestLoader.discover()` 自动发现测试。

**选择原因**：
- 风格指南规定"无 setup.py/pyproject.toml/requirements.txt"——保持零配置
- unittest 是 Python 标准库，不需要额外安装
- 测试覆盖：BackgroundManager（单例行为、Canvas 注册、背景设置）、Config（深度合并、验证、备份恢复）、SSHClient（状态、解析、重连）、ThemeColors（切换、令牌、缩放）、PillUI 组件（状态机、交互、boundary cases）
- 测试运行：`python -m tests.run_all` 或 `python tests/run_all.py`

**测试特点**：
- PillUI 测试使用 `setUpModule` 创建隐藏 `tk.Tk()` 根窗口（tkinter Variable 需要）
- SSH 测试全部 mock Paramiko，不依赖真实网络
- Config 测试使用 `tempfile.TemporaryDirectory` 隔离文件系统
- BackgroundManager 测试每个 case 重置类级别状态

---

---

## 9. v2.1.0 更新记录

v2.1.0 是一个稳定性与功能增强版本，共修复 37 个 bug，涵盖主题系统、渲染引擎和背景图片三大领域。

### 9.1 主题系统 (15 项修复)

**核心问题：亮色主题下所有组件颜色不更新。** v2.0.0 中所有 PillUI 组件使用硬编码的暗色调色板，导致切换到亮色模式后只有背景和 Canvas 原生内容变色，PillUI 组件（按钮、标签、卡片、进度条等）始终保持暗色。

**修复方案**：
- 为所有 8 个 PillUI 组件（Button、Label、Card、ProgressBar、Slider、CheckBox、OptionMenu、PageCanvas）添加 `apply_theme(theme_colors)` 方法，从 ThemeColors 动态读取颜色令牌替代硬编码值
- `PageCanvas.apply_theme()` 遍历所有注册组件并调用其 `apply_theme()`，触发全局重绘
- 修复 `toggle_mode()` 中两分支均设为 `mode='dark'` 的 bug，现在正确切换到 Light
- 颜色主题（green/blue/dark-blue）正式激活：`set_color_theme()` 修改强调色系令牌，`get_color_theme()` 返回当前主题名，SettingsPage 中 OptionMenu 选择后立即生效
- 修复启动时忽略保存的主题设置：`main.py` 现从配置读取 `appearance.theme` 和 `appearance.color_theme` 并应用
- **消除主题切换闪屏**：原方案切换→200ms延迟设背景→300ms延迟刷新全Canvas 导致闪白。改为直接调用 `refresh_all_canvases()` 同步重绘
- 设置页面添加"颜色主题"下拉菜单（green/blue/dark-blue），与"主题模式"并列

### 9.2 渲染引擎 (14 项修复)

**关键修复**：
- **文字光晕修复**：Pillow `draw.text()` 在透明 RGBA 图层上绘制文字时产生暗色小框（抗锯齿边缘与透明背景混合产生暗晕）。修复方案：先创建 `"RGB"` 不透明层绘制文字 → 将 alpha 通道从 RGB 层分离 → 合成到透明图层，彻底消除暗晕
- **`font_scale` 全局生效**：所有组件的 `draw()` 方法新增 `font_scale` 参数，PageCanvas 渲染时传入 `self._font_scale`，字体缩放滑块现在对所有文字（按钮、标签、卡片标题等）生效
- **60fps hover 渲染**：`mark_dirty()` 渲染调度从 `after_idle` 改为 `after(16ms)`，hover 状态变化不再有延迟感（~16.7ms 一帧）
- **粗体字体 tofu 修复**：`msyhbd` 字体文件不存在时回退到 `get_font('msyh', size)` 而非 `load_default()`，避免中文显示为方框
- **状态页自动刷新只在本页运行**：页面切换时 `stop_auto_refresh()` 取消定时器，切回时重新 `start_auto_refresh()`，避免后台刷新浪费 SSH 往返
- **无限重试防护**：`SSHClient._auto_reconnect()` 添加最大重试次数（3次）和指数退避（1s/2s/4s），防止连接抖动时无限循环
- **字形 bearing 居中修正**：`draw_text_aligned()` 使用 `font.getbbox()` 替代 `draw.textbbox()` 获取字形度量，修正了 bearing 导致的文字视觉偏移

### 9.3 背景图片 (8 项修复)

**关键修复**：
- **新增 4 种适配模式**：`fit_image()` 函数（`pillui/image_utils.py`）支持 cover（裁剪填充，v2.1.0 默认）、contain（完整显示，留白）、fill（拉伸填充，v2.0.0 行为）、tile（平铺）四种模式
- **设置页面适配模式选择器**：背景卡片新增 PillowOptionMenu，用户可选择 cover/contain/fill/tile
- **背景底图动态适配主题**：浅色模式下背景混合底图从固定 `(13, 17, 23)` 深色改为 `ThemeColors.get('bg')` 动态色
- **配置持久化**：新增 `appearance.background_fit_mode` 配置键（默认 `"cover"`），保存/加载/验证均已支持
- **BackgroundManager 增强**：新增 `set_fit_mode(mode)` 类方法，背景缓存 key 从 `(size,)` 扩展为 `(size, fit_mode)`，模式切换时清除缓存
- **错误弹窗**：背景图片加载失败时弹出 `messagebox.showerror` 提示用户，而非静默失败

### 9.4 v2.1.1 紧急修复
- **emoji 清除**：Pillow 无字体回退，所有 emoji 字符被替换为纯文字，消除文字豆腐块问题
- **设置页修复**：`hex_to_rgba()` 无法解析 Tkinter 颜色名 `"gray30"`，改为 hex 值 `"#4D4D4D"`

---

*文档生成日期：2026-06-19*
