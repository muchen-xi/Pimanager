# 更新日志

## v2.1.1 (2026-06-19)

### 紧急修复
- 修复：文字周围出现小框 — 清除全部 38 个 emoji 字符（Pillow 无字体回退，emoji 渲染为豆腐块）
- 修复：设置页完全无法渲染 — PillowCard 的 `border="gray30"` 传入 `hex_to_rgba()` 导致崩溃

## v2.1.0 (2026-06-19)

本次更新共修复 37 个 bug，涵盖主题系统、渲染引擎和背景图片三大领域。

### 主题系统 (15 项)

- **修复**：亮色主题下所有 PillUI 组件颜色不更新 — 全组件硬编码暗色调色板 → 为 Button/Label/Card/ProgressBar/Slider/CheckBox/OptionMenu/PageCanvas 添加 `apply_theme()` 方法，从 ThemeColors 动态读取颜色令牌
- **修复**：`toggle_mode()` 中两分支均设为 `mode='dark'`，导致无法切换到亮色模式 — 已修正为正确切换 Dark/Light
- **新增**：颜色主题功能正式激活 — `set_color_theme()` / `get_color_theme()` 方法，支持 green/blue/dark-blue 三色强调色系
- **新增**：设置页添加"颜色主题"下拉菜单（green/blue/dark-blue），与"主题模式"并列
- **修复**：启动时忽略保存的主题设置 — `main.py` 现从配置读取 `appearance.theme` 和 `appearance.color_theme` 并应用
- **修复**：主题切换时 300ms 闪屏 — 移除延迟调度，改为 `refresh_all_canvases()` 同步重绘
- **修复**：亮色模式下进度条轨道色仍为暗色 `#1A1A1A` — 改为动态读取 `scrollbar_track` 令牌
- **修复**：亮色模式下 PillowOptionMenu 背景/文字/边框硬编码暗色值
- **修复**：亮色模式下 PillowSlider 轨道和刻度颜色硬编码
- **修复**：亮色模式下 PillowCheckBox 勾号颜色硬编码为白色
- **修复**：亮色模式下 PillowCard 默认 `fill` 硬编码为 `#161B22`
- **修复**：亮色模式下 PillowButton `transparent` 样式 hover 色硬编码 `#333333`
- **修复**：侧边栏背景色在主题切换后不更新
- **修复**：状态栏颜色在主题切换后不更新
- **修复**：PillowOptionMenu 弹出菜单使用硬编码颜色 — 改为从 ThemeColors 动态获取

### 渲染引擎 (14 项)

- **修复**：文字周围出现暗色小框（Pillow 在透明 RGBA 图层上绘字产生抗锯齿暗晕）— 改为两阶段渲染：RGB 不透明层绘字 → 分离 alpha → 合成到透明层
- **修复**：`font_scale` 参数未传入组件 `draw()` 调用 — 所有组件 `draw()` 新增 `font_scale` 参数，PageCanvas.render() 传入 `self._font_scale`
- **修复**：字体缩放滑块拖动后文字大小无变化 — 组件内字号计算改为 `int(base_size * font_scale)`
- **优化**：hover 交互延迟 — `mark_dirty()` 渲染调度从 `after_idle` 改为 `after(16ms)`，实现 60fps hover 反馈
- **修复**：粗体字体（`msyhbd`）不存在时回退到 `load_default()` 导致中文显示为方框 — 回退改为 `get_font('msyh', size)`
- **修复**：状态页自动刷新在切换到其他页面后仍持续执行 — 页面切换时 `stop_auto_refresh()`，切回时 `start_auto_refresh()`
- **修复**：无限重试循环 — `SSHClient._auto_reconnect()` 添加最大重试 3 次 + 指数退避 1s/2s/4s
- **修复**：字形 bearing 导致文字视觉未居中 — `draw_text_aligned()` 使用 `font.getbbox()` 替代 `draw.textbbox()` 获取准确包围盒
- **修复**：组件 `draw()` 返回等大图层造成大量临时内存分配 — 添加 early return 优化
- **修复**：`composite_layer()` 偏移叠加时 alpha 通道处理不当
- **修复**：`hex_to_rgba()` 对 3 位短 hex 颜色（如 `#FFF`）处理失败
- **修复**：多行文字行高计算不一致 — 统一为 `font_size + 6`
- **修复**：`PillowScrollFrame.render()` 组件坐标临时偏移后未在异常时恢复
- **修复**：PillowLabel 超长文字溢出边界 — 添加按宽度截断

### 背景图片 (8 项)

- **新增**：`fit_image()` 函数（`pillui/image_utils.py`）— 支持 4 种适配模式：cover（裁剪填充，默认）/ contain（完整显示）/ fill（拉伸）/ tile（平铺）
- **新增**：设置页背景卡片添加"适配模式"下拉菜单 — 用户可选择 cover/contain/fill/tile
- **新增**：配置键 `appearance.background_fit_mode`（默认 `"cover"`）— 保存/加载/验证均已支持
- **新增**：`BackgroundManager.set_fit_mode(mode)` 类方法 — 模式切换时清除缓存并刷新所有 Canvas
- **修复**：亮色模式下背景混合底图固定为深色 `(13, 17, 23)` — 改为 `ThemeColors.get('bg')` 动态色
- **修复**：背景缓存 key 不区分适配模式 — 扩展为 `(size, fit_mode)` 元组
- **修复**：背景图片加载失败静默忽略 — 添加 `messagebox.showerror` 用户可见错误弹窗
- **修复**：BackgroundManager 未使用的 dead registration 清理
