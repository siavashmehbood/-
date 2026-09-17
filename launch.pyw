import os, runpy
ROOT = r"C:\Users\GREEN-LEAF\Desktop\ایران"
os.chdir(ROOT)
runpy.run_path(os.path.join(ROOT, "gui_pyside6.py"), run_name="__main__")