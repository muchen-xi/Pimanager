import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Wait for the main app to write its debug log
time.sleep(3)

log_path = os.path.join(os.path.dirname(__file__), "debug.log")
if os.path.exists(log_path):
    with open(log_path, encoding='utf-8') as f:
        content = f.read()
    print(content if content else "(empty file)")
else:
    print("Log file not found")
