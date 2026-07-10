"""
PiManager 主题颜色系统（NiceGUI 版）
- 保留 token 系统用于 CSS 变量注入
- NiceGUI dark_mode() 控制亮暗切换
- 通过 CSS 自定义属性实现全应用主题一致
"""
from nicegui import ui

# ─── 颜色加速器（主题色 accent） ───────────────────────────
_COLOR_ACCENTS = {
    'green': {
        'dark': {'accent': '#4CAF50', 'accent_hover': '#3A7A3A', 'accent_dim': '#2B5B2B'},
        'light': {'accent': '#2DA44E', 'accent_hover': '#2C974B', 'accent_dim': '#DCF5E4'},
    },
    'blue': {
        'dark': {'accent': '#58A6FF', 'accent_hover': '#1F6FEB', 'accent_dim': '#1A3A5C'},
        'light': {'accent': '#0969DA', 'accent_hover': '#0550AE', 'accent_dim': '#DDF4FF'},
    },
    'dark-blue': {
        'dark': {'accent': '#79C0FF', 'accent_hover': '#1F6FEB', 'accent_dim': '#0D2B4A'},
        'light': {'accent': '#0550AE', 'accent_hover': '#033D8B', 'accent_dim': '#DDF4FF'},
    },
}

# ─── 深色 / 浅色调色板 ─────────────────────────────────
_DARK = {
    'bg': '#0D1117',
    'bg_card': '#161B22',
    'bg_sidebar': '#0D1117',
    'text': '#C9D1D9',
    'text_secondary': '#8B949E',
    'danger': '#8B0000',
    'danger_hover': '#A00000',
    'warning': '#FFB347',
    'warning_strong': '#FF4444',
    'card_border': '#30363D',
    'separator': '#21262D',
    'input_bg': '#21262D',
    'status_ok': '#4CAF50',
    'hover': '#1C2128',
    'row_hover': '#161B22',
}

_LIGHT = {
    'bg': '#FFFFFF',
    'bg_card': '#F6F8FA',
    'bg_sidebar': '#F6F8FA',
    'text': '#24292F',
    'text_secondary': '#656D76',
    'danger': '#CF222E',
    'danger_hover': '#A40E26',
    'warning': '#D4A72C',
    'warning_strong': '#CF222E',
    'card_border': '#D0D7DE',
    'separator': '#D8DEE4',
    'input_bg': '#FFFFFF',
    'status_ok': '#2DA44E',
    'hover': '#F3F4F6',
    'row_hover': '#EBEDF0',
}

# ─── CSS 模板 ──────────────────────────────────────────
_STYLE_TPL = """/* PiManager Theme — auto-generated */
:root {{
  --pm-bg: {bg};
  --pm-bg-card: {bg_card};
  --pm-bg-sidebar: {bg_sidebar};
  --pm-text: {text};
  --pm-text-secondary: {text_secondary};
  --pm-accent: {accent};
  --pm-accent-hover: {accent_hover};
  --pm-accent-dim: {accent_dim};
  --pm-danger: {danger};
  --pm-danger-hover: {danger_hover};
  --pm-warning: {warning};
  --pm-warning-strong: {warning_strong};
  --pm-card-border: {card_border};
  --pm-separator: {separator};
  --pm-input-bg: {input_bg};
  --pm-status-ok: {status_ok};
  --pm-hover: {hover};
  --pm-row-hover: {row_hover};
  --pm-font-scale: {font_scale};
}}

/* ── Dark mode overrides ── */
.body--dark {{
  --pm-bg: #0D1117;
  --pm-bg-card: #161B22;
  --pm-text: #C9D1D9;
  --pm-text-secondary: #8B949E;
  /* …其余深色值在运行时注入 */
}}

/* ── Light mode overrides ── */
.body--light {{
  --pm-bg: #FFFFFF;
  --pm-bg-card: #F6F8FA;
  --pm-text: #24292F;
}}

/* ── Sidebar tweaks ── */
.pm-sidebar {{
  background: var(--pm-bg-sidebar);
  border-right: 1px solid var(--pm-separator);
}}

/* ── Status cards ── */
.pm-stat-card {{
  background: var(--pm-bg-card);
  border: 1px solid var(--pm-card-border);
  border-radius: 8px;
  padding: 12px 16px;
}}
.pm-stat-card .title {{ color: var(--pm-text-secondary); font-size: 12px; }}
.pm-stat-card .value {{ color: var(--pm-text); font-size: 24px; font-weight: 700; }}

/* ── Terminal log ── */
.pm-terminal {{
  background: #0A0E14;
  color: #E6E1CF;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  border-radius: 6px;
  padding: 8px;
}}

/* ── Misc ── */
.pm-text-mono {{ font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; }}
.pm-divider {{ border-top: 1px solid var(--pm-separator); }}
.pm-sidebar-btn {{ width: 100%; justify-content: flex-start; }}
"""


