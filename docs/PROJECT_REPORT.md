# PiManager v2.2 开发历程报告

> 作者：晨曦 (Chenxi) | 2026-06-19 | 技术栈：Python 3.9+ / tkinter / Pillow / Paramiko

---

## 1. 项目概述

### 1.1 定位与背景

PiManager v2 是一个运行在 Windows 桌面的树莓派 SSH 管理工具。它通过 Paramiko SSH/SFTP 远程管理树莓派 Zero W 的系统监控、文件传输、命令终端和配置——所有远程操作无需在树莓派上安装任何 Agent。

定位可以概括为"树莓派的桌面遥控器"：你在 Windows 本机打开 PiManager，左侧导航选功能，所有交互通过 SSH 完成。不是 Web 面板，不是 VNC，就是一本机原生桌面窗口。

### 1.2 目标用户

自己。这是个人工具项目，主要场景是开发过程中的树莓派 Zero W 远程管理——查状态、传文件、跑脚本。但项目按开源标准完善了文档体系和许可证（MIT），可供其他树莓派用户直接使用。

### 1.3 技术栈一览

| 层次 | 技术 | 作用 |
|------|------|------|
| 窗口框架 | tkinter | 原生窗口、事件循环 |
| UI 渲染 | Pillow (PIL) 14.0+ | 像素级组件绘制、图层合成 |
| 图像显示 | PIL.ImageTk.PhotoImage | PIL Image → Canvas 可显示格式 |
| SSH 通信 | Paramiko 3.0+ | SSH 连接、SFTP 传输、命令执行 |
| 并发模型 | threading.Thread | 后台 I/O，避免阻塞 GUI |
| 配置存储 | JSON | `pimanager.json`，自动版本迁移 |
| 测试框架 | unittest | Python 标准库，零额外依赖 |

仅依赖 2 个外部库：`paramiko` + `Pillow`。其余全部来自 Python 标准库。

### 1.4 版本演进

```
v1.0  (未发布)     CustomTkinter 组件库 + tkinter
       ↓          问题：组件外观受限、主题耦合、部分组件高DPI异常
v2.0  (内部)      自建 pillui 组件库替代 CustomTkinter
       ↓          纯 Pillow Canvas 渲染，图层合成模型
v2.1  (稳定)      37 个 bug 修复 + 双主题正式可用 + 4种背景适配模式
       ↓
v2.1.1-2.1.2     紧急修复：emoji tofu、hex_to_rgba 崩溃、create_text_layer 全画布覆盖
       ↓
v2.2.0            新功能：IP 漂移自动修复 (socket.getaddrinfo + 指数退避)
       ↓
v2.2.1            修复：_original_hostname 被 IP 覆盖、Keep-alive 未启动、背景位置感知裁剪
       ↓
v2.2.2 (开源)     MIT License、移除个人配置、README 更新、合规审查
```

---

## 2. 技术路线选择

每个选择都有具体的 WHY，而非"习惯"。

### 2.1 为什么不用 Electron / Web 前端？

考虑过三个方案：
1. **Electron + React**：包体积 ~150MB（Chromium 运行时），与"轻量级"定位严重冲突。树莓派 Zero W 的桌面管理工具本身才几 MB，附一个 150MB 的运行时不合理。
2. **Flask + 浏览器**：需要管理 HTTP 服务生命周期、端口冲突、WebSocket 桥接层（SSH 数据需从 Python 进程 push 到浏览器）。多了一层中间转换，增加了调试复杂度。
3. **tkinter + Pillow**：Python 标准库自带窗口框架，零额外安装。Windows 原生支持，不依赖外部渲染引擎。

选择 tkinter 的根本原因是：**本项目是单用户本地桌面工具，不需要 Web 的任何优势（远程访问、多用户、响应式布局），但 Web 的所有劣势（包体积、服务管理、跨进程通信）一个不少**。

### 2.2 为什么选 tkinter 作窗口层？

tkinter 是 Python 标准库的一部分，任何安装了 Python 的 Windows 机器都可以直接运行。它提供：
- 原生窗口管理（标题栏、resize、最小化）
- 事件循环（`mainloop()`）
- Canvas 组件（像素级渲染的画布）
- `after()` 定时器（延迟调度、防抖）

不好的一面：tkinter 的原生控件外观陈旧，在 Windows 上调用的是 Win32 经典控件，无法实现现代 UI 风格。这就是 pillui 存在的理由——**用 tkinter 拿窗口和事件循环，用 Pillow 拿像素渲染，两者各取所长**。

### 2.3 为什么 Pillow 而不是 pygame / cairo？

| 候选 | 优势 | 否决原因 |
|------|------|----------|
| pygame | 完整的 2D 游戏引擎，硬件加速 | 依赖重（SDL2），需要事件循环接管，API 面向游戏而非 UI |
| cairo | 矢量图形库，高质量抗锯齿 | C 库绑定，Windows 安装不便，文字渲染需额外 pango 支持 |
| Pillow | 纯 Python 图像处理，已在依赖中 | 无硬件加速，但 1100x700 纯 CPU 渲染完全够用 |

