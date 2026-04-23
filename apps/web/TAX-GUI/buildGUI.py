# -*- coding: utf-8 -*-
import locale
from cx_Freeze import setup, Executable
import os

# Set the locale to avoid encoding issues
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# Readme file might cause issues if not read with proper encoding
def readme():
    with open('README.txt', encoding='utf-8') as f:
        return f.read()

# Ensure the environment variable is set to avoid encoding issues
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Additional build options
build_exe_options = {
    "packages": ["wx", "json", "requests", "tkinter"],
    "excludes": [],
    "include_files": ["log.json", "config.ini", "aqua_logo-min.png", "bg-min.png"]  # Ensure assets are included
}

setup(
    name="AQUA AUDIT",
    version="1.0",
    description="AQUA AUDIT",
    long_description=readme(),
    options={"build_exe": build_exe_options},
    executables=[Executable("mvc.py", base="gui")]
)
