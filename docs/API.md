# PiManager v2 API 文档

> PiManager — 轻量级树莓派 Zero W 桌面管理器，版本 2.1.0。基于 tkinter + Pillow 自绘 UI 组件库（PillUI），替代 CustomTkinter 依赖，通过 Paramiko 实现 SSH 远程管理。

---

## 目录

1. [PillUI 组件库](#pillui-组件库)
   - [渲染工具函数](#渲染工具函数)
   - [BaseComponent](#basecomponent)
   - [PageCanvas](#pagecanvas)
   - [PillowButton](#pillowbutton)
   - [PillowLabel](#pillowlabel)
   - [PillowProgressBar](#pillowprogressbar)
   - [PillowCard](#pillowcard)
   - [PillowCheckBox](#pillowcheckbox)
   - [PillowSlider](#pillowslider)
   - [PillowOptionMenu](#pillowoptionmenu)
   - [PillowScrollFrame](#pillowscrollframe)
2. [核心服务 API](#核心服务-api)
   - [ThemeColors](#themecolors)
   - [配置管理 (config)](#配置管理-config)
   - [SSHClient](#sshclient)
   - [StreamingCommand](#streamingcommand)
   - [BackgroundManager](#backgroundmanager)
3. [页面 API](#页面-api)
   - [PiManagerApp](#pimanagerapp)
   - [StatusPanel](#statuspanel)
   - [FileBrowser](#filebrowser)
   - [CanvasFileList / LocalFileList](#canvasfilelist--localfilelist)
   - [TerminalPage](#terminalpage)
   - [TerminalSession](#terminalsession)
   - [TerminalTab](#terminaltab)
   - [CanvasTerminalOutput](#canvasterminaloutput)
   - [SettingsPage](#settingspage)

---

## PillUI 组件库

PillUI (`pillui/`) 是一套纯 Pillow + tkinter Canvas 渲染的 UI 组件库。所有组件继承自 `BaseComponent`，通过 `PageCanvas` 管理渲染和事件分发。

### 渲染工具函数

位于 `pillui/renderer.py` 和 `pillui/_draw_utils.py`，提供颜色转换、字体加载和图层管理。

#### `hex_to_rgba(hex_color, alpha=255)`

将十六进制颜色字符串转换为 RGBA 元组。

```
:param hex_color: 十六进制颜色字符串，如 "#1A2B3C"
:param alpha: alpha 通道值，范围 0-255，默认 255（不透明）
:return: (R, G, B, A) 元组
```

```python
from pillui.renderer import hex_to_rgba
color = hex_to_rgba("#4CAF50")        # (76, 175, 80, 255)
translucent = hex_to_rgba("#4CAF50", 128)  # (76, 175, 80, 128)
```

#### `hex_to_rgb(hex_color)`

将十六进制颜色字符串转换为 RGB 元组。

```
:param hex_color: 十六进制颜色字符串，如 "#1A2B3C"
:return: (R, G, B) 元组
```

#### `get_font(family='msyh', size=12)`

加载字体，带缓存和多平台路径回退。

```
:param family: 字体名称（不含扩展名），如 "msyh"、"msyhbd"
:param size: 字号（像素）
:return: PIL ImageFont 对象
```

搜索路径依次为：
1. `C:/Windows/Fonts/{family}.ttc` — Windows 微软雅黑
2. `C:/Windows/Fonts/{family}.ttf` — Windows TrueType
3. `/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc` — Linux Noto
4. `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` — Linux DejaVu
5. PIL 默认字体（最终回退）

```python
font_normal = get_font('msyh', 12)
font_bold = get_font('msyhbd', 16)
```

#### `create_layer(w, h)`

创建透明的 RGBA 图层。

```
:param w: 宽度（像素）
:param h: 高度（像素）
:return: PIL RGBA Image，所有像素初始为 (0, 0, 0, 0)
```

#### `composite_layer(base, layer, x=0, y=0)`

将 layer 叠加到 base 上，返回合成结果。

```
:param base: 底层 PIL Image（RGBA）
:param layer: 要叠加的 PIL Image（RGBA）
:param x: 水平偏移量（像素）
:param y: 垂直偏移量（像素）
:return: 合成后的 PIL Image
```

#### `center_text(draw, rect, text, fill, font)`

在矩形区域内居中绘制文字。

```
:param draw: PIL ImageDraw 对象
:param rect: (x, y, width, height) 矩形区域
:param text: 文字内容
:param fill: 文字颜色 RGB 元组
:param font: PIL ImageFont 对象
```

#### `draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=1)`

在 ImageDraw 上绘制圆角矩形（`_draw_utils.py`）。

```
:param draw: PIL ImageDraw 对象
:param x1: 左上角 x 坐标
:param y1: 左上角 y 坐标
:param x2: 右下角 x 坐标
:param y2: 右下角 y 坐标
:param radius: 圆角半径
:param fill: 填充色 RGBA 元组
:param outline: 边框色 RGBA 元组
:param width: 边框宽度
```

#### `text_bbox(text, font)`

获取文字包围盒尺寸（`_draw_utils.py`）。

```
:param text: 文字内容
:param font: PIL ImageFont 对象
:return: (width, height) 元组
```

#### `draw_text_aligned(draw, rect, text, fill, font, align='center')`

在矩形内绘制文字，支持水平对齐和垂直居中（`_draw_utils.py`）。

```
:param draw: PIL ImageDraw 对象
:param rect: (x, y, width, height) 矩形区域
:param text: 文字内容
:param fill: 文字颜色 RGB 元组
:param font: PIL ImageFont 对象
:param align: "left" | "center" | "right"，默认 "center"
```

#### `fit_image(image, target_w, target_h, mode='fill', bg_color=(0, 0, 0, 0))`

将图片适配到目标尺寸，支持 4 种适配模式（`pillui/image_utils.py`，v2.1.0 新增）。

```
:param image: PIL Image 对象
:param target_w: 目标宽度（像素）
:param target_h: 目标高度（像素）
:param mode: 适配模式 — "fill"（拉伸填充）/ "contain"（完整显示留白）/ "cover"（裁剪填充）/ "tile"（平铺）
:param bg_color: contain/tile 模式下的背景色 RGBA 元组，默认透明
:return: 适配后的 PIL Image（target_w × target_h）
```

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `fill` | 拉伸到目标尺寸，可能变形 | 精确填充，不关心比例 |
| `contain` | 等比缩放完整显示，留白居中 | 显示完整图片 |
| `cover` | 等比缩放填满，超出裁剪 | 背景填充（v2.1.0 默认） |
| `tile` | 原始尺寸平铺 | 纹理/小图标背景 |

```python
from pillui.image_utils import fit_image

# 背景图片按 cover 模式适配 1100x700
bg = fit_image(original_img, 1100, 700, mode="cover")
```

---

### BaseComponent

`pillui/canvas_renderer.py` — 所有 Pillow UI 组件的抽象基类。定义组件生命周期和事件接口。

```python
class BaseComponent:
    def __init__(self, x=0, y=0, w=0, h=0)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | int | 组件左上角 x 坐标（像素） |
| `y` | int | 组件左上角 y 坐标（像素） |
| `w` | int | 组件宽度（像素） |
| `h` | int | 组件高度（像素） |

**实例属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `rect` | tuple | 组件边界 `(x1, y1, x2, y2)` |
| `visible` | bool | 是否可见，默认 `True` |
| `x` | int | 只读属性，返回 `rect[0]`（左上角 x） |
| `y` | int | 只读属性，返回 `rect[1]`（左上角 y） |
| `w` | int | 只读属性，返回组件宽度 |
| `h` | int | 只读属性，返回组件高度 |

**公共方法**

#### `draw(cw, ch, font_scale=1.0)`

在透明图层上绘制组件。子类必须实现此方法。

```
:param cw: 整个 PageCanvas 的宽度（像素）
:param ch: 整个 PageCanvas 的高度（像素）
:param font_scale: 字体缩放因子（v2.1.0 新增），默认 1.0
:return: PIL RGBA Image 图层
```

> **v2.1.0 变更**：所有组件的 `draw()` 方法新增 `font_scale` 参数，由 PageCanvas 渲染时传入。组件内部字号计算为 `int(base_size * font_scale)`，确保字体缩放滑块全局生效。

#### `hit_test(mx, my)`

判断鼠标坐标是否在组件范围内。

```
:param mx: 鼠标 x 坐标
:param my: 鼠标 y 坐标
:return: bool — 鼠标是否在组件区域内
```

#### `set_pos(x, y)`

更新组件左上角位置。

```
:param x: 新 x 坐标
:param y: 新 y 坐标
```

#### `set_size(w, h)`

更新组件尺寸（保持左上角不变）。

```
:param w: 新宽度
:param h: 新高度
```

**事件钩子（子类按需覆盖）**

| 方法 | 触发时机 |
|------|----------|
| `on_click(event)` | 左键按下 |
| `on_release(event)` | 左键释放 |
| `on_enter()` | 鼠标进入组件区域 |
| `on_leave()` | 鼠标离开组件区域 |
| `on_drag(event)` | 鼠标拖拽中（B1-Motion） |
| `on_mousewheel(event)` | 鼠标滚轮事件 |
| `apply_theme(theme_colors)` | 应用主题颜色（v2.1.0 新增），子类重写以从 ThemeColors 动态更新颜色属性 |

---

### PageCanvas

`pillui/canvas_renderer.py` — 全页面 Canvas。负责管理 Pillow 组件的注册、渲染合成和事件分发。

```python
class PageCanvas(tk.Canvas):
    def __init__(self, master, width=400, height=300, **kwargs)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `width` | int | Canvas 宽度，默认 400 |
| `height` | int | Canvas 高度，默认 300 |
| `**kwargs` | — | 传递给 `tk.Canvas` 的额外参数（自动设置 `highlightthickness=0, bd=0`） |

**使用示例**

```python
from pillui import PageCanvas, PillowButton

canvas = PageCanvas(master, width=800, height=600)
canvas.set_bg_color("#0D1117")
btn = PillowButton("点击", x=10, y=10, w=100, h=36, command=my_func)
canvas.add("my_btn", btn)
canvas.grid(row=0, column=0, sticky="nsew")
```

#### `add(comp_id, comp)`

注册组件到 Canvas。组件按 add 顺序叠加，hit-test 从上层开始。

```
:param comp_id: 唯一组件 ID（字符串），用于后续获取和移除
:param comp: BaseComponent 实例
```

调用后自动标记重绘。组件的 `_parent` 会被设置为当前 Canvas。

#### `remove(comp_id)`

移除指定组件。

```
:param comp_id: 组件 ID
```

如果该组件当前被 hover，自动清除 hover 状态。

#### `get(comp_id)`

获取已注册的组件。

```
:param comp_id: 组件 ID
:return: BaseComponent 实例，不存在则返回 None
```

#### `clear()`

清空所有已注册组件，清除 hover 状态，标记重绘。

#### `set_bg_color(color)`

设置纯色背景。

```
:param color: hex 颜色字符串，如 "#0D1117"
```

会清除之前设置的背景图片。

#### `set_bg_image(pil_image)`

设置背景图片。

```
:param pil_image: PIL Image 对象
```

#### `get_bg_image()`

获取当前背景图。

```
:return: PIL Image 或 None
```

#### `mark_dirty()`

标记需要重绘。使用 `after_idle` 延迟合并多次调用，避免频繁渲染。如果上一个 idle 尚未执行，会被取消。

#### `render()`

合成所有组件图层并显示到 Canvas。渲染流程：
1. Layer 0 — 背景（图片或纯色）
2. Layer 1..N — 每个可见组件的 `draw()` 输出，用 `Image.alpha_composite` 逐层叠加
3. 转换 `ImageTk.PhotoImage` 显示到 tk Canvas

```
手动调用：通常在背景变更后显式调用
自动调用：add/remove/clear/set_bg_* 等操作后通过 mark_dirty 自动触发
```

#### `apply_theme(theme_colors=None)`

将主题颜色传播到所有注册组件并触发重绘（v2.1.0 新增）。

```
:param theme_colors: ThemeColors 类，若未传则自动导入
```

遍历 `_components` 中所有组件，调用其 `apply_theme(theme_colors)` 方法，然后自动触发 `mark_dirty()` 重绘。

#### `set_font_scale(scale)`

设置字体缩放因子。

```
:param scale: 缩放比例（float），1.0 为默认大小
```

#### `font_scale` 属性

只读属性，返回当前字体缩放因子。

**事件分发机制**

PageCanvas 内部绑定以下 tk 事件，自动分发给对应组件：

| tk 事件 | 分发给组件的方法 | 逻辑 |
|---------|-----------------|------|
| `<Button-1>` | `comp.on_click(event)` | 从上层向下 hit-test，命中即停 |
| `<B1-Motion>` | `comp.on_drag(event)` | 发给当前 hover 的组件 |
| `<ButtonRelease-1>` | `comp.on_release(event)` | 发给当前 hover 的组件 |
| `<Motion>` | `comp.on_enter()` / `comp.on_leave()` | 跟踪 hover 状态变化，变化时触发重绘 |
| `<MouseWheel>` | `comp.on_mousewheel(event)` | 发给当前 hover 的组件 |
| `<Configure>` | `mark_dirty()` | 窗口大小改变，80ms 延迟后重绘 |

hover 状态切换流程：Motion 事件遍历所有可见组件做 hit-test，若新 hover 与旧 hover 不同，则旧组件的 `on_leave()` 和新组件的 `on_enter()` 依次触发，然后标记重绘。

---

### PillowButton

`pillui/button.py` — 纯 Pillow 绘制的按钮，支持 hover/pressed 状态变化和 3 种预设样式。

```python
class PillowButton(BaseComponent):
    def __init__(self, text='', x=0, y=0, w=100, h=36,
                 command=None, style='primary', font_size=13,
                 disabled=False)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | str | 按钮文字 |
| `x` | int | 左上角 x |
| `y` | int | 左上角 y |
| `w` | int | 宽度，默认 100 |
| `h` | int | 高度，默认 36 |
| `command` | callable | 点击回调（无参数） |
| `style` | str | 样式名：`"primary"` / `"danger"` / `"transparent"`，默认 `"primary"` |
| `font_size` | int | 字号，默认 13 |
| `disabled` | bool | 初始禁用状态，默认 `False` |

**3 种样式对照**

| 样式 | 背景 | 悬停背景 | 文字颜色 | 边框 |
|------|------|---------|---------|------|
| `primary` | `#2B5B2B` | `#3A7A3A` | `#FFFFFF` | 无 |
| `danger` | `#8B0000` | `#A00000` | `#FFFFFF` | 无 |
| `transparent` | 透明 | `#333333` | `#C9D1D9` | `#555555` |

**状态渲染优先级**：禁用 > 按下 > 悬停 > 正常

当 `disabled=True` 时，背景强制为 `#555555`，文字颜色为 `#888888`。

#### `set_text(text)`

动态更新按钮文字。

```
:param text: 新文字内容
```

自动触发父 Canvas 重绘。

```python
btn = PillowButton("连接", x=10, y=10, w=100, h=36, command=do_connect)
canvas.add("connect_btn", btn)
# 后续更新
canvas.get("connect_btn").set_text("断开")
```

#### `set_style(style)`

切换按钮样式。

```
:param style: "primary" | "danger" | "transparent"
```

#### `set_disabled(disabled)`

设置禁用状态。

```
:param disabled: bool — True 禁用，False 启用
```

禁用状态下按钮不响应点击。

#### `on_click(event)` / `on_release(event)`

按下时设置 `_pressed=True`，释放时执行 `command` 回调。禁用时均不响应。

#### `on_enter()` / `on_leave()`

进入时标记 `_hovered=True`，离开时重置 `_hovered=False` 和 `_pressed=False`。

---

### PillowLabel

`pillui/label.py` — 纯文本标签，支持多行、对齐方式，以及 `nw`（左上角）和 `center` 两种锚点模式。

```python
class PillowLabel(BaseComponent):
    def __init__(self, text='', x=0, y=0, w=100, h=20,
                 font_size=12, color='#C9D1D9',
                 align='left', weight='normal', anchor='nw')
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | str | 文字内容，支持 `\n` 换行 |
| `x` | int | 水平位置 |
| `y` | int | 垂直位置 |
| `w` | int | 宽度（最小 1） |
| `h` | int | 高度（最小 1） |
| `font_size` | int | 字号，默认 12 |
| `color` | str | hex 颜色，默认 `"#C9D1D9"` |
| `align` | str | 水平对齐：`"left"` / `"center"` / `"right"`，默认 `"left"` |
| `weight` | str | 字重：`"normal"`（微软雅黑）或 `"bold"`（微软雅黑粗体），默认 `"normal"` |
| `anchor` | str | 定位锚点：`"nw"`（左上角，坐标即组件左上角）或 `"center"`（坐标即组件中心），默认 `"nw"` |

**anchor 模式说明**

- `"nw"` — `x, y` 为组件左上角坐标，`w, h` 为实际尺寸。这是常规模式。
- `"center"` — `x, y` 为组件中心坐标，`w, h` 控制文字区域宽度。文字垂直方向根据行数居中。

```python
# 左上角锚点 — 常规用法
label = PillowLabel("Hello World", x=20, y=30, w=200, h=24)

# 中心锚点 — 组件以 (400, 300) 为中心放置
label = PillowLabel("居中文字", x=400, y=300, w=200, h=30, anchor="center")

# 多行文字
label = PillowLabel("第一行\n第二行\n第三行",
                     x=10, y=10, w=300, h=80, font_size=14)
```

#### `set_text(text)`

更新文字内容，仅在内容变化时触发重绘。

```
:param text: 新文字内容
```

#### `set_color(color)`

更新文字颜色。

```
:param color: hex 颜色字符串，如 "#FF6B6B"
```

---

### PillowProgressBar

`pillui/progress_bar.py` — 水平进度条，带背景轨道和渐变填充效果。

```python
class PillowProgressBar(BaseComponent):
    def __init__(self, x=0, y=0, w=200, h=12,
                 value=0.0, color='#4CAF50')
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | int | 左上角 x |
| `y` | int | 左上角 y |
| `w` | int | 宽度，默认 200 |
| `h` | int | 高度，默认 12 |
| `value` | float | 初始进度值 0.0 ~ 1.0，默认 0.0 |
| `color` | str | 填充色 hex 字符串，默认 `"#4CAF50"` |

**渲染**：背景轨道为 `#1A1A1A` 圆角矩形（radius=4），填充条用 `color` 绘制。值小于等于 0 时不显示填充条，填充宽度小于 3px 时跳过绘制。

#### `set(value)`

设置进度值，自动 clamp 到 `[0.0, 1.0]`。

```
:param value: 进度值 0.0 ~ 1.0
```

#### `set_color(color)`

设置填充颜色。

```
:param color: hex 颜色字符串
```

#### `value` 属性

只读属性，返回当前进度值（0.0 ~ 1.0）。

```python
bar = PillowProgressBar(x=20, y=100, w=200, h=16)
canvas.add("cpu_bar", bar)

# 更新进度
bar.set(0.75)      # 75%
bar.set_color("#FF4444")  # 变红
```

---

### PillowCard

`pillui/card.py` — 圆角矩形卡片容器，带可选的标题栏。

```python
class PillowCard(BaseComponent):
    def __init__(self, x=0, y=0, w=200, h=100,
                 title='', fill='#161B22',
                 border='gray35', radius=10, title_size=13)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | int | 左上角 x |
| `y` | int | 左上角 y |
| `w` | int | 宽度，默认 200 |
| `h` | int | 高度，默认 100 |
| `title` | str | 标题文字，显示于卡片左上角（距边界 12×10 像素），空字符串不显示 |
| `fill` | str | 背景填充色 hex，默认 `"#161B22"` |
| `border` | str | 边框颜色 hex，默认 `"gray35"` |
| `radius` | int | 圆角半径，默认 10 |
| `title_size` | int | 标题字号，默认 13 |

**说明**：PillowCard 仅绘制背景和标题，不自动管理子组件。需将子组件（Label、Button 等）通过坐标叠加在卡片上方（使用相同的 PageCanvas，按 add 顺序后续组件会叠加到卡片之上）。

```python
# 卡片 + 内部组件叠加
card = PillowCard(10, 10, 300, 120, title="系统信息",
                  fill="#161B22", border="gray30", radius=8)
canvas.add("info_card", card)

# 叠加在卡片上方的标签（坐标相对于 Canvas 原点）
cpu_label = PillowLabel("CPU: 45%", x=24, y=42, w=260, h=20, font_size=12)
canvas.add("cpu_label", cpu_label)
```

---

### PillowCheckBox

`pillui/checkbox.py` — 复选框组件，使用 tk.BooleanVar 管理状态。

```python
class PillowCheckBox(BaseComponent):
    def __init__(self, text='', x=0, y=0, w=200, h=24,
                 variable=None, command=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | str | 标签文字 |
| `x` | int | 左上角 x |
| `y` | int | 左上角 y |
| `w` | int | 组件宽度，默认 200 |
| `h` | int | 组件高度，默认 24 |
| `variable` | tk.BooleanVar | 绑定布尔变量，用于读写选中状态 |
| `command` | callable | 状态切换回调（无参数） |

**渲染**：16×16 的复选框（radius=3），选中时填充 `#4CAF50` 并绘制白色勾号（两条短线组合），未选中时填充 `#1A1A1A`。标签文字在复选框右侧 8px 处，颜色 `#C9D1D9`，字号 12。

**状态切换逻辑**：点击时调用 `variable.set(not variable.get())` 翻转状态，随后标记重绘并执行 `command`。

**hit_test 重写**：垂直方向仅命中 `y1` 到 `y1+22` 的范围，便于和相邻组件留出间距。

```python
import tkinter as tk

var = tk.BooleanVar(value=True)
checkbox = PillowCheckBox("启用自动连接", x=20, y=40, w=260, h=24,
                          variable=var,
                          command=lambda: print("状态:", var.get()))
canvas.add("auto_check", checkbox)
```

---

### PillowSlider

`pillui/slider.py` — 水平滑块组件，支持拖拽交互和步进离散化。

```python
class PillowSlider(BaseComponent):
    def __init__(self, x=0, y=0, w=200, h=24,
                 from_val=0.0, to_val=1.0, steps=10,
                 variable=None, command=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | int | 左上角 x |
| `y` | int | 左上角 y |
| `w` | int | 宽度，默认 200 |
| `h` | int | 高度，默认 24 |
| `from_val` | float | 最小值，默认 0.0 |
| `to_val` | float | 最大值，默认 1.0 |
| `steps` | int | 离散步数（>0 时启用步进吸附），默认 10 |
| `variable` | tk.DoubleVar | 绑定变量，读写当前值 |
| `command` | callable | 释放时回调，传入当前值 `command(value)` |

**渲染**：轨道宽度为组件宽度减去左右各 8px 内边距。轨道底线 `#333333`，已填充段 `#4CAF50`。滑块椭圆半径 7px，拖拽中颜色变为 `#3A7A3A`。

**拖拽交互流程**：
1. 点击组件区域 → `_dragging=True`，根据鼠标 x 更新值
2. 拖拽移动（B1-Motion）→ `on_drag(event)` 持续调用 `_update_from_mouse`
3. 释放 → `_dragging=False`，最终更新值，执行 `command(value)`

**步进逻辑**：`_update_from_mouse` 先将鼠标位置映射为 `[0, 1]` 的比率，计算原始值，再用 `step_size = (to_val - from_val) / steps` 做 round 吸附，确保滑块停在离散刻度上。

```python
import tkinter as tk

scale_var = tk.DoubleVar(value=1.0)
slider = PillowSlider(x=140, y=40, w=260, h=24,
                      from_val=0.8, to_val=1.5, steps=7,
                      variable=scale_var,
                      command=lambda v: print(f"缩放: {v:.1f}x"))
canvas.add("scale_slider", slider)
```

---

### PillowOptionMenu

`pillui/option_menu.py` — 下拉选择框。Pillow 绘制外观，tk.Menu 弹窗选择。

```python
class PillowOptionMenu(BaseComponent):
    def __init__(self, x=0, y=0, w=120, h=30,
                 values=None, variable=None, command=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | int | 左上角 x |
| `y` | int | 左上角 y |
| `w` | int | 宽度，默认 120 |
| `h` | int | 高度，默认 30 |
| `values` | list[str] | 下拉选项列表 |
| `variable` | tk.StringVar | 绑定变量，存储当前选中值 |
| `command` | callable | 选择回调，传入选中的值 `command(value)` |

**渲染**：圆角矩形背景（`#1A1A1A`、radius=6、边框 `#555555`），左侧显示当前选中值，右侧显示 ▼ 箭头。

**tk.Menu 弹出机制**：`on_click` 时创建一个 `tk.Menu`（tearoff=0），遍历 `values` 为每个选项添加 `command`，调用 `menu.post(root_x, root_y)` 在组件正下方弹出。选择后通过 `_select(value)` 更新 `variable` 并执行 `command`。

Menu 的主题颜色通过 `ThemeColors.get()` 获取，若导入失败则使用硬编码回退值。

```python
import tkinter as tk

theme_var = tk.StringVar(value="dark")
menu = PillowOptionMenu(x=380, y=37, w=120, h=28,
                        values=["dark", "light"],
                        variable=theme_var,
                        command=lambda v: print(f"切换到: {v}"))
canvas.add("theme_menu", menu)
```

---

### PillowScrollFrame

`pillui/scroll_frame.py` — 可滚动内容区域，继承自 `PageCanvas`。

```python
class PillowScrollFrame(PageCanvas):
    def __init__(self, master, width=400, height=300,
                 content_height=600, **kwargs)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `width` | int | Canvas 宽度，默认 400 |
| `height` | int | Canvas 高度，默认 300 |
| `content_height` | int | 内容总高度（像素），默认 600 |
| `**kwargs` | — | 传递给 `PageCanvas` 的额外参数 |

内部自动创建垂直 `tk.Scrollbar`，放置在 Canvas 右侧（`row=0, column=1`）。

**滚动机制**：
- 鼠标滚轮：增量 30px，`_scroll_y` clamp 在 `[0, content_height - visible_h]` 范围内
- 滚动条拖动：通过 `_on_scrollbar` 的 `moveto` 解析比率更新 `_scroll_y`
- 渲染时：临时偏移所有组件坐标 (`y - _scroll_y`)，调用父类 `render()`，绘制完成后还原组件原始坐标

#### `set_content_height(h)`

更新内容总高度，触发重绘。

```
:param h: 内容高度（像素）
```

```python
from pillui.scroll_frame import PillowScrollFrame

scroll = PillowScrollFrame(master, width=400, height=300, content_height=800)
scroll.set_bg_color("#0D1117")
scroll.grid(row=0, column=0, sticky="nsew")

# 往滚动区域添加组件（坐标使用绝对坐标，会随滚动偏移）
for i in range(20):
    label = PillowLabel(f"第 {i+1} 行", x=10, y=i * 40, w=380, h=30)
    scroll.add(f"row_{i}", label)
```

---

## 核心服务 API

### ThemeColors

`theme.py` — 统一颜色令牌系统，支持深色/浅色模式切换和字体缩放。

```python
class ThemeColors:
    _mode = 'Dark'   # 类级别：当前主题模式
    _font_scale = 1.0  # 类级别：字体缩放因子
```

所有方法均为 `@classmethod`，无需实例化。

#### `set_mode(mode)`

设置主题模式。

```
:param mode: "dark" 或 "light"（大小写不敏感）
```

```python
ThemeColors.set_mode('dark')
ThemeColors.set_mode('light')
```

#### `get_mode()`

获取当前主题模式。

```
:return: "Dark" 或 "Light"
```

#### `toggle_mode()`

切换主题模式。当前为 Dark 则切为 Light，反之亦然。

#### `set_color_theme(name)` (v2.1.0 新增)

设置颜色主题，修改强调色系令牌。

```
:param name: "green" | "blue" | "dark-blue"
```

```python
ThemeColors.set_color_theme('blue')  # 切换为蓝色强调色
```

#### `get_color_theme()` (v2.1.0 新增)

获取当前颜色主题名称。

```
:return: "green" | "blue" | "dark-blue"
```

#### `get(key)`

获取颜色值。

```
:param key: 颜色令牌名称
:return: hex 颜色字符串，不存在时返回 "#000000"
```

#### `fg_hover(key)`

获取前景色和悬停色对。

```
:param key: 颜色令牌名称
:return: (fg_color, hover_color) 元组
```

#### `set_font_scale(scale)`

设置全局字体缩放因子。

```
:param scale: 缩放比例，1.0 为默认，范围 0.5 ~ 3.0
```

#### `get_font_scale()`

获取当前字体缩放因子。

```
:return: float
```

#### `scaled_font(family, size)`

返回缩放后的字体元组。

```
:param family: 字体名称
:param size: 原始字号
:return: (family, scaled_size) 元组
```

```python
font = ThemeColors.scaled_font('Segoe UI', 10)  # 返回缩放后的元组
```

**完整颜色令牌表**

| 令牌 | 深色 `#` | 浅色 `#` | 用途 |
|------|---------|---------|------|
| `bg` | `0D1117` | `FFFFFF` | 页面背景 |
| `bg_card` | `161B22` | `F6F8FA` | 卡片背景 |
| `text` | `C9D1D9` | `24292F` | 主文字 |
| `text_secondary` | `8B949E` | `656D76` | 次要文字 |
| `accent` | `4CAF50` | `2DA44E` | 强调色 |
| `accent_hover` | `3A7A3A` | `2C974B` | 强调色悬停 |
| `accent_dim` | `2B5B2B` | `DCF5E4` | 强调色弱化 |
| `danger` | `8B0000` | `CF222E` | 危险操作 |
| `danger_hover` | `A00000` | `A40E26` | 危险操作悬停 |
| `warning` | `FFB347` | `D4A72C` | 警告色 |
| `warning_strong` | `FF4444` | `CF222E` | 严重警告 |
| `card_border` | `(gray55, gray35)` | `(gray55, gray35)` | 卡片边框（元组） |
| `btn_primary` | `2B5B2B` | `2DA44E` | 主按钮背景 |
| `btn_primary_hover` | `3A7A3A` | `2C974B` | 主按钮悬停 |
| `btn_transparent_hover` | `333333` | `E8E8E8` | 透明按钮悬停 |
| `separator` | `(gray70, gray30)` | `(gray70, gray30)` | 分隔线（元组） |
| `input_placeholder` | `555555` | `999999` | 输入框占位符 |
| `scrollbar` | `555555` | `CCCCCC` | 滚动条 |
| `scrollbar_track` | `1A1A1A` | `E8E8E8` | 滚动条轨道 |
| `nav_active` | `(gray80, gray28)` | `(gray75, gray28)` | 导航激活（元组） |
| `dual_btn` | `1E3A5A` | `DDF4FF` | 双栏按钮 |
| `dual_btn_hover` | `2A4A6A` | `C6ECFF` | 双栏按钮悬停 |
| `terminal_prompt` | `4CAF50` | `2DA44E` | 终端提示符 |
| `status_ok` | `4CAF50` | `2DA44E` | 状态正常 |
| `local_file_name` | `8BCCFF` | `0969DA` | 本地文件名 |
| `canvas_bg` | `0D1117` | `FFFFFF` | Canvas 背景 |
| `canvas_text` | `C9D1D9` | `24292F` | Canvas 文字 |
| `canvas_text_dim` | `8B949E` | `656D76` | Canvas 弱化文字 |
| `canvas_selection` | `2A5A2A` | `DCF5E4` | Canvas 选中高亮 |
| `canvas_err` | `FF6B6B` | `CF222E` | Canvas 错误文字 |
| `canvas_quick_btn` | `1E3A1E` | `DCF5E4` | Canvas 快捷按钮 |
| `canvas_quick_btn_hover` | `2A4A2A` | `C6ECFF` | Canvas 快捷按钮悬停 |

---

### 配置管理 (config)

`config.py` — 配置加载、保存、验证、迁移和备份恢复。全部为模块级函数。

**常量**

| 常量 | 说明 |
|------|------|
| `CONFIG_DIR` | 配置目录 = `pimanager/` |
| `CONFIG_FILE` | 配置文件路径 = `pimanager/pimanager.json` |
| `CONFIG_BACKUP_DIR` | 备份目录 = `pimanager/config_backups/` |
| `CONFIG_VERSION` | 当前配置版本 = `2` |

**`DEFAULT_CONFIG` 完整结构**

```python
{
    'version': 2,
    'connections': [
        {
            'name': "树莓派 Zero W",
            'host': 'muchenxi-20081128.local',
            'port': 22,
            'username': 'chenxi',
            'key_path': '~/.ssh/id_ed25519',
            'use_key': True,
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
    }
}
```

#### `load_config()`

加载配置（自动迁移旧版本）。

```
:return: dict — 配置字典（始终包含所有默认字段）
```

流程：
1. 若 `pimanager.json` 存在，读取并调用 `_migrate_and_merge`
2. 若 JSON 损坏，尝试从最近备份恢复
3. 若无可用备份，返回 `DEFAULT_CONFIG.copy()`
4. 若配置文件不存在，返回 `DEFAULT_CONFIG.copy()`

#### `save_config(config)`

保存配置到文件，保存前自动备份当前配置。

```
:param config: 配置字典
```

自动设置 `config['version'] = CONFIG_VERSION`，格式化 JSON（`indent=2, ensure_ascii=False`）。

#### `validate_config(config)`

验证配置合法性。

```
:param config: 配置字典
:return: list[str] — 错误消息列表，无错误时为空列表
```

验证项：
- 端口在 `[1, 65535]`
- 主机地址非空
- `background_opacity` 在 `[0, 1]`
- `font_scale` 在 `[0.5, 3.0]`
- `refresh_interval` 在 `[1, 60]`

```python
from pimanager.config import load_config, validate_config

cfg = load_config()
errors = validate_config(cfg)
if errors:
    for e in errors:
        print(f"配置错误: {e}")
```

#### `backup_config()`

备份当前配置文件到 `config_backups/` 目录。

```
:return: str — 备份文件路径，失败时返回空字符串
```

备份文件命名格式：`pimanager_YYYYMMDD_HHMMSS.json`。自动清理保留最近 10 个备份。

#### `restore_config(backup_path=None)`

从备份恢复配置。

```
:param backup_path: 指定备份路径，None 则使用最新备份
:return: bool — 恢复成功返回 True
```

#### `reset_to_defaults()`

重置为默认配置并保存。

```
:return: dict — 默认配置字典
```

#### `get_connection(name=None)`

获取连接配置。

```
:param name: 连接名称，None 返回第一个连接
:return: dict — 连接配置字典
```

#### 配置迁移 (`_migrate_and_merge`)

自动执行版本迁移。当前支持迁移：
- **V1 → V2**：添加 `version` 字段，`behavior` 增加 `terminal_history_size`（默认 500）

---

### SSHClient

`ssh_client.py` — 基于 Paramiko 的 SSH 客户端，支持密钥/密码认证、命令执行、SFTP 文件传输、流式输出和自动重连。

```python
class SSHClient:
    def __init__(self)
```

构造函数无参数。所有连接参数通过 `connect()` 方法传入。

#### `connected` 属性

只读属性，返回当前连接状态（`bool`）。

#### `host` 属性

只读属性，返回当前连接的主机地址（`str`）。

#### `connect(host, port=22, username='pi', key_path=None, password=None, timeout=10)`

建立 SSH 连接。

```
:param host: 远程主机地址
:param port: SSH 端口，默认 22
:param username: 登录用户名，默认 "pi"
:param key_path: 私钥文件路径（Ed25519 或 RSA），用于密钥认证
:param password: 登录密码，用于密码认证
:param timeout: 连接超时秒数，默认 10
:return: (bool, str) — (成功标志, 消息)
```

认证优先级：密钥 > 密码。若已连接则先断开再重连。连接成功后自动打开 SFTP 通道。

```python
ssh = SSHClient()
ok, msg = ssh.connect("raspberrypi.local", 22, "pi",
                      key_path="/home/user/.ssh/id_ed25519")
if ok:
    print("连接成功")
```

#### `disconnect()`

断开连接，关闭 SFTP、Shell 通道和 SSH 客户端。线程安全（使用 `threading.RLock`）。

#### `reconnect()`

使用上次的连接参数自动重连。

```
:return: (bool, str) — (成功标志, 消息)
```

#### `exec_command(command, timeout=30)`

执行远程命令（阻塞模式）。

```
:param command: 要执行的 Shell 命令
:param timeout: 超时秒数，默认 30
:return: (exit_code, stdout, stderr) 三元组
```

未连接时返回 `(-1, '', "未连接")`。SSH 异常时自动尝试重连并重试一次。

```python
code, out, err = ssh.exec_command("ls -la /home/pi")
print(out)
```

#### `exec_command_batch(commands, timeout=30)`

批量执行命令，合并为一次 SSH 调用（用 `echo '---CMD_SPLIT---'` 分隔）。

```
:param commands: 命令字符串列表
:param timeout: 超时秒数，默认 30
:return: [(exit_code, stdout, stderr), ...] 结果列表
```

#### `exec_command_streaming(command, on_stdout=None, on_stderr=None, on_done=None, timeout=None)`

执行远程命令并实时流式返回输出（非阻塞）。立即返回 `StreamingCommand` 句柄。

```
:param command: 要执行的 Shell 命令
:param on_stdout: 回调 on_stdout(line) — 每行 stdout 输出时调用（在子线程中）
:param on_stderr: 回调 on_stderr(line) — 每行 stderr 输出时调用（在子线程中）
:param on_done: 回调 on_done(exit_code, error_message) — 命令完成时调用（在子线程中）
:param timeout: 通道创建超时秒数，None 使用默认值
:return: StreamingCommand 句柄
```

内部使用 `get_pty=True` 分配伪终端，使远程进程行缓冲输出。PTY 模式下 stdout 和 stderr 合并到 stdout 流。

```python
def on_out(line):
    print(f">>> {line}")

def on_done(code, err):
    print(f"完成, exit={code}, err={err}")

handle = ssh.exec_command_streaming(
    "ping -c 5 google.com",
    on_stdout=on_out,
    on_done=on_done
)
# 稍后可按需取消
handle.cancel()
```

#### `start_keep_alive(interval=30)` / `_stop_keep_alive()`

启动/停止连接保活。每 `interval` 秒发送 `echo "keepalive"`，失败时自动重连。

#### `list_dir(remote_path, limit=None, offset=0)`

列出远程目录内容（支持分页）。

```
:param remote_path: 远程目录路径
:param limit: 返回条目数上限（None=全部）
:param offset: 分页偏移量（0 起始）
:return: list[dict] — 文件信息列表，每个条目包含 name/size/mtime/is_dir/is_link/permissions
```

排序规则：目录优先，然后按名称字母序（`_sort_dir_key`）。

#### `get_file_info(remote_path)`

获取单个文件/目录信息。

```
:param remote_path: 远程路径
:return: dict 或 None — 文件信息字典
```

#### `download_file(remote_path, local_path, progress_callback=None)`

下载文件（含大小校验）。

```
:param remote_path: 远程文件路径
:param local_path: 本地保存路径
:param progress_callback: 进度回调 callback(transferred, total)
:return: (bool, str) — (成功标志, 消息)
```

传输完成后校验远程文件大小与本地文件大小是否一致。

#### `upload_file(local_path, remote_path, progress_callback=None)`

上传文件（含大小校验）。

```
:param local_path: 本地文件路径
:param remote_path: 远程保存路径
:param progress_callback: 进度回调 callback(transferred, total)
:return: (bool, str) — (成功标志, 消息)
```

#### `delete_remote(remote_path)`

删除远程文件/目录（目录使用迭代方式递归删除，避免大目录栈溢出）。

```
:param remote_path: 远程路径
:return: (bool, str) — (成功标志, 消息)
```

#### `create_remote_dir(remote_path)`

创建远程目录。

```
:param remote_path: 远程目录路径
:return: (bool, str) — (成功标志, 消息)
```

#### `rename_remote(old_path, new_path)`

重命名远程文件/目录。

```
:param old_path: 原始路径
:param new_path: 新路径
:return: (bool, str) — (成功标志, 消息)
```

#### `get_system_status()`

获取树莓派系统状态（1 次 SSH 往返，合并多个命令）。

```
:return: dict — 系统状态字典
```

返回字典结构：

```python
{
    'hostname': str,         # 主机地址
    'cpu_percent': float,    # CPU 使用率 (%)
    'cpu_temp': float,       # CPU 温度 (°C)
    'memory_total': int,     # 内存总量 (MB)
    'memory_used': int,      # 已用内存 (MB)
    'memory_percent': float, # 内存使用率 (%)
    'disk_total': int,       # 磁盘总量 (MB)
    'disk_used': int,        # 已用磁盘 (MB)
    'disk_percent': float,   # 磁盘使用率 (%)
    'uptime': str,           # 运行时间
    'load_avg': str,         # 负载均值
    'os_version': str,       # 操作系统版本
    'kernel': str,           # 内核版本
    'error': str,            # 错误信息（始终为空字符串）
}
```

#### `get_sidebar_stats()`

获取侧边栏精简状态（1 次 SSH 往返）。

```
:return: dict — 精简状态字典
```

返回字典结构：

```python
{
    'cpu': float,       # CPU 使用率 (%)
    'mem_total': int,   # 内存总量 (MB)
    'mem_used': int,    # 已用内存 (MB)
    'mem_pct': float,   # 内存使用率 (%)
    'ip': str,          # IP 地址（无则 "--"）
    'temp': float,      # CPU 温度 (°C)
}
```

#### `test_connection()`

测试连接是否存活。

```
:return: bool
```

#### `_parse_kv_lines(text)` (静态方法)

解析 `KEY:VALUE` 行输出，供内部使用。

```
:param text: 原始文本
:return: [(key, value), ...] 键值对列表
```

---

### StreamingCommand

`ssh_client.py` — 流式命令执行句柄，由 `exec_command_streaming` 返回。

```python
class StreamingCommand:
    def __init__(self)
```

#### `is_running` 属性

只读属性，返回命令是否仍在运行（`bool`）。

#### `send_ctrl_c()`

发送 Ctrl+C (SIGINT) 给远程进程。

通过 PTY 的 stdin 发送 `\x03` 字符。这是优雅终止方式——远程进程可以做清理工作（如 Python 的 finally 块）。不设置 `_cancelled` 标志，保留 readline 循环继续读取进程退出前的最后输出。如果进程不响应，再调用 `cancel()` 强制关闭。

#### `cancel()`

强制关闭 SSH 通道（硬终止）。设置 `_cancelled=True` 并关闭 channel。

```python
# 典型生命周期
handle = ssh.exec_command_streaming("long_running_task", on_stdout=handle_line)

# 方式一：优雅终止
handle.send_ctrl_c()
if handle.is_running:  # 1.5s 后仍然在运行
    handle.cancel()    # 强制关闭

# 方式二：直接强制
handle.cancel()
```

---

### BackgroundManager

`app.py` — 全局背景管理器。加载图片，与暗色混合后应用到所有注册的 Canvas。

```python
class BackgroundManager:
    _blended = None       # 混合后的 PIL Image
    _opacity = 0.15       # 背景透明度
    _path = ""            # 图片路径
    _canvases = []        # 已注册的 Canvas 列表
    _tk_images = {}       # id → PhotoImage（防回收）
    _size_cache = {}      # size → resized PIL Image
```

所有方法均为 `@classmethod`。

#### `register(canvas)`

注册一个 Canvas（PageCanvas 或 tk.Canvas）。注册后背景变更时自动刷新。

```
:param canvas: PageCanvas 或 tk.Canvas 实例
```

#### `unregister(canvas)`

取消注册 Canvas。

```
:param canvas: PageCanvas 或 tk.Canvas 实例
```

#### `set_background(path, opacity)`

设置背景图片并混合。

```
:param path: 图片文件路径，空字符串表示清除
:param opacity: 混合不透明度，0.0 ~ 1.0
```

处理流程：
1. 打开图片 → 转换为 RGBA
2. 与暗色 `(13, 17, 23)` 按 `opacity` 混合（`Image.blend`）
3. 清除缓存
4. 调用 `_refresh()` 更新所有已注册 Canvas

#### `clear()`

清除背景，恢复纯色。

#### `set_fit_mode(mode)` (v2.1.0 新增)

设置背景适配模式并立即刷新所有已注册 Canvas。

```
:param mode: "cover" | "contain" | "fill" | "tile"
```

```python
BackgroundManager.set_fit_mode('contain')  # 完整显示背景图片
```

#### `get_blended(size=None)`

返回混合后的背景图。

```
:param size: 目标尺寸 (width, height)，None 返回原尺寸
:return: PIL Image 或 None
```

带 `_size_cache` 缓存，同尺寸复用已缩放的图像。

#### `apply_to_canvas(canvas)`

将混合背景直接绘制到原始 tk.Canvas（供文件列表/终端等非 pillui Canvas 调用）。

```
:param canvas: tk.Canvas 实例
```

绘制流程：缩放背景到 Canvas 尺寸 → 创建 `ImageTk.PhotoImage` → `canvas.create_image` 以 `bg_image` 标签贴入 → 调用 `tag_lower` 置于最底层。

#### `_refresh()`

内部方法，遍历所有已注册 Canvas 并更新背景：PageCanvas 通过 `set_bg_image` / `set_bg_color` + `render()`；原始 tk.Canvas 通过 `apply_to_canvas`。

---

## 页面 API

### PiManagerApp

`app.py` — 主应用窗口（tk.Tk 子类）。管理侧边栏、页面路由、连接和状态栏。

```python
class PiManagerApp(tk.Tk):
    SIDEBAR_W = 240   # 侧边栏宽度（像素）

    def __init__(self)
```

**构造**：初始化窗口（1100×700，最小 900×600）、侧边栏（PageCanvas + Pillow 组件）、内容区（4 个页面）、状态栏。

**页面路由**：

| 页面 ID | 对应类 | 用途 |
|---------|--------|------|
| `"status"` | `StatusPanel` | 系统状态监控 |
| `"files"` | `FileBrowser` | 文件管理 |
| `"terminal"` | `TerminalPage` | 命令终端 |
| `"settings"` | `SettingsPage` | 应用设置 |

#### `_show_page(page_id)`

切换页面。

```
:param page_id: "status" | "files" | "terminal" | "settings"
```

切换逻辑：隐藏所有页面 → 显示目标页面 → 高亮对应导航按钮 → 若切换到状态页且已连接则自动刷新。

#### `_highlight_nav(page_id)`

高亮当前导航按钮。当前页按钮设为 `"primary"` 样式，其余设为 `"transparent"`。

```
:param page_id: 页面标识符
```

#### `refresh_all_canvases()`

主题/字体变更后刷新所有页面和侧边栏。依次更新：侧边栏背景 → 状态栏颜色 → 内容区背景 → 各页面 `refresh_theme()`。

#### `_apply_background(force=False)`

应用背景图片。从配置读取 `background_path` 和 `background_opacity`，调用 `BackgroundManager.set_background`。

#### 连接管理

| 方法 | 说明 |
|------|------|
| `_auto_connect()` | 从配置读取并自动连接 |
| `_toggle_connection()` | 连接/断开切换（由侧边栏按钮触发） |
| `_do_connect(host, port, username, key_path, password, use_key)` | 在后台线程中执行连接 |
| `_on_connect_result(ok, msg)` | 连接结果回调（主线程），更新侧边栏 UI |
| `_on_disconnected()` | 断开时清理 UI 状态 |

#### `_show_conn_settings()`

打开连接设置对话框（tk.Toplevel），编辑主机、端口、用户名、密钥路径并保存。

#### `_shutdown_pi()` / `_reboot_pi()`

发送关机和重启命令，带确认对话框。

#### `_update_status_clock()`

每 30 秒更新状态栏时钟和连接时长。

#### `_on_close()`

窗口关闭清理：停止侧边栏刷新、取消时钟、停止状态页自动刷新、断开 SSH。

---

### StatusPanel

`status_panel.py` — 系统状态监控面板，全 Pillow 渲染。

```python
class StatusPanel(tk.Frame):
    def __init__(self, master, ssh_client, config=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `ssh_client` | SSHClient | SSH 客户端实例 |
| `config` | dict | 配置字典，None 使用空字典 |

**构造**：创建 PageCanvas 并注册到 `BackgroundManager`，调用 `_build()` 构建所有 UI 组件（系统信息卡片、CPU/温度/内存/磁盘四块卡片、运行信息、刷新按钮）。

#### `refresh()`

手动刷新状态数据（在后台线程中调用 `SSHClient.get_system_status()`，主线程更新 UI）。

#### `_update_ui(s)`

根据 `get_system_status()` 返回的数据更新所有组件显示：

- 主机名、OS 版本、内核版本
- CPU 使用率（进度条 + 百分比文字）
- 温度（带颜色分级：< 50°C 绿色，50-70°C 黄色，> 70°C 红色）
- 内存（进度条 + `used / total MB`）
- 磁盘（进度条 + `used / total MB` 或 GB）
- 运行时间和负载

进度条颜色也按使用率分级（< 50% 绿色，50-80% 黄色，> 80% 红色）。

#### `_show_disconnected()`

显示未连接状态，将所有指示器重置为 "--"。

#### `refresh_theme()`

主题切换时重绘 Canvas。

#### `start_auto_refresh(interval_seconds=None)` / `stop_auto_refresh()`

启动/停止自动刷新。默认每 3 秒一次（由 `config.behavior.refresh_interval` 控制）。使用 `self.after` 循环。

```
:param interval_seconds: 可选，覆盖默认刷新间隔
```

---

### FileBrowser

`file_browser.py` — 文件管理器，支持单栏/双栏模式、文件传输（含进度回调）和远程运行。

```python
class FileBrowser(tk.Frame):
    def __init__(self, master, ssh_client, config=None, app_ref=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `ssh_client` | SSHClient | SSH 客户端实例 |
| `config` | dict | 配置字典，None 使用空字典 |
| `app_ref` | PiManagerApp | 应用引用，用于跨页面跳转（如推送到终端） |

**构造**：构建工具栏、内容区（远程列表 + 可选本地列表）、状态栏。

#### `refresh()`

加载远程当前目录内容（`ssh.list_dir(_cwd)`）。

#### `_toggle_mode()`

切换单栏/双栏模式：

- **单栏 → 双栏**：显示本地文件列表（`LocalFileList`），显示"下载到本地"/"上传到树莓派"按钮，强制几何更新后加载本地目录
- **双栏 → 单栏**：隐藏本地列表和跨栏按钮

#### 文件操作

| 方法 | 说明 |
|------|------|
| `_upload_file()` | 弹出文件选择对话框，上传到远程当前目录 |
| `_download_selected()` | 弹出目录选择对话框，下载远程选中文件 |
| `_download_to_local()` | 双栏模式：从远程栏下载到本地栏当前目录 |
| `_upload_from_local()` | 双栏模式：从本地栏上传到远程当前目录 |
| `_do_transfer(direction, src, dst)` | 执行文件传输（带进度条） |
| `_run_selected()` | 运行远程选中文件：`.py` 用 `python3`，`.sh` 用 `bash`，其它加 `chmod +x`。优先推送到终端页执行 |
| `_mkdir()` | 在远程当前目录创建"新建文件夹" |
| `_delete_selected()` | 删除远程选中文件（带确认对话框） |
| `_rename_selected()` | 重命名远程选中文件（加前缀 `renamed_`） |

#### `refresh_theme()`

主题切换时刷新文件列表。

---

### CanvasFileList / LocalFileList

`file_browser.py` — Canvas 渲染的文件列表（非 pillui，使用原始 tk.Canvas）。

```python
class _CanvasListBase(tk.Frame):
    def __init__(self, master, is_local=False, **kw)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `is_local` | bool | 是否为本地文件列表（影响文件名颜色） |
| `**kw` | — | 传递给 `tk.Frame` |

**CanvasFileList** — 远程文件列表。

```python
class CanvasFileList(_CanvasListBase):
    def __init__(self, master, **kw)
```

**LocalFileList** — 本地文件列表。

```python
class LocalFileList(_CanvasListBase):
    def __init__(self, master, **kw)
```

特有属性和方法：

| 属性/方法 | 说明 |
|-----------|------|
| `current_path` | 当前显示目录路径，初始为 `~` |
| `navigate(path)` | 切换到指定目录 |
| `go_up()` | 切换到上级目录 |
| `refresh()` | 重新加载当前目录 |

本地列表使用 `os.scandir` 加载，通过 `_load_token` 实现线程安全：新请求取消旧请求的结果。

**公共方法和事件钩子**：

| 方法/钩子 | 说明 |
|-----------|------|
| `set_items(items)` | 设置文件列表数据并重绘 |
| `get_selected()` | 返回当前选中项（dict 或 None） |
| `on_click(item, idx)` | 单击回调（需外部赋值） |
| `on_dblclick(item, idx)` | 双击回调（需外部赋值） |
| `on_rightclick(item, idx, event)` | 右键回调（需外部赋值） |
| `refresh_theme()` | 主题切换刷新 |
| `_redraw()` | 重绘文件列表 |

**_redraw 渲染细节**：
- 远程文件名为 `#8BCCFF`，本地文件名为 `#0969DA`
- 目录前缀 `DIR`，文件前缀 `   `
- 名称超长截断加 `..`
- 文件大小格式化：>1MB 用 `M`，>1KB 用 `K`
- 修改时间格式化 `MM-DD HH:MM`
- 虚拟滚动：`_scroll_y` 控制偏移，鼠标滚轮增量 40px
- 选中行高亮使用 `canvas_selection` 颜色

---

### TerminalPage

`terminal_page.py` — 多标签终端页。

```python
class TerminalPage(tk.Frame):
    def __init__(self, master, ssh_client, config=None, app_ref=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `ssh_client` | SSHClient | SSH 客户端实例 |
| `config` | dict | 配置字典，None 使用空字典 |
| `app_ref` | PiManagerApp | 应用引用，供 FileBrowser 推送命令到此页 |

**构造**：构建标签栏、快捷命令栏、终端内容区和底栏。自动创建名为"终端 1"的初始会话。

#### 快捷命令 (QUICK_COMMANDS)

预定义的 10 个快捷命令按钮（两行各 5 个）：

| 按钮 | 命令 |
|------|------|
| 状态 | `top -bn1 \| head -8` |
| 列表 | `ls -lah` |
| 磁盘 | `df -h` |
| 内存 | `free -m` |
| 温度 | `vcgencmd measure_temp` |
| 运行 | `uptime` |
| 网络 | `ip addr show \| grep 'inet '` |
| 进程 | `ps aux --sort=-%mem \| head -8` |
| Python | `python3 --version; pip3 list \| tail -5` |
| 用户 | `whoami; id` |

#### `_add_session(name)`

创建新终端会话和标签。

```
:param name: 会话名称
```

内部流程：创建 `TerminalSession` → 创建 `TerminalTab` → 注册到 `_tabs` → 切换到新标签。

#### `_switch_tab(idx)`

切换活动标签。

```
:param idx: 标签索引
```

#### `_active_tab()`

获取当前激活的 `TerminalTab` 实例。

```
:return: TerminalTab 或 None
```

#### `_run_quick(cmd)`

执行快捷命令：填入当前标签的输入框并发送。

#### `_clear_active()`

清屏当前活动终端。

#### `_copy_all()`

复制当前终端全部输出到系统剪贴板。

#### `refresh_theme()`

主题切换时刷新所有标签。

---

### TerminalSession

`terminal_page.py` — 终端会话数据模型，管理历史记录和回退。

```python
class TerminalSession:
    def __init__(self, name, index)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | str | 会话显示名称 |
| `index` | int | 唯一索引 |

**属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | str | 会话名称 |
| `index` | int | 唯一索引 |
| `history` | deque | 命令历史，最大长度 500（由 `config.behavior.terminal_history_size` 决定） |
| `history_index` | int | 历史回退指针，-1 表示未在回退中 |

#### `add_history(cmd)`

将命令添加到历史记录。

```
:param cmd: 命令字符串（空字符串会被忽略）
```

#### `history_up()`

回退到上一条历史命令。

```
:return: 历史命令字符串，无历史时返回 ""
```

首次调用时从最新历史开始。循环调用逐条回退。到达最旧命令时停滞。

#### `history_down()`

前进到下一条历史命令。

```
:return: 历史命令字符串，已到最新时返回 ""
```

到达最新命令后再调用会清空输入框（返回 `""`）。

#### `reset_history()`

重置历史回退指针为 -1（返回最新位置）。

---

### TerminalTab

`terminal_page.py` — 单个终端标签页，支持流式和阻塞双模式执行。

```python
class TerminalTab(tk.Frame):
    def __init__(self, master, ssh_client, session, **kw)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `ssh_client` | SSHClient | SSH 客户端实例 |
| `session` | TerminalSession | 关联的会话数据模型 |

**构造**：创建 `CanvasTerminalOutput` 输出区、输入栏（含 `$` 提示符、Entry、发送/清屏/流式开关按钮）。

#### `_toggle_stream()`

切换流式/阻塞模式。流式开启时按钮显示"流式:开"（绿色），关闭时显示"流式:关"（灰色）。

#### `_execute()`

执行输入命令。流程：
1. 获取输入 → 添加到历史
2. 输出 `$ {cmd}` 提示
3. 检查连接状态
4. 根据流式开关选择 `_exec_streaming` 或 `_exec_blocking`

#### `_exec_blocking(cmd)`

阻塞模式：后台线程调用 `ssh.exec_command`，主线程逐行显示 stdout 和 stderr。

#### `_exec_streaming(cmd)`

流式模式：后台线程调用 `ssh.exec_command_streaming`，实时逐行显示输出。发送按钮变为"停止"（红色）。

#### `_stop_streaming()`

发送 Ctrl+C (SIGINT)，1.5 秒后若仍在运行则强制关闭。

#### `_finish_streaming(generation=None)`

流式执行完成：恢复按钮状态。若 `generation` 与当前 `_exec_generation` 不匹配则忽略（防止过时回调）。

#### `_on_ctrl_c(event)`

Ctrl+C 快捷键处理：若流式运行中则发送中断信号，返回 `"break"` 阻止 tk 默认行为。

#### `_on_up(event)` / `_on_down(event)`

上下键浏览命令历史。

#### `focus_input()`

聚焦输入框。

#### `refresh_theme()`

主题切换时刷新输出区。

---

### CanvasTerminalOutput

`terminal_page.py` — Canvas 渲染的虚拟终端输出（非 pillui）。

```python
class CanvasTerminalOutput(tk.Frame):
    def __init__(self, master, **kw)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |

**构造**：创建内部 tk.Canvas + 垂直 Scrollbar，注册到 `BackgroundManager`。

#### `insert(pos, text, tag=None)`

在指定位置插入文字。

```
:param pos: 插入位置（当前仅追加到末尾，忽略此参数）
:param text: 文字内容（自动换行由每行单独 insert 实现）
:param tag: "stderr"（红色 #FF6B6B）、"prompt"（主题强调色）或 None（默认文字色）
```

#### `delete(start, end=None)`

清空所有行并重置滚动位置。

#### `see(pos)`

滚动到底部。

#### `get(start, end=None)`

获取全部输出文本（用 `\n` 连接所有行）。

```
:return: str — 全部输出文本
```

#### `_redraw()`

使用原始 tk.Canvas 重绘终端输出：
- 虚拟滚动：`_scroll_y` 控制偏移
- 行高 18px，每行最多 120 字符截断
- 每行使用独立 `create_text`，颜色按 tag 区分
- 鼠标滚轮增量 30px，滚轮操作时 `_auto_scroll=False`

#### `refresh_theme()`

主题切换时更新 Canvas 背景色并重绘。

---

### SettingsPage

`settings_page.py` — 应用设置页面，全 Pillow 渲染。

```python
class SettingsPage(tk.Frame):
    def __init__(self, master, config, ssh_client=None, app_ref=None)
```

**构造参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `master` | tk.Widget | 父容器 |
| `config` | dict | 配置字典（直接修改） |
| `ssh_client` | SSHClient | SSH 客户端实例（可选） |
| `app_ref` | PiManagerApp | 应用引用，用于触发主题/背景/缩放变更 |

**构造**：创建 PageCanvas，依次构建 4 个卡片：外观、背景、行为、关于。

#### 设置分类

**1. 外观设置 (`_build_appearance_card`)**

| 设置项 | 控件 | 绑定变量 | 说明 |
|--------|------|---------|------|
| 主题模式 | PillowOptionMenu | `tk.StringVar` | dark / light |
| 颜色主题 | PillowOptionMenu | `tk.StringVar` | green / blue / dark-blue |
| 字体缩放 | PillowSlider | `tk.DoubleVar` | 0.8 ~ 1.5，7 步 |

`_on_theme_change`：调用 `ThemeColors.set_mode` → 200ms 延迟重新应用背景 → 300ms 延迟刷新所有 Canvas。

`_on_scale_change`：更新百分比标签 → `ThemeColors.set_font_scale` → 防抖 100ms 后刷新所有 Canvas。

**2. 背景设置 (`_build_background_card`)**

| 设置项 | 控件 | 说明 |
|--------|------|------|
| 当前背景 | PillowLabel | 显示文件名或"未设置" |
| 选择图片 | PillowButton | 弹出文件选择对话框 |
| 清除背景 | PillowButton | 调用 `BackgroundManager.clear()` |
| 透明度 | PillowSlider | 0.05 ~ 0.5，9 步 |

`_on_opacity_change`：实时更新透明度并重新应用背景（`_app._apply_background(force=True)`）。

**3. 行为设置 (`_build_behavior_card`)**

| 设置项 | 控件 | 绑定变量 | 说明 |
|--------|------|---------|------|
| 自动连接 | PillowCheckBox | `tk.BooleanVar` | 启动时自动连接 |
| 刷新间隔 | PillowSlider | `tk.IntVar` | 1 ~ 30 秒，29 步 |
| 删除确认 | PillowCheckBox | `tk.BooleanVar` | 删除前弹出确认框 |

**4. 关于 (`_build_about_card`)**

显示版本号、技术栈说明（Python + tkinter + Pillow + Paramiko）、双主题信息。包含"保存所有设置"按钮。

#### `_save_all()`

收集所有设置控件的当前值，更新 `config` 字典，保存到文件。

保存字段：`appearance.theme`、`appearance.color_theme`、`appearance.font_scale`、`appearance.background_opacity`、`behavior.auto_connect`、`behavior.refresh_interval`、`behavior.confirm_before_delete`。

#### `refresh_theme()`

主题切换时重绘设置页 Canvas。

---

## 入口文件

`main.py` — 应用入口。

```python
def main():
    ThemeColors.set_mode('dark')
    ThemeColors.set_font_scale(1.0)
    app = PiManagerApp()
    app.mainloop()

if __name__ == '__main__':
    main()
```

初始化主题为深色模式、字体缩放 1.0 倍，启动 `PiManagerApp` 主窗口。