Pillow 的关键优势是 `Image.alpha_composite()` —— RGBA 图层合成。这直接启发了 pillui 的渲染模型：**每个 UI 组件返回一张透明 RGBA 图层，全部叠在一起就是完整界面**。而且 Pillow 已经在 v1 中用于背景图处理，不新增依赖。

### 2.4 为什么自建组件库？

现有的 Python UI 组件库选择：
- **CustomTkinter** (v1 使用)：组件外观定制度有限，主题系统与组件生命周期耦合，Windows 高 DPI 下部分组件渲染异常。包体积和依赖链较重
- **ttkbootstrap**：同样基于 ttk，定制范围受限于 ttk 主题引擎
- **Kivy / PyQt**：框架级依赖，改变整个应用架构

选择自建 pillui 的根本原因：**当组件渲染有 bug 时，你有完整的源代码去改，而不是等上游修复**。v2.1.0 修复的 37 个渲染 bug 中，有 15 个是主题颜色硬编码问题——如果用的是第三方库，每个都要等 PR merge。自己写的，从发现到修复平均不超过 2 小时。

代价是约 1000 行 pillui 代码（8 个组件 + 工具模块），但从 v2.1.0 之后基本稳定，此后再没出过渲染层 bug。

### 2.5 为什么 paramiko 而不是 asyncssh？

- Paramiko 是 Python SSH 的事实标准，文档和社区都成熟得多
- asyncssh 基于 asyncio，但项目的风格指南明确禁止 async/await——保持同步代码风格的一致性
- 并发模型用 `threading.Thread` + `self.after(0, callback)` 桥接回 GUI 主线程，足够简单，不需要 asyncio 的事件循环管理

线程安全通过两把锁保证：`SSHClient._lock`（RLock，保护连接状态和 SFTP）和 `SSHClient._cmd_lock`（Lock，串行化命令执行）。

### 2.6 为什么 unittest 而不是 pytest？

风格指南规定"零配置"——无 `setup.py`、`pyproject.toml`、`requirements-dev.txt`。unittest 是 Python 标准库，`python -m tests.run_all` 即可运行全部 261 个测试，不需要安装额外工具。pytest 虽然好用，但项目目标不是"最佳实践"，而是"最小依赖"。

### 2.7 为什么 MIT 协议？

MIT 是最宽松的开源协议：允许商用、闭源、修改后不公开。选择 MIT 的原因是：
- 这是一个个人工具项目，不想通过协议限制任何人的使用方式
- 项目中 `pillui` 组件库可能被其他人提取使用，MIT 不要求修改后的代码开源
- GitHub Pages 生态中 MIT 是最常见选择，用户理解成本最低

---

## 3. pillui 组件库设计

### 3.1 渲染管线

pillui 的渲染模型核心是一条流水线：

```
配置阶段                    渲染阶段                      显示阶段
BaseComponent              PageCanvas.render()           tk.Canvas
.draw(cw, ch)              Layer 0: 背景                 ImageTk.PhotoImage
  → 返回 RGBA              Layer 1: comp1.draw           (防GC引用持有)
    PIL Image              Layer 2: comp2.draw
    (透明图层)              ...                          canvas.create_image
                           Image.alpha_composite         (0, 0, anchor="nw")
                           逐层叠加
```

每一步的数据格式转换：

1. **组件定义**：`PillowButton("文字", x, y, w, h, command=cb)` —— 仅存储几何信息和样式参数，不创建任何图像对象
2. **注册到 Canvas**：`canvas.add("comp_id", comp)` —— 存入 `_components` 有序字典，设置 `comp._parent = self`
3. **标记脏区**：`canvas.mark_dirty()` —— 取消前一个 `after(16ms)` 待执行渲染，仅当 `_dirty=False` 时调度新渲染
4. **60fps 渲染**：`after(16ms)` 触发 `render()` —— ~60fps 节流，hover 反馈无延迟
5. **图层合成**：遍历 `_components` 字典（按 add 顺序），调用 `comp.draw(cw, ch)` 获取 RGBA 图层，用 `Image.alpha_composite()` 叠加。每个组件的 `draw()` 返回一张**与 PageCanvas 等大的透明 RGBA 图层**，组件内容绘制在各自的 `(x, y)` 偏移处
6. **显示**：合成后的 PIL Image → `ImageTk.PhotoImage` → `canvas.delete('all')` → `create_image(0, 0, anchor="nw")`

**为什么是 `alpha_composite` 而不是 `paste`？**

`Image.paste(layer, (x, y), layer)` 使用 layer 自身的 alpha 通道做遮罩，但它在粘贴时直接替换目标像素——不支持源图层自身的半透明叠加。`Image.alpha_composite(base, layer)` 使用标准 Porter-Duff "over" 合成算法：`result = src + dst * (1 - src_alpha)`，正确处理部分透明像素。pillui 的按钮 hover 效果、进度条圆角边缘、卡片透明边框都依赖此算法。

`alpha_composite` 的限制是两张图必须尺寸完全一致，这就是为什么组件 `draw()` 返回等大图层——简化合成逻辑，保证每次 `alpha_composite` 调用都合法。

### 3.2 BaseComponent 生命周期

