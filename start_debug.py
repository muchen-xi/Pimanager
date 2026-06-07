"""直接写日志文件诊断 app 启动"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG = os.path.join(os.path.dirname(__file__), "startup.log")

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    # Also try stderr
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()

log("=== Starting app ===")

import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

from pimanager.app import PiManagerApp
log("PiManagerApp imported")

try:
    app = PiManagerApp()
    log("App created")
    app.mainloop()
    log("App exited normally")
except Exception as e:
    log(f"CRASH: {e}")
    import traceback
    log(traceback.format_exc())