class ThemeColors:
    """主题颜色系统（NiceGUI 适配版）。

    用法:
        ThemeColors.set_mode('dark')
        ThemeColors.set_color_theme('green')
        ThemeColors.set_font_scale(1.0)
        ThemeColors.apply()          # 注入 CSS + 切换 dark_mode
        hex_color = ThemeColors.get('accent')   # 取色
    """
    _mode = 'Dark'
    _color_theme = 'green'
    _font_scale = 1.0
    _injected = False   # 标记 CSS 是否已注入

    # ─── 模式 / 主题 / 缩放 ─────────────────────────────

    @classmethod
    def set_mode(cls, mode: str):
        cls._mode = 'Dark' if str(mode).lower() == 'dark' else 'Light'

    @classmethod
    def get_mode(cls) -> str:
        return cls._mode

    @classmethod
    def toggle_mode(cls):
        cls.set_mode('light' if cls._mode == 'Dark' else 'dark')

    @classmethod
    def set_color_theme(cls, name: str):
        if name in _COLOR_ACCENTS:
            cls._color_theme = name

    @classmethod
    def get_color_theme(cls) -> str:
        return cls._color_theme

    @classmethod
    def set_font_scale(cls, scale: float):
        cls._font_scale = float(scale)

    @classmethod
    def get_font_scale(cls) -> float:
        return cls._font_scale

    # ─── 取色 ──────────────────────────────────────────

    @classmethod
    def get(cls, key: str) -> str:
        """获取当前主题下的颜色值。"""
        palette = _DARK if cls._mode == 'Dark' else _LIGHT
        # accent 覆盖
        accent_set = _COLOR_ACCENTS.get(cls._color_theme, {})
        mode_key = 'dark' if cls._mode == 'Dark' else 'light'
        if key in accent_set.get(mode_key, {}):
            return accent_set[mode_key][key]
        return palette.get(key, '#000000')

    @classmethod
    def fg_hover(cls, key: str):
        """返回 (fg_color, hover_color) 元组。"""
        return cls.get(key), cls.get(key + '_hover')

    # ─── NiceGUI 集成 ──────────────────────────────────

    @classmethod
    def apply(cls):
        """应用到 NiceGUI：注入 CSS + 设置 dark_mode。"""
        palette = _DARK if cls._mode == 'Dark' else _LIGHT
        accent = _COLOR_ACCENTS.get(cls._color_theme, {})
        mk = 'dark' if cls._mode == 'Dark' else 'light'
        a = accent.get(mk, {})

        css = _STYLE_TPL.format(
            bg=palette['bg'],
            bg_card=palette['bg_card'],
            bg_sidebar=palette['bg_sidebar'],
            text=palette['text'],
            text_secondary=palette['text_secondary'],
            accent=a.get('accent', '#4CAF50'),
            accent_hover=a.get('accent_hover', '#3A7A3A'),
            accent_dim=a.get('accent_dim', '#2B5B2B'),
            danger=palette['danger'],
            danger_hover=palette.get('danger_hover', palette['danger']),
            warning=palette['warning'],
            warning_strong=palette['warning_strong'],
            card_border=palette['card_border'],
            separator=palette['separator'],
            input_bg=palette['input_bg'],
            status_ok=palette['status_ok'],
            hover=palette['hover'],
            row_hover=palette['row_hover'],
            font_scale=cls._font_scale,
        )

        if cls._injected:
            # 更新已有的 <style> 块
            ui.run_javascript(f'document.getElementById("pm-theme").textContent = {css!r};')
        else:
            ui.add_head_html(f'<style id="pm-theme">{css}</style>')
            cls._injected = True

        # 切换 NiceGUI dark_mode
        ui.dark_mode().value = (cls._mode == 'Dark')

    # ─── 缩放字体 ───────────────────────────────────────

    @classmethod
    def scaled_font(cls, family: str, size: int):
        return f'{int(size * cls._font_scale)}px {family}'