```python
class BaseComponent:
    def __init__(self, x=0, y=0, w=0, h=0):
        self.rect = (x, y, x + w, y + h)   # 边界元组，唯一真实数据源
        self.visible = True
        self._parent = None                  # 所属 PageCanvas 引用

    @property
    def x(self): return self.rect[0]        # x, y, w, h 都是只读属性，从 rect 推导
    @property
    def y(self): return self.rect[1]
    @property
    def w(self): return self.rect[2] - self.rect[0]
    @property
    def h(self): return self.rect[3] - self.rect[1]
```

生命周期流程：

```
实例化(__init__)
  └─ rect 确定，_parent=None
      ↓
注册(canvas.add)
  └─ comp._parent = canvas, canvas.mark_dirty()
      ↓
渲染(render 调用 draw)
  └─ 接收等大画布尺寸(cw, ch)，返回等大透明 RGBA
      ↓
交互(事件分发)
  ├─ on_enter()  ← Motion 检测进入
  ├─ on_leave()  ← Motion 检测离开
  ├─ on_click()  ← Button-1 + hit_test
  ├─ on_release() ← ButtonRelease-1
  ├─ on_drag()   ← B1-Motion
  └─ on_mousewheel() ← MouseWheel + hover
      ↓
状态更新
  └─ comp.set_text() / set(value) 等 → parent.mark_dirty()
      ↓
移除(canvas.remove)
  └─ _components.pop(comp_id), 清 hover, mark_dirty()
```

**事件分发机制**：PageCanvas 统一处理所有 tk 原生鼠标事件，分发给组件。

```
<Button-1>    → _on_click     → 逆序遍历 _components → 第一个 hit_test 命中者处理，之后停止
<B1-Motion>   → _on_drag      → 转发到缓存的 _hovered 组件
<Motion>      → _on_motion    → hit_test + enter/leave 追踪 + mark_dirty
<MouseWheel>  → _on_mousewheel → 转发到 _hovered 组件
<Configure>   → _on_resize    → 80ms 防抖后 mark_dirty
```

关键设计：`_on_click` 采用"最上层吸收"模型——逆序遍历，命中即停，不会穿透。而 `_on_motion` 每次都要遍历所有组件来追踪 hover 状态变化（enter/leave），变化时触发 `mark_dirty()` 因为 hover 状态改变需要重绘。

### 3.3 逐个组件详解

#### PillowButton — 按钮

**设计意图**：替代 tkinter Button，支持 3 种预设样式 + hover/pressed/disabled 状态切换。

**状态机**：
```
disabled? ──yes→ fill=#555555, text=#888888, 拦截 click/release
     │no
pressed? ──yes→ fill=hover_color
     │no
hovered? ──yes→ fill=hover_color
     │no
normal: fill=bg_color (transparent时为(0,0,0,0))
```

**draw() 算法**（`pillui/button.py:42-107`）：
1. 读取 `_BUTTON_STYLES` 模块级字典（由 `apply_theme()` 动态更新）
2. 状态判断 → 确定 fill 颜色（RGBA 元组）
3. 非透明 fill → `draw.rounded_rectangle(radius=8)` 圆角背景
4. 有 border → 画 1px 圆角边框
5. 文字居中：使用 `draw.textbbox()` 获取字形包围盒，补偿 bearing 偏移
6. 透明按钮特殊处理（BUG 8 fix）：在页面背景色上绘制文字（不透光层），避免 RGBA 抗锯齿暗晕

**三种预设样式**：
| 样式 | bg | hover | text | border |
|------|-----|-------|------|--------|
| primary | 主题色 `btn_primary` | `btn_primary_hover` | `#FFFFFF` | 无 |
| danger | 主题色 `danger` | `danger_hover` | `#FFFFFF` | 无 |
| transparent | 透明 | `btn_transparent_hover` | 主题色 `text` | `card_border` |

`apply_theme()` 方法在 `pillui/button.py:109-134`：**直接修改模块级 `_BUTTON_STYLES` 字典**，从 ThemeColors 读取颜色令牌写入。这是 pillui 组件应用主题的统一模式——修改共享状态而非实例状态。

#### PillowLabel — 文本标签

**设计意图**：替代 tkinter Label，支持多行、三种水平对齐、两种字重、两种锚点。

**draw() 核心**（`pillui/label.py:38-94`）：
1. 按 `\n` 分割多行，`line_height = font_size + 6`
2. `anchor='center'` 时 x, y 重新计算为左上角
3. 每行文字：先测量 `textbbox` → 创建不透光小图层（页面背景色）→ 在上面绘字 → `paste` 到透明主图层
4. 这是"两阶段渲染"：先在 RGB 不透明层画字，再分离到透明层，彻底消除抗锯齿暗晕

**锚点模式**：
- `nw`（默认）：`(x, y)` = 左上角，文字向右向下展开
- `center`：`(x, y)` = 组件中心点 → `x = x - w//2`, `y = y - total_h//2`

`set_text()` 做了相等性检查，相同文字不触发 `mark_dirty()`，避免不必要的重绘。

#### PillowCard — 卡片容器

