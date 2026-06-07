"""诊断3: 可视化验证 - 打开窗口看 bg 是否真的显示"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import customtkinter as ctk
from PIL import Image, ImageTk
import tkinter as tk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

root = ctk.CTk()
root.geometry("800x600")
root.title("Visual Test")

# 创建一个显眼的背景
bg = Image.new("RGBA", (800, 600), (255, 0, 0, 255))  # 纯红
for x in range(0, 800, 50):
    for y in range(0, 600, 50):
        if (x//50 + y//50) % 2 == 0:
            bg.putpixel((x, y), (0, 255, 0, 255))
bg.save("test_bg_vivid.png")

content = ctk.CTkFrame(root, fg_color="transparent")
content.pack(fill="both", expand=True, padx=20, pady=20)

# 测试1: 默认 solid 的 frame
f1 = ctk.CTkFrame(content, height=80)
f1.pack(fill="x", pady=5)
ctk.CTkLabel(f1, text="Solid frame - BG should show through").pack(pady=10)

# 测试2: transparent frame
f2 = ctk.CTkFrame(content, fg_color="transparent", height=80)
f2.pack(fill="x", pady=5)
ctk.CTkLabel(f2, text="Transparent frame - BG should show through").pack(pady=10)

# 测试3: 终端风格 textbox
tb = ctk.CTkTextbox(content, height=100, fg_color="#0D1117")
tb.pack(fill="x", pady=5)
tb.insert("1.0", "Terminal: BG should show through or behind")

# 测试4: entry
e = ctk.CTkEntry(content, fg_color="#0D1117", placeholder_text="Entry: BG should show through")
e.pack(fill="x", pady=5)

# 测试5: buttons
bf = ctk.CTkFrame(content, fg_color="transparent")
bf.pack(fill="x", pady=5)
ctk.CTkButton(bf, text="Button").pack(side="left", padx=3)
ctk.CTkOptionMenu(bf, values=["A","B","C"]).pack(side="left", padx=3)

# 强制布局
root.update()
root.update_idletasks()

print(f"Content size: {content.winfo_width()}x{content.winfo_height()}")

from pimanager.app import BackgroundManager

# 方式A: 10% 透明度（和用户设置一样）
BackgroundManager.setup(content)
BackgroundManager.set_background("test_bg_vivid.png", 0.10)
print(f"refs={len(BackgroundManager._refs)}")

# 检查 canvas inner_parts
for name, w in [("f1", f1), ("f2", f2), ("tb", tb), ("e", e)]:
    c = w._canvas
    inner = c.find_withtag("inner_parts")
    bg_imgs = c.find_withtag("bg_image")
    fill = c.itemcget("inner_parts", "fill") if inner else "no tag"
    cv_bg = c.cget("bg")
    print(f"  {name}: canvas={c.winfo_width()}x{c.winfo_height()}, canvas_bg='{cv_bg}', inner_parts_fill='{fill}', bg_images={len(bg_imgs)}")

print("\n--- Now close the window to continue ---")
root.after(5000, root.destroy)
root.mainloop()
