"""
Phase 1 测试 — 验证 pillui 组件库基础功能
运行: python test_pillui.py
"""
import tkinter as tk
import sys
import os

# 确保 pillui 可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pillui import PageCanvas, PillowButton, PillowLabel, PillowProgressBar


def main():
    root = tk.Tk()
    root.title("pillui Phase 1 测试")
    root.geometry('600x400')
    root.configure(bg='#0D1117')

    # 创建 PageCanvas
    canvas = PageCanvas(root, width=600, height=400, bg='#0D1117')
    canvas.pack(fill='both', expand=True)

    # 添加标题标签
    title = PillowLabel("pillui 组件库测试", 20, 20, 400, 30,
                        font_size=18, color='#4CAF50', weight='bold')
    canvas.add('title', title)

    # 添加计数标签
    count = 0
    count_label = PillowLabel(f"点击次数: {count}", 20, 70, 200, 24,
                              font_size=13, color='#C9D1D9')
    canvas.add('count', count_label)

    # 添加按钮
    def on_click():
        nonlocal count
        count += 1
        lbl = canvas.get('count')
        if lbl:
            lbl.set_text(f"点击次数: {count}")

        # 切换按钮样式
        if count % 5 == 0:
            btn = canvas.get('test_btn')
            if btn:
                btn.set_text(f"哇! {count}次了!")
                btn.set_style('danger')
        else:
            btn = canvas.get('test_btn')
            if btn:
                btn.set_text(f"点我 ({count})")
                btn.set_style('primary' if count % 3 != 0 else 'transparent')

    btn1 = PillowButton("点我 (0)", 20, 110, 140, 40, command=on_click)
    canvas.add('test_btn', btn1)

    btn2 = PillowButton("透明按钮", 180, 110, 140, 40,
                        style='transparent',
                        command=lambda: print("透明按钮被点击"))
    canvas.add('btn2', btn2)

    btn3 = PillowButton("危险按钮", 340, 110, 140, 40,
                        style='danger',
                        command=lambda: print("危险按钮被点击"))
    canvas.add('btn3', btn3)

    # 进度条
    bar = PillowProgressBar(20, 180, 350, 24)
    bar.set(0.6)
    canvas.add('bar', bar)

    pct_label = PillowLabel('60%', 390, 180, 60, 24,
                            font_size=13, color='#C9D1D9')
    canvas.add('bar_pct', pct_label)

    # 多行标签
    multi = PillowLabel("这是多行标签测试\n第二行文字\n第三行更长的文字",
                        20, 220, 300, 80, font_size=12, color='#8B949E',
                        align='left')
    canvas.add('multi', multi)

    print("[OK] pillui Phase 1 测试窗口启动中...")
    print("    点击按钮看交互效果")
    print("    关闭窗口退出")

    root.mainloop()


if __name__ == '__main__':
    main()
