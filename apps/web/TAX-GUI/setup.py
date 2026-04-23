import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
# Ensure assets folder is included for cx_Freeze compatibility
build_exe_options = {
    "packages": ["wx", "wx.html2", "json", "requests", "tkinter", "os", "base64", "dotenv"],
    "include_files": [
        ("assets", "assets"),  # Include assets folder (required for images)
        ("log.json", "log.json"),  # Include log.json
        (".env", ".env"),  # Include .env file
    ],
    "excludes": []
}

# GUI applications require a different base on Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="AQUA",
    version="1.0",
    description="AQUA Application",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "mvc.py",
            base=base,
            target_name="AQUA.exe",
            icon="assets/aqua_logo.ico"  # Optional: add your icon here
        )
    ]
) 