import os
import sys
import shutil
import subprocess

print("=" * 31)
print("Android Archiver - Build Script")
print("=" * 31)

SCRIPT_NAME = "Android-Archiver.py"
ICO_FILE = "icon.ico"
OUTPUT_NAME = "Android Archiver"

if not os.path.exists(SCRIPT_NAME):
    print(f"Error: {SCRIPT_NAME} not found!")
    print(f"Make sure {SCRIPT_NAME} is in the same directory as this build script.")
    input("Press Enter to exit...")
    sys.exit(1)

if not os.path.exists(ICO_FILE):
    print(f"Warning: {ICO_FILE} not found!")
    print(f"Building without icon...")
    use_icon = False
else:
    use_icon = True
    print(f"Using icon: {ICO_FILE}")

print(f"\nChecking PyInstaller installation...")
try:
    result = subprocess.run(
        ["pyinstaller", "--version"],
        capture_output=True,
        text=True,
        check=True
    )
    print(f"PyInstaller version: {result.stdout.strip()}")
except (subprocess.CalledProcessError, FileNotFoundError):
    print("Error: PyInstaller not installed!")
    print("\nInstalling PyInstaller...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True
        )
        print("PyInstaller installed successfully!")
    except subprocess.CalledProcessError:
        print("Failed to install PyInstaller!")
        print("Please run: pip install pyinstaller")
        input("Press Enter to exit...")
        sys.exit(1)

print("\nCleaning previous build files...")
for folder in ["build", "dist", "__pycache__"]:
    if os.path.exists(folder):
        shutil.rmtree(folder)
        print(f"  Removed {folder}/")

spec_files = [f for f in os.listdir(".") if f.endswith(".spec")]
for spec in spec_files:
    os.remove(spec)
    print(f"  Removed {spec}")

print("\nBuilding executable...")

cmd = [
    "pyinstaller",
    "--onefile",
    "--console",
    "--name", OUTPUT_NAME,
]

if use_icon:
    cmd.extend(["--icon", ICO_FILE])

cmd.append(SCRIPT_NAME)

print(f"Command: {' '.join(cmd)}")
print()

try:
    subprocess.run(cmd, check=True)
    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print("=" * 60)
    print(f"\nExecutable location: dist/{OUTPUT_NAME}.exe")

except subprocess.CalledProcessError as e:
    print(f"\nBuild failed with error code {e.returncode}")
    input("Press Enter to exit...")
    sys.exit(1)

print()
input("Press Enter to exit...")
