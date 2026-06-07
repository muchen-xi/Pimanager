"""诊断 BackgroundManager 是否对 CTkTextbox 等控件生效"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import customtkinter as ctk
from PIL import Image, ImageTk
import tkinter as tk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.geometry("800x600")
root.title("Background Patch Test")

# 创建一个简单的背景图
bg_img = Image.new("RGBA", (800, 600), (255, 100, 50, 100))
for x in range(0, 800, 40):
    for y in range(0, 600, 40):
        bg_img.putpixel((x, y), (255, 255, 255, 50))
bg_img.save("test_bg.png")

# ---- 手动应用 BackgroundManager ----
from pimanager.app import BackgroundManager

# 内容区
content = ctk.CTkFrame(root, fg_color="transparent")
content.pack(fill="both", expand=True, padx=20, pady=20)

# 测试用的各种控件
frame1 = ctk.CTkFrame(content, fg_color="transparent", height=100)
frame1.pack(fill="x", pady=5)
ctk.CTkLabel(frame1, text="CTkFrame (transparent) - should show bg").pack(pady=10)

frame2 = ctk.CTkFrame(content, fg_color=("gray85", "gray20"), height=100)
frame2.pack(fill="x", pady=5)
ctk.CTkLabel(frame2, text="CTkFrame (solid color) - should show bg after patch").pack(pady=10)

textbox = ctk.CTkTextbox(content, height=120, fg_color="#0D1117")
textbox.pack(fill="x", pady=5)
textbox.insert("1.0", "CTkTextbox (terminal style) - should show bg through text area")

entry = ctk.CTkEntry(content, fg_color="#0D1117", placeholder_text="CTkEntry - should show bg")
entry.pack(fill="x", pady=5)

btn_frame = ctk.CTkFrame(content, fg_color="transparent")
btn_frame.pack(fill="x", pady=5)
btn = ctk.CTkButton(btn_frame, text="CTkButton - should show bg behind")
btn.pack(side="left", padx=5)
opt = ctk.CTkOptionMenu(btn_frame, values=["A", "B", "C"])
opt.pack(side="left", padx=5)
chk = ctk.CTkCheckBox(btn_frame, text="CheckBox")
chk.pack(side="left", padx=5)
sld = ctk.CTkSlider(btn_frame)
sld.pack(side="left", padx=5)
sld.set(0.5)

# Setup BackgroundManager
BackgroundManager.setup(content)
BackgroundManager.set_background("test_bg.png", 0.15)

# 调试：检查 _on_widget_draw 是否被调用
original_on_draw = BackgroundManager._on_widget_draw
call_count = [0]

def debug_on_draw(widget):
    call_count[0] += 1
    cls_name = widget.__class__.__name__
    has_canvas = hasattr(widget, '_canvas')
    is_desc = BackgroundManager._is_descendant_of_content(widget)
    print(f"[_on_widget_draw #{call_count[0]}] {cls_name} canvas={has_canvas} descendant={is_desc} enabled={BackgroundManager._enabled} bg_tk={BackgroundManager._bg_tk_full is not None}")
    if has_canvas:
        c = widget._canvas
        if c.winfo_exists():
            print(f"  canvas size: {c.winfo_width()}x{c.winfo_height()}")
            # Check inner_parts fill BEFORE our change
            fills = c.itemcget("inner_parts", "fill") if "inner_parts" in str(c.find_all()) else "NO inner_parts"
            print(f"  inner_parts fill: {fills}")
    original_on_draw(widget)
    # Check inner_parts fill AFTER our change
    if has_canvas and widget._canvas.winfo_exists():
        try:
            fills_after = widget._canvas.itemcget("inner_parts", "fill")
            has_bg = widget._canvas.find_withtag("bg_image")
            print(f"  AFTER: inner_parts fill='{fills_after}' bg_images={len(has_bg)}")
        except:
            pass

BackgroundManager._on_widget_draw = debug_on_draw

print("=" * 60)
print("Patched classes:")
for cls, orig in BackgroundManager._original_draws.items():
    print(f"  {cls.__name__} -> patched")
print("=" * 60)

root.after(1000, lambda: print("\n--- After 1 second ---"))
root.after(3000, lambda: print(f"\nTotal _on_widget_draw calls: {call_count[0]}"))
root.after(5000, lambda: root.destroy())

root.mainloop()