**设计意图**：纯装饰组件，圆角矩形背景 + 可选标题。不承载子组件——子组件由 PageCanvas 独立管理，通过坐标对齐实现"视觉上在卡片内"。这是 pillui 设计哲学的关键体现：**组件之间不嵌套，全部平铺在 PageCanvas 上，渲染顺序决定视觉层级**。

**draw()**：`draw.rounded_rectangle` 绘制圆角背景 + 1px 边框 + 左上角标题（msyhbd 粗体）。

`apply_theme()` 从 `ThemeColors.get('bg_card')` 读取填充色，从 `ThemeColors.get('card_border')` 读取边框色（border 是元组时取 `[0]` 即浅色模式值）。

#### PillowProgressBar — 进度条

水平进度条，轨道 + 填充条。CPU/内存/磁盘使用率可视化。

**渲染细节**：
- 轨道：`rounded_rectangle(radius=4, fill=track_color)`
- 填充段：`fill_w > 3` 时才绘制（防止 0% 时出现短线）
- 值 clamp 在 `[0.0, 1.0]`
- 轨道色从 `ThemeColors.get('bg_card')` 动态获取（非硬编码 `#1A1A1A`）

#### PillowSlider — 水平滑块

带离散步进的拖拽滑块。用于字体缩放、背景透明度、刷新间隔等数值设置。

**交互流程**：
1. `on_click` → `_dragging=True` → `_update_from_mouse(event.x)`
2. `on_drag` → 持续调用 `_update_from_mouse` → mark_dirty
3. `on_release` → `_dragging=False` → 最终更新 → 触发 `command(value)`

**步进逻辑**（`pillui/slider.py:122-126`）：
```python
if self.steps > 0:
    step_size = (self.to_val - self.from_val) / self.steps
    val = round(val / step_size) * step_size
```

**hit_test 扩展**：垂直方向扩展了 8px 容错区域（`y1-8` 到 `y2+8`），方便鼠标定位滑轨。

#### PillowCheckBox — 复选框

16x16 圆角方块 + 勾号（两条短线组成）+ 右侧标签文字。

**hit_test 重写**：有效高度限制为 22px，不管组件 rect 多高。方便与相邻组件留出间距。

**状态切换**：`on_click` → `variable.set(not variable.get())` → `command()`。不需要 `on_release`，点击即切换。

#### PillowOptionMenu — 下拉选择框

Pillow 绘制外观 + 原生 `tk.Menu` 弹窗。这是 pillui 唯一的"借壳"组件——不自己画弹出菜单（太复杂），而是用 Pillow 画选择框的外观，点击时弹原生 `tk.Menu`。

**设计权衡**：`tk.Menu` 使用的是系统原生菜单控件（Windows 下是 Win32 菜单），外观与 pillui 主题不完全统一。但自己实现下拉菜单需要处理弹出窗口管理、焦点、ESC 关闭、屏幕边界检测等一系列复杂逻辑，投入产出比太低。

### 3.4 主题系统

#### ThemeColors 颜色令牌表

`theme.py` 中的 `ThemeColors` 是一个**类级别单例**（所有方法都是 `@classmethod`，共享 `_mode` 和 `_color_theme` 类变量）。核心结构：

```python
class ThemeColors:
    _mode = 'Dark'          # 当前主题模式
    _color_theme = 'green'  # 颜色主题
    _font_scale = 1.0       # 字体缩放

    _dark = { 31 个颜色令牌 }   # 深色调色板
    _light = { 31 个颜色令牌 }  # 浅色调色板

    _color_accents = {        # 三套强调色覆盖表
        'green': {
            'dark':  {accent: '#4CAF50', accent_hover: '#3A7A3A', ...},
            'light': {accent: '#2DA44E', accent_hover: '#2C974B', ...}
        },
        'blue':     {...},
        'dark-blue': {...},
    }
```

**31 个颜色令牌**覆盖范围：
- **基础色**：`bg`, `bg_card`, `text`, `text_secondary` — 页面/卡片/文字
- **语义色**：`accent`, `danger`, `warning`, `status_ok` — 功能状态
- **交互态**：`accent_hover`, `danger_hover`, `btn_primary_hover` — hover 反馈
- **组件专用**：`btn_primary`, `btn_transparent_hover`, `scrollbar`, `terminal_prompt`
- **Canvas 渲染**：`canvas_bg`, `canvas_text`, `canvas_selection`, `canvas_err`, `canvas_quick_btn`, `canvas_quick_btn_hover`
- **元组色**：`card_border`, `separator`, `nav_active` — 返回 `(light_val, dark_val)` 对

#### 暗/亮双模式 + 三套强调色

`ThemeColors.get(key)` 的解析优先级：
1. 查当前颜色主题的模式覆盖值（`_color_accents[theme][mode]`）
2. 回退到当前主题模式的色板（`_dark` 或 `_light`）
3. 都不存在返回 `'#000000'`

颜色主题（green/blue/dark-blue）仅覆盖 5 个强调色令牌：`accent`, `accent_hover`, `accent_dim`, `btn_primary`, `btn_primary_hover`。其余 26 个令牌由深/浅模式决定。

#### apply_theme() 动态切换机制

