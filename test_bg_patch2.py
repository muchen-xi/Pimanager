"""诊断2: 模拟 app 启动流程测试 _apply_background 完整路径"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import customtkinter as ctk
from PIL import Image, ImageTk
import tkinter as tk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.geometry("800x600")

# 创建测试背景图
bg = Image.new("RGBA", (800, 600), (255, 80, 30, 180))
for x in range(0, 800, 20):
    for y in range(0, 600, 20):
        bg.putpixel((x, y), (255, 255, 255, 60))
bg.save("test_bg.png")

# 模拟 app.py 的结构
content = ctk.CTkFrame(root, fg_color="transparent")
content.pack(fill="both", expand=True, padx=10, pady=10)

frame1 = ctk.CTkFrame(content, height=80, fg_color=("gray85","gray20"))
frame1.pack(fill="x", pady=4)
ctk.CTkLabel(frame1, text="Status Frame (solid bg)").pack(pady=10)

frame2 = ctk.CTkFrame(content, fg_color="transparent", height=80)
frame2.pack(fill="x", pady=4)
ctk.CTkLabel(frame2, text="Transparent Frame").pack(pady=10)

textbox = ctk.CTkTextbox(content, height=100, fg_color="#0D1117")
textbox.pack(fill="x", pady=4)
textbox.insert("1.0", "Terminal - CTkTextbox with solid bg")

entry = ctk.CTkEntry(content, fg_color="#0D1117", placeholder_text="CTkEntry")
entry.pack(fill="x", pady=4)

# ==== 模拟 app.py 的流程 ====
from pimanager.app import BackgroundManager

print("Step 1: setup()")
BackgroundManager.setup(content)

print("\nStep 2: update() + update_idletasks() to force layout")
root.update()
root.update_idletasks()

print(f"\nPost-update sizes:")
print(f"  content: {content.winfo_width()}x{content.winfo_height()} (root: {content.winfo_rootx()},{content.winfo_rooty()})")
print(f"  frame1: {frame1.winfo_width()}x{frame1.winfo_height()} (root: {frame1.winfo_rootx()},{frame1.winfo_rooty()})")
print(f"  frame2: {frame2.winfo_width()}x{frame2.winfo_height()} (root: {frame2.winfo_rootx()},{frame2.winfo_rooty()})")
print(f"  textbox: {textbox.winfo_width()}x{textbox.winfo_height()} (root: {textbox.winfo_rootx()},{textbox.winfo_rooty()})")
print(f"  entry: {entry.winfo_width()}x{entry.winfo_height()} (root: {entry.winfo_rootx()},{entry.winfo_rooty()})")

print("\nStep 3: set_background()")
BackgroundManager.set_background("test_bg.png", 0.15)

print(f"\nAfter set_background:")
print(f"  _bg_tk_full size: {BackgroundManager._bg_tk_full.width()}x{BackgroundManager._bg_tk_full.height()}")
print(f"  _enabled: {BackgroundManager._enabled}")

# 手动检查 canvas 状态
for name, widget in [("frame1", frame1), ("frame2", frame2), ("textbox", textbox), ("entry", entry)]:
    c = widget._canvas
    inner = c.find_withtag("inner_parts")
    bg_imgs = c.find_withtag("bg_image")
    fill = c.itemcget("inner_parts", "fill") if inner else "no tag"
    print(f"  {name}: canvas={c.winfo_width()}x{c.winfo_height()}, inner_parts fill={fill}, bg_images={len(bg_imgs)}")

# 强制再触发一次 draw
print("\nStep 4: Force _draw() again on all widgets")
for name, widget in [("frame1", frame1), ("frame2", frame2), ("textbox", textbox), ("entry", entry)]:
    widget._draw()
    c = widget._canvas
    inner = c.find_withtag("inner_parts")
    bg_imgs = c.find_withtag("bg_image")
    fill = c.itemcget("inner_parts", "fill") if inner else "no tag"
    print(f"  {name}: canvas={c.winfo_width()}x{c.winfo_height()}, inner_parts fill={fill}, bg_images={len(bg_imgs)}")

root.after(2000, root.destroy)
root.mainloop()