主题切换的传播路径：
```
SettingsPage._on_theme_change(theme)
  → ThemeColors.set_mode(theme)          # 更新类变量 _mode
  → 等 200ms → _app._apply_background()  # 背景用新底色重新混合
  → 再等 300ms → app.refresh_all_canvases()
        → 遍历所有页面调用 refresh_theme()
            → PageCanvas.apply_theme()
                → 遍历 _components 中每个组件
                → comp.apply_theme(ThemeColors)
                    每个组件直接修改自己的模块级颜色变量
                → mark_dirty() 重绘
```

每个组件的 `apply_theme()` 是在做什么？以 Button 为例：
```python
def apply_theme(self, theme_colors):
    _BUTTON_STYLES['primary'] = {
        'bg': theme_colors.get('btn_primary'),
        'hover': theme_colors.get('btn_primary_hover'),
        'text': '#FFFFFF', 'border': None
    }
    # 同样更新 danger 和 transparent 样式
```

**直接修改模块级字典，不存储主题引用**。后续每次 `draw()` 时自动使用新值。这是"推模式"主题系统——切换时一次性推送所有颜色，运行时零开销读取。

#### color_theme 实现

`set_color_theme(name)` 仅修改 `_color_theme` 类变量。之后调用 `ThemeColors.get(key)` 时，先查 `_color_accents[name][mode]` 字典看是否有覆盖值。颜色主题的覆盖是"软覆盖"——只覆盖了 5 个令牌，其余仍由深/浅模式决定。

---

## 4. 核心功能实现

### 4.1 SSH 连接管理

**密钥认证**（`ssh_client.py:136-184`）：
```
Ed25519Key.from_private_key_file(path)
  → 失败 → RSAKey.from_private_key_file(path)
    → 失败 → password 认证（如果提供了密码）
      → 否则 → "请提供密钥或密码"
```

三个 timeout 全部显式设置：`timeout`, `banner_timeout`, `auth_timeout`，防止网络故障时长时间挂起。

**IP 漂移自动修复**（v2.2.0 新增）：

树莓派通过 DHCP 获取 IP 时，`raspberrypi.local` 的 mDNS 解析地址会变化。PiManager 检测到连接失败后，不直接用上次的 IP 重连，而是重新解析主机名：

```python
def _auto_reconnect(self):
    if self._auto_rediscover:
        resolve_from = self._original_hostname or self._host  # 始终从原始主机名解析
        resolved, _ = self._resolve_hostname(resolve_from, self._port)
        if resolved and resolved != self._host:
            actual_host = resolved  # 使用新 IP 重连
```

**关键设计：`_original_hostname`**。`connect()` 时如果传入的是主机名（非 IP），将其永久保存到 `_original_hostname`。`_host` 会随着成功连接更新为实际 IP，但 `_original_hostname` 永远不变。这样即使 `_host` 被 IP 覆盖了，漂移检测时仍然从 `_original_hostname` 重新解析——**v2.2.1 之前这个 bug 导致漂移修复只生效一次**，因为 `_resolve_hostname(resolved_ip)` 发现传入的已经是 IP 就直接返回了。

**Keep-alive 保活**：使用 `threading.Timer`（非 tkinter `after`，因为 SSHClient 是纯 Python 类，无 GUI 依赖）。连续 2 次保活失败才触发重连——容忍瞬态网络抖动，不因单次超时就误杀健康连接。

### 4.2 流式终端

**PTY 模式**（`ssh_client.py:323-327`）：
```python
stdin, stdout, stderr = self._client.exec_command(
    command, timeout=timeout, get_pty=True)
```

`get_pty=True` 分配伪终端，远程进程以为自己在真实终端里，自动切换为行缓冲——`print()` 立即送出，不再积压。副作用是 stdout 和 stderr 合并到 stdout 一个流。

**Ctrl+C 优雅终止**（两阶段策略）：
1. `handle.send_ctrl_c()` → 通过 PTY stdin 发送 `\x03`（SIGINT），远程进程可以做清理（如 Python 的 finally 块）
2. 等待 1.5 秒 → 如果进程仍未退出 → `handle.cancel()` 强制关闭 SSH channel

**过时回调防护**：`_exec_generation` 计数器，每次执行新命令递增。回调时检查 `generation` 参数是否与当前值匹配，防止前一个命令的延迟回调覆盖当前命令的 UI。

### 4.3 文件管理器

**双栏布局**（远程 + 本地）：单栏默认显示远程，点击"双栏"按钮后左右分栏。本地列表使用 `os.scandir` 加载，线程执行（`_load_token` 机制防止过期回调覆盖当前数据）。

**Canvas 虚拟滚动**（`file_browser.py::_CanvasListBase._redraw()`）：
```python
y0 = -self._scroll_y
for i, item in enumerate(self._items):
    y = y0 + i * 28        # 行高 28px
    if y < -28 or y > canvas_height + 28:
        continue            # 跳过不可见行
    # ... 绘制可见行 ...
```

**位置感知背景裁剪**（v2.2.1）：双栏模式下，两个 Canvas 并排显示同一张背景图的不同区域——先按容器尺寸适配背景图，然后逐栏裁剪出各自的区域，视觉连续无变形。

**SFTP 进度回调**：上传/下载完成后自动校验文件大小（远程 vs 本地字节数），不匹配时报错。

### 4.4 状态监控

**合并 SSH 往返**：`get_system_status()` 将 8 个监控指标合并为 1 次 SSH 调用——用一个分号连接的 Shell 脚本，每条输出以 `KEY:value` 格式标记，返回后由 `_parse_kv_lines()` 解析。

```python
script = (
    "echo CPU_TEMP:$(cat /sys/class/thermal/thermal_zone0/temp);"
    "echo CPU_PCT:$(...);"
    "echo MEM:$(free -m | grep Mem | awk '{print $2,$3}');"
    "echo DISK:$(df -BM / | tail -1 | awk '{print $2,$3,$5}');"
    "echo UPTIME:$(uptime -p 2>/dev/null || uptime);"
    "echo LOAD:$(...);"
    "echo OS:$(...);"
    "echo KERNEL:$(uname -r)"
)
```

侧边栏用更精简的 `get_sidebar_stats()`（4 个指标），每 3 秒刷新一次。**页面切换时自动暂停**——离开状态页时 `stop_auto_refresh()`，切回时 `start_auto_refresh()`。避免在其他页面工作时空耗 SSH 往返。

---

## 5. 踩坑实录

每个 bug 都按"症状 → 根因 → 修复"的格式记录。

### Bug 1: emoji tofu — 文字周围出现小框（v2.1.1）

**症状**：按钮、标签文字旁边出现空白小方框。

**根因**：Pillow 没有字体回退机制。当文本中含有 emoji 字符（如 🚀、📊 等），`draw.text()` 在当前字体中找不到对应字形，Pillow 渲染为 `.notdef` 字符——显示为空心方框（豆腐块/tofu）。

**修复**：清除全部 38 个 emoji 字符，全部替换为纯文字描述。

### Bug 2: 字体 .ttc index — 粗体显示为方框（v2.1.0）

**症状**：`msyhbd`（微软雅黑粗体）字体渲染后全部中文显示为方框。

**根因**：`msyhbd.ttc` 文件不存在，`msyh.ttc` 存在但包含多个字体 face（index 0 是常规体，index 1 是粗体）。v2.0 的 `get_font()` 回退逻辑是 `get_font('msyhbd', size) → FileNotFound → load_default()`，默认字体没有中文字形。

**修复**（`pillui/renderer.py:56-59`）：
```python
if family.endswith('bd') or family.endswith('bold'):
    base_family = family.replace('bd', '').replace('bold', '')
    filenames = ['%s.ttc' % base_family, '%s.ttf' % base_family,
                 '%s.ttc' % family, '%s.ttf' % family]
```
找到 `msyh.ttc` 后用 `ImageFont.truetype(path, size, index=1)` 加载粗体 face。

### Bug 3: RGBA 透明层抗锯齿暗晕（v2.0→v2.1.0）

**症状**：亮色主题下，所有文字周围出现明显的暗色小方框/阴影。

**根因**：`draw.text()` 在完全透明的 RGBA 图层上绘制文字时，抗锯齿算法在字形边缘产生半透明像素。这些像素的 RGB 值是文字色（如深灰色），alpha 是过渡值。当这个图层通过 `alpha_composite` 叠加到浅色背景上时，半透明深色像素与浅色背景混合，产生暗色光晕。

**修复**：**两阶段文字渲染**。
1. 创建一个不透光小图层（`create_text_layer(tw+N, th+N, page_bg_color)`——背景色等于页面背景色）
2. 在这个不透光层上绘制文字（抗锯齿边缘与背景色混合，不产生暗晕）
3. 将这个小图层 `paste`（使用自身 alpha 作为遮罩）到透明主图层

这是 pillui 文字渲染的核心机制，适用于所有文字组件。

### Bug 4: hex_to_rgba('gray30') 崩溃（v2.1.1）

**症状**：设置页完全无法渲染，PillowCard 构造时报错。

**根因**：`PillowCard` 的 `border` 参数传入了 Tkinter 颜色名 `"gray30"`。`hex_to_rgba()` 函数只处理 `#` 开头的 hex 字符串，`"gray30"` 没有 `#` 前缀，`lstrip('#')` 后还是 `"gray30"`，`int("gray30"[0:2], 16)` 抛出 `ValueError`。

**修复**：将 `border="gray30"` 改为 `border="#4D4D4D"`（`gray30` 的实际 hex 值）。

### Bug 5: create_text_layer 全画布覆盖（v2.1.2）

**症状**：设置页只能看到最后一张卡片，前面三张卡片完全不可见。

**根因**：`PillowCard` 和 `PillowOptionMenu` 的 `draw()` 方法调用了 `create_text_layer(cw, ch, ...)` 创建全画布不透光 RGBA 层（`Image.new('RGBA', (w, h), fill_color)`）。虽然组件只在 rect 区域绘制了卡片，但返回的 RGBA 图层的其他区域是**不透明的 fill_color**。当 `alpha_composite` 合成时，第二张卡片的全画布不透光层覆盖了第一张卡片的内容。

**修复**：`draw()` 只创建透明图层，仅在组件的 rect 区域绘制不透明内容。`create_text_layer` 仅用于文字绘制的小尺寸不透光层（尺寸 = 文字包围盒 + 少量 padding）。

### Bug 6: mark_dirty 渲染冻结（v2.0→v2.1.0）

**症状**：hover 交互有明显延迟，拖动滑块时滑块位置更新滞后。

**根因**：`mark_dirty()` 使用 `after_idle` 调度渲染。`after_idle` 在 tkinter 事件循环完全空闲时才执行，如果事件队列中有多个待处理事件（如连续的 Motion 事件），渲染可能被延迟数十甚至上百毫秒。

**修复**：从 `after_idle` 改为 `after(16ms)`——约 60fps 节流。既保持了防抖效果（连续多个 mark_dirty 只产生一次渲染），又保证了 hover 反馈的即时性。

```python
def mark_dirty(self):
    if self._idle_id is not None:
        self.after_cancel(self._idle_id)
        self._idle_id = None
    if not self._dirty:
        self._dirty = True
    self._idle_id = self.after(16, self._do_render)  # 60fps
```

### Bug 7: exec_command 误杀健康连接（v2.1.0）

**症状**：命令执行失败时立即触发自动重连，即使只是命令本身有问题（如 `ls /nonexistent`），一次失败的 exec_command 导致整个连接断开并重连。

**根因**：v2.0 中 `exec_command` 捕获所有异常后都调用 `_auto_reconnect()`。但 `paramiko.SSHException` 可能由命令本身的错误引起，不代表连接断开。

**修复**：v2.1.0 中 `exec_command` 不再自动重连。重连逻辑移至 Keep-alive 检测——只有连续 2 次保活探测失败才认为连接确实断开。

### Bug 8: _original_hostname 被 IP 覆盖（v2.2.1）

**症状**：IP 漂移修复只生效一次——第一次漂移后，`_host` 变成了 IP 地址，后续解析时 `_resolve_hostname(ip_address)` 发现是 IP 就直接返回，不再重新解析主机名。

**根因**：`_host` 在 `_resolve_hostname` 和 `connect` 成功后会被更新为实际 IP。下一次 `_auto_reconnect` 时，`resolve_from = self._original_hostname or self._host` —— 如果 `_original_hostname` 为空就使用 `_host`。但在 v2.2.0 中，`_original_hostname` 只在 `_resolve_hostname` 返回有值时才设置，而 `_resolve_hostname` 返回 `(resolved_ip, hostname)` —— 只有传入的是主机名时 `hostname` 才非 None。

**修复**：在 `_do_connect()` 成功后，直接判断传入的 `host` 是否为 IP 地址——用 `ipaddress.ip_address(host)` 尝试解析，失败则说明是主机名，将其保存到 `_original_hostname`。

### Bug 9: Keep-alive 从未启动（v2.2.1）

**症状**：连接一段时间后无操作自动断开，保活功能"存在但无效"。

**根因**：`start_keep_alive()` 定义在 `SSHClient` 中，但 `connect()` 成功后从未调用它。代码流程是 `connect() → _do_connect() → 设置 _connected = True`，但 `start_keep_alive()` 不在调用链中。

**修复**：在 `_do_connect()` 成功后，自动调用 `start_keep_alive()`。

---

## 6. 测试策略

### 6.1 覆盖范围

共 **261 个测试用例**，分布在 7 个测试文件中：

| 测试文件 | 用例数 | 覆盖内容 |
|----------|--------|----------|
| `test_pillui_components.py` | 105 | 所有 8 个 PillUI 组件的状态机、交互、boundary |
| `test_theme.py` | 45 | ThemeColors 令牌读写、模式切换、颜色主题覆盖 |
| `test_terminal_session.py` | 33 | 命令历史、上下翻阅、边界值 |
| `test_background_manager.py` | 30 | 单例行为、Canvas 注册/注销、背景设置、缓存 |
| `test_config.py` | 17 | 加载、深度合并、验证、备份恢复、V1→V2→V3 迁移 |
| `test_ssh_client.py` | 17 | 状态管理、命令解析、重连逻辑、IP 漂移、保活 |
| `test_terminal_output.py` | 14 | 行插入、删除、虚拟滚动边界、输出获取 |

### 6.2 组件逻辑测试策略

PillUI 组件测试使用**真实 tkinter 根窗口**（`setUpModule` 创建隐藏 `tk.Tk()`）来创建 `tk.DoubleVar`、`tk.BooleanVar` 等 Variable 对象。这是必要的——PillowImage、Slider 等组件依赖 `tkinter.Variable` 进行双向数据绑定。

```python
# 来自 test_pillui_components.py
@classmethod
def setUpClass(cls):
    cls._root = tk.Tk()
    cls._root.withdraw()  # 隐藏窗口，不显示
```

PageCanvas 的 render 方法在测试中被 mock，避免实际调用 `ImageTk.PhotoImage`（需要真实的 Canvas widget 尺寸）。

### 6.3 为什么不做 UI 截图对比测试？

考虑过以下方案：
1. **PIL Image 逐像素对比**：PageCanvas.render() 输出 PIL Image，与预期图像做像素级 diff
2. **Selenium-style 自动化**：模拟用户点击，截图对比

否决原因：
- Pillow 字体渲染受系统字体版本影响（微软雅黑不同版本字形略有差异），跨机器对比不可靠
- 截图测试维护成本极高——每个组件状态变化都需要新的"黄金参考图"
- 当前 261 个组件行为测试已经覆盖了所有状态机路径和 boundary 条件，UI 层的正确性由这些测试间接保证

---

## 7. 开源发布

### 7.1 MIT 协议选择

选择 MIT 而非 GPL 的核心考量：`pillui` 组件库具有独立复用价值。如果有人想在自己的 tkinter 项目中使用这套 Pillow 组件库，MIT 允许他们闭源使用而不需要公开自己的代码。

### 7.2 文档体系

五个文档文件构成了完整的文档体系：

| 文档 | 定位 | 读者 |
|------|------|------|
| `README.md` | 项目概览、快速开始、项目结构 | 首次接触者 |
| `docs/ARCHITECTURE.md` | 分层架构、组件设计、渲染策略、设计决策 | 贡献者、代码审查者 |
| `docs/API.md` | 完整 API 参考（PillUI + 服务层 + 页面层） | 使用 pillui 的开发者 |
| `docs/USER_GUIDE.md` | 功能使用说明、快捷键、常见问题 | 终端用户 |
| `docs/COMPLIANCE_REPORT.md` | 开源合规审查报告 | Reviewer |

### 7.3 敏感信息清理

v2.2.2 开源发布前执行的清理：
- `pimanager.json` 中所有个人默认配置（主机名 `raspberrypi.local`、用户名 `pi`、密钥路径 `~/.ssh/id_ed25519`）替换为通用占位符
- `README.md` 添加 License 徽章和 Python 版本徽章
- 合规审查报告更新，确认所有修复已应用

---

## 8. 性能数据

### 8.1 字体缓存命中率

`_font_cache` 字典以 `(family, size)` 为 key。项目固定使用 `msyh`（微软雅黑常规）和 `msyhbd`（微软雅黑粗体）两种字体。在 1.0x 字体缩放下，所有组件共享字号 11px ~ 26px 约 8-10 个不同 size。首帧渲染后缓存命中率接近 100%。

### 8.2 mark_dirty 防抖效果

`after(16ms)` 防抖策略：同一帧内（16ms 窗口）连续多次 `mark_dirty()` 只触发一次 `render()`。典型场景：
- 拖拽滑块时每移动 1px 触发 1 次 mark_dirty → 60fps 下每秒至多 60 次 render，而非每像素触发
- 主题切换时 20+ 个组件各自调用 mark_dirty → 合并为 1 次全页渲染

### 8.3 BackgroundManager per-size 缓存

`_size_cache` 字典以 `(size, fit_mode)` 为 key。窗口大小不变时，resize（LANCZOS 重采样）仅发生 1 次。LANCZOS 是较慢但质量最高的 resize 算法，缓存避免了每次渲染都重采样的大开销。

### 8.4 Canvas 虚拟滚动帧率

文件列表和终端输出都采用"全量遍历 + 跳过不可见行"策略：
- 文件列表：行高 28px，800px 可见高 ≈ 28 行可见，但遍历所有 N 行。数百个文件时无感知延迟
- 终端输出：行高 18px，约 30-40 行可见。O(n) 遍历在 n < 2000 时流畅

改进方向：当输出量达到数万行时，用二分查找定位起始可见行索引，仅遍历可见范围。

### 8.5 各页面组件数量与渲染耗时

| 页面 | PillUI 组件数 | 每次 render 的 alpha_composite 次数 |
|------|-------------|----------------------------------|
| 侧边栏 | ~22 | 22 |
| 状态监控 | ~25 | 25 |
| 设置页 | ~28 | 28 |
| 文件管理 | 0 (原生 Canvas) | 0 |
| 命令终端 | 0 (原生 Canvas) | 0 |

1100x700 尺寸下，单个等大 RGBA 图层占用约 3MB 内存。25 层合成时临时内存峰值约 75MB（Python 会及时回收中间图层）。

---

## 9. 未来方向

### 9.1 高 DPI 适配

当前在 100% 缩放的显示器上所有像素尺寸精确。在高 DPI（150%/200%）下，tkinter Canvas 的 `create_image` 会做缩放但 Pillow 图层是固定像素——文字和组件会模糊。需要实现 DPI 感知的缩放因子。

### 9.2 插件系统

以下功能目前硬编码在页面中，适合抽象为插件：
- 快捷命令按钮（10 个），定义在 `terminal_page.py` 的 `QUICK_COMMANDS` 列表
- 状态监控的 Shell 命令
- 文件管理器的"远程运行"执行器（.py → python3, .sh → bash）

### 9.3 Web 版

最自然的演进方向：WebSocket + xterm.js。`SSHClient` 的 `exec_command_streaming` 已经提供了逐行流式回调，只需将 `on_stdout` 从 `self.after(0, insert_output)` 改为 WebSocket send。终端渲染交给 xterm.js（它专门做这件事）。pillui 组件库保留用于桌面版。

---

*报告基于 commit f14a3b1 的实际代码生成，所有代码片段均来自项目源文件。*
