"""
Android Archiver - A tool for backing up Android device storage via ADB.
Supports full and partial backups with real-time progress tracking and error logging.
"""

import os
import subprocess
import time
import sys
import shutil
import shlex
from datetime import datetime
from colorama import init, Fore, Style
import re
import platform
import configparser
import threading

init()

if getattr(sys, 'frozen', False):
    CURRENT_DIR = os.path.dirname(sys.executable)
    PLATFORM_TOOLS_PATH = os.path.join(CURRENT_DIR, "platform-tools")
else:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    PLATFORM_TOOLS_PATH = os.path.join(CURRENT_DIR, "platform-tools")

ADB_PATH = os.path.join(PLATFORM_TOOLS_PATH, "adb.exe")

if not os.path.exists(PLATFORM_TOOLS_PATH):
    print(f"{Fore.RED}Error: platform-tools directory not found at {PLATFORM_TOOLS_PATH}{Style.RESET_ALL}")
    print("Please ensure the platform-tools folder exists in the same directory")
    print("as this script/executable and contains adb.exe")
    input("Press Enter to exit...")
    sys.exit(1)

def get_android_device_name():
    """Get the name of the connected Android device using adb and display device info."""
    try:
        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=10
        )

        devices = result.stdout.splitlines()
        device_lines = [line for line in devices if line.strip() and "List of devices attached" not in line]

        if not device_lines:
            print(f"{Fore.YELLOW}No devices found. Restarting ADB server...{Style.RESET_ALL}")
            subprocess.run([ADB_PATH, "kill-server"], check=True)
            subprocess.run([ADB_PATH, "start-server"], check=True)
            result = subprocess.run(
                [ADB_PATH, "devices"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                timeout=10
            )
            devices = result.stdout.splitlines()
            device_lines = [line for line in devices if line.strip() and "List of devices attached" not in line]

            if not device_lines:
                print(f"{Fore.RED}No Android device found. Please ensure:{Style.RESET_ALL}")
                print(f"1. USB debugging is enabled in Developer Options")
                print(f"2. Device is set to 'File Transfer' mode")
                print(f"3. Appropriate USB drivers are installed")
                print("")
                input("Press Enter to exit...")
                return None

        if len(device_lines) > 1:
            print(f"{Fore.YELLOW}Multiple devices detected. Please select a device:{Style.RESET_ALL}")
            for i, device in enumerate(device_lines):
                device_id = device.split("\t")[0]
                print(f"{i+1}. {device_id}")
            print("")
            selection = input("Enter device number: ")
            try:
                device_index = int(selection) - 1
                if 0 <= device_index < len(device_lines):
                    device_name = device_lines[device_index].split("\t")[0]
                else:
                    print(f"{Fore.RED}Invalid selection.{Style.RESET_ALL}")
                    input("Press Enter to exit...")
                    return None
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
                print("")
                input("Press Enter to exit...")
                return None
        else:
            device_name = device_lines[0].split("\t")[0]

        def get_device_prop(prop):
            try:
                result = subprocess.run(
                    [ADB_PATH, "-s", device_name, "shell", f"getprop {shell_quote(prop)}"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                    timeout=5
                )
                return result.stdout.strip()
            except Exception:
                return "Unknown"

        print(f"\n{Fore.GREEN}Device Information:{Style.RESET_ALL}")
        print(f" - {Fore.WHITE}Manufacturer: {Fore.GREEN}{get_device_prop('ro.product.manufacturer')}{Style.RESET_ALL}")
        print(f" - {Fore.WHITE}Model: {Fore.GREEN}{get_device_prop('ro.product.model')}{Style.RESET_ALL}")
        print(f" - {Fore.WHITE}Android Version: {Fore.GREEN}{get_device_prop('ro.build.version.release')}{Style.RESET_ALL}")
        print(f" - {Fore.WHITE}Build Number: {Fore.GREEN}{get_device_prop('ro.build.display.id')}{Style.RESET_ALL}")
        print(f" - {Fore.WHITE}Serial Number: {Fore.GREEN}{device_name}{Style.RESET_ALL}")

        return device_name

    except Exception as e:
        print(f"{Fore.RED}Error detecting Android device: {e}{Style.RESET_ALL}")
        input("Press Enter to exit...")
        return None

def select_backup_location(config):
    """Select the backup location using simple console prompts."""
    print("-" * 60)
    
    user_home = os.path.expanduser("~")

    if config.has_option('DEFAULT', 'backup_location'):
        default_backup_dir = config.get('DEFAULT', 'backup_location')
    else:
        default_backup_dir = os.path.join(user_home, "Documents", "AndroidBackup")

    print(f"\n{Fore.GREEN}Backup Location:{Style.RESET_ALL}")
    print(f"Default: {Fore.CYAN}{default_backup_dir}{Style.RESET_ALL}")
    print("")
    choice = input("Press Enter to use default, or type a custom path: ").strip()

    if choice:
        backup_location = choice
    else:
        backup_location = default_backup_dir

    print(f"{Fore.CYAN}Using: {backup_location}{Style.RESET_ALL}")

    critical_dirs = [
        os.path.expanduser("~"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Pictures"),
        os.path.expandvars("%SystemDrive%"),
        os.path.expandvars("%ProgramFiles%"),
        os.path.expandvars("%ProgramFiles(x86)%"),
        os.path.expandvars("%LocalAppData%"),
        os.path.expandvars("%AppData%")
    ]

    backup_location = os.path.normpath(backup_location)
    if any(os.path.normpath(critical_dir) == backup_location
           for critical_dir in critical_dirs):
        print(f"{Fore.RED}Error: Cannot use a critical system directory as backup location.{Style.RESET_ALL}")
        return select_backup_location(config)

    if backup_location.startswith('\\\\'):
        print(f"{Fore.YELLOW}Warning: Network drive selected. Performance may be slower.{Style.RESET_ALL}")
        confirm = input("Continue with network backup? (y/n): ").lower()
        if confirm != 'y':
            return select_backup_location(config)

    try:
        if platform.system() == 'Windows':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(backup_location),
                None,
                None,
                ctypes.pointer(free_bytes)
            )
            free_space = free_bytes.value
        else:
            stat = os.statvfs(backup_location)
            free_space = stat.f_bavail * stat.f_frsize

        if free_space < 10 * 1024**3:
            print(f"{Fore.YELLOW}Warning: Less than 10GB free space ({format_size(free_space)}) in backup location.{Style.RESET_ALL}")
            confirm = input("Continue anyway? (y/n): ").lower()
            if confirm != 'y':
                return select_backup_location(config)
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not verify free space: {e}{Style.RESET_ALL}")

    return backup_location

def check_existing_backup(backup_location):
    """Check if backup location already has files and ask user what to do."""
    if os.path.exists(backup_location):
        files_in_dir = os.listdir(backup_location)
        if files_in_dir:
            print(f"\n{Fore.YELLOW}Warning: Backup location already contains files.{Style.RESET_ALL}")
            print(f"Found {len(files_in_dir)} items in: {backup_location}")
            print("")
            print("Options:")
            print("1. Merge with existing backup (add new files)")
            print("2. Delete existing backup and start fresh")
            print("3. Cancel and choose different location")
            print("")
            choice = input("Select option (1-3): ").strip()

            if choice == "2":
                confirm = input(f"Delete all existing files? This cannot be undone! (yes/no): ").lower()
                if confirm == "yes":
                    try:
                        shutil.rmtree(backup_location)
                        os.makedirs(backup_location)
                        print(f"Existing backup deleted.")
                        return True
                    except Exception as e:
                        print(f"{Fore.RED}Failed to delete existing backup: {e}{Style.RESET_ALL}")
                        return False
                else:
                    print(f"{Fore.YELLOW}Deletion cancelled.{Style.RESET_ALL}")
                    return False
            elif choice == "3":
                return False
            elif choice == "1":
                print(f"Will merge with existing backup.")
                return True
            else:
                print(f"{Fore.RED}Invalid choice.{Style.RESET_ALL}")
                return False
    return True

def check_adb_version():
    """Check if ADB version is compatible."""
    try:
        result = subprocess.run(
            [ADB_PATH, "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=10
        )
        version_match = re.search(r"Version (\d+\.\d+\.\d+)", result.stdout)
        if version_match:
            version = version_match.group(1)
            print(f"{Fore.CYAN}ADB Version: {version}{Style.RESET_ALL}")
            return True
        return False
    except Exception as e:
        print(f"{Fore.RED}Error checking ADB version: {e}{Style.RESET_ALL}")
        return False

def check_device_compatibility(device_name):
    """Check if device is compatible and accessible."""
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device_name, "get-state"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=10
        )
        if "device" not in result.stdout.lower():
            print(f"{Fore.RED}Device is not in proper state: {result.stdout}{Style.RESET_ALL}")
            return False
        return True
    except Exception as e:
        print(f"{Fore.RED}Error checking device compatibility: {e}{Style.RESET_ALL}")
        return False

def cleanup_interrupted_backup(backup_location, dir_created_by_us):
    """Clean up partially transferred files after an interrupted backup."""
    if dir_created_by_us and os.path.exists(backup_location):
        print(f"{Fore.YELLOW}Cleaning up interrupted backup...{Style.RESET_ALL}")
        try:
            shutil.rmtree(backup_location)
            print(f"{Fore.GREEN}Cleanup completed.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Cleanup failed: {e}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Backup directory not cleaned (may contain existing files).{Style.RESET_ALL}")

def get_backup_parameters(device_name):
    """Prompt user for backup type and return source path.
    
    Returns: (source_path, exclude_android_flag)
    """
    print("-" * 60)
    
    print(f"\n{Fore.GREEN}Backup Type:{Style.RESET_ALL}")
    print("1. Full backup (entire /sdcard, excludes Android folder)")
    print("2. Partial backup (select specific folder)")
    print("")
    backup_type = input("Select backup type (1-2): ").strip()

    if backup_type == "2":
        try:
            folders = [
                f for f in list_remote_entries(device_name, "/sdcard")
                if f
                and not f.startswith('.')
                and f != 'Android'
            ]

            if not folders:
                print(f"{Fore.RED}No accessible folders found{Style.RESET_ALL}")
                input("Press Enter to exit...")
                return None, False

            print(f"\n{Fore.GREEN}Available folders in /sdcard:{Style.RESET_ALL}")
            for i, folder in enumerate(folders, 1):
                print(f"{i}. {folder}")

            print("")
            selection = input("Select folder number: ").strip()
            try:
                folder_index = int(selection) - 1
                if 0 <= folder_index < len(folders):
                    source_path = f"/sdcard/{folders[folder_index]}"
                    return source_path, False
                else:
                    print(f"{Fore.RED}Invalid selection{Style.RESET_ALL}")
                    input("Press Enter to exit...")
                    return None, False
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number{Style.RESET_ALL}")
                input("Press Enter to exit...")
                return None, False

        except Exception as e:
            print(f"{Fore.RED}Error listing folders: {e}{Style.RESET_ALL}")
            input("Press Enter to exit...")
            return None, False
    else:
        source_path = "/sdcard"
        return source_path, True

    return None, False

def estimate_backup_size():
    """Prompt user to estimate backup size in GB.
    
    Returns: estimated size in bytes
    """
    print("-" * 60)
    
    print(f"\n{Fore.GREEN}Estimated Backup Size:{Style.RESET_ALL}")
    print("Please estimate the total size of your backup in GB")
    print("Example: For 32GB of data, enter '32'")
    
    while True:
        try:
            print("")
            estimated_gb = float(input("Enter estimated size in GB: "))
            print("")
            if estimated_gb <= 0:
                print(f"{Fore.RED}Size must be positive{Style.RESET_ALL}")
                continue
            return estimated_gb * 1024**3
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number{Style.RESET_ALL}")

# adb pull progress lines like "[ 50%] /sdcard/foo.mp4"
_PROGRESS_LINE_RE = re.compile(r'^\[\s*\d+%\]')
_WIN_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')
_PULL_RETRIES = 3
_MAX_INDIVIDUAL_PULLS = 25
_MAX_GAP_DEPTH = 3
_CONSOLE_LOCK = threading.Lock()

def shell_quote(value):
    """Quote a value for safe use inside an adb shell command string."""
    return shlex.quote(str(value))

def adb_shell(device_name, command, timeout=60):
    """Run a single shell command string on the device."""
    return subprocess.run(
        [ADB_PATH, "-s", device_name, "shell", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )

def log_errors_thread(stderr_stream, log_file):
    """Background thread to capture stderr; log all non-progress lines."""
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            for line in stderr_stream:
                line = line.strip()
                if not line or _PROGRESS_LINE_RE.match(line):
                    continue
                timestamp = datetime.now().strftime("%H:%M:%S")
                f.write(f"[{timestamp}] {line}\n")
                f.flush()
    except Exception:
        pass

def append_error_log(error_log_path, message):
    try:
        with open(error_log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass

def sanitize_component(name):
    """Make a path component safe for Windows filenames."""
    name = _WIN_INVALID_CHARS.sub('_', name)
    name = name.rstrip(' .')
    return name or '_'

def get_current_backup_size(backup_location, backup_start_time):
    """Get total size of files created/modified during this backup.
    
    Returns: (total_size, file_count)
    """
    total_size = 0
    file_count = 0
    skip_names = {"backup_errors.log", "backup_completed.txt", "backup_incomplete.txt"}
    
    try:
        for dirpath, _, filenames in os.walk(backup_location):
            for filename in filenames:
                if filename in skip_names:
                    continue
                filepath = os.path.join(dirpath, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    if mtime >= backup_start_time:
                        size = os.path.getsize(filepath)
                        total_size += size
                        file_count += 1
                except (FileNotFoundError, PermissionError, OSError):
                    continue
    except (FileNotFoundError, PermissionError):
        pass
    
    return total_size, file_count

def count_remote_files(device_name, source_path, exclude_android=False):
    """Count regular files under source_path on the device. Returns int or None."""
    # Trailing slash makes find follow /sdcard, which is a symlink on Android
    quoted = shell_quote(source_path.rstrip("/") + "/")
    if exclude_android:
        find_expr = f"find {quoted} -type f ! -path '*/Android/*' 2>/dev/null | wc -l"
    else:
        find_expr = f"find {quoted} -type f 2>/dev/null | wc -l"
    try:
        result = adb_shell(device_name, find_expr, timeout=300)
        output = (result.stdout or "").strip().replace("\r", "")
        if not output:
            return None
        return int(output.splitlines()[-1].strip())
    except Exception:
        return None

def count_local_files(pulled_root, exclude_android=False):
    """Count files under the pulled directory tree on disk."""
    if not os.path.isdir(pulled_root):
        return 0
    skip_names = {"backup_errors.log", "backup_completed.txt", "backup_incomplete.txt"}
    count = 0
    try:
        for dirpath, dirnames, filenames in os.walk(pulled_root):
            if exclude_android:
                dirnames[:] = [d for d in dirnames if d != "Android"]
            for filename in filenames:
                if filename in skip_names:
                    continue
                count += 1
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return count

def list_remote_entries(device_name, remote_dir):
    """List immediate child names under remote_dir."""
    try:
        result = adb_shell(
            device_name,
            f"ls -1A {shell_quote(remote_dir)}",
            timeout=60
        )
        return [
            line.strip().replace("\r", "")
            for line in result.stdout.splitlines()
            if line.strip()
        ]
    except Exception:
        return []

def list_remote_files(device_name, remote_dir, find_type="f"):
    """List all paths of find_type ("f" files, "d" directories) under remote_dir on the device."""
    try:
        result = adb_shell(
            device_name,
            f"find {shell_quote(remote_dir)} -type {find_type} 2>/dev/null",
            timeout=300
        )
        return [
            line.strip().replace("\r", "")
            for line in result.stdout.splitlines()
            if line.strip()
        ]
    except Exception:
        return []

def get_remote_size(device_name, remote_path):
    try:
        result = adb_shell(
            device_name,
            f"stat -c %s {shell_quote(remote_path)}",
            timeout=15
        )
        output = (result.stdout or "").strip().replace("\r", "")
        if not output:
            return None
        return int(output.splitlines()[-1].strip())
    except Exception:
        return None

def remote_to_local_file(remote_file, remote_root, local_root):
    """Map a remote file path to a Windows-safe local path under local_root."""
    remote_root = remote_root.rstrip("/")
    if remote_file.startswith(remote_root + "/"):
        rel = remote_file[len(remote_root) + 1:]
    else:
        rel = remote_file.lstrip("/")
    parts = [sanitize_component(p) for p in rel.split("/") if p]
    return os.path.join(local_root, *parts) if parts else local_root

def ensure_extended_path(path):
    """On Windows, prefix absolute paths with \\\\?\\ to allow long paths."""
    if platform.system() != "Windows":
        return path
    abs_path = os.path.abspath(path)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abs_path[2:]
    return "\\\\?\\" + abs_path

def remote_path_needs_stream(remote_path):
    """True if the remote path is non-ASCII or has a component problematic for Windows adb pull."""
    if not remote_path.isascii():
        return True
    for part in remote_path.replace("\\", "/").split("/"):
        if not part:
            continue
        if _WIN_INVALID_CHARS.search(part):
            return True
        if part != part.rstrip(" ."):
            return True
    return False

def build_pull_jobs(device_name, source_path, backup_location, exclude_android):
    """Build (remote_path, local_parent) jobs. Full backup pulls top-level items separately."""
    source_path = source_path.rstrip("/") or "/sdcard"
    if source_path == "/sdcard" and exclude_android:
        pulled_root = os.path.join(backup_location, "sdcard")
        os.makedirs(pulled_root, exist_ok=True)
        jobs = []
        for name in list_remote_entries(device_name, "/sdcard"):
            if name == "Android":
                continue
            jobs.append((f"/sdcard/{name}", pulled_root, name))
        return jobs, pulled_root
    basename = os.path.basename(source_path)
    pulled_root = os.path.join(backup_location, basename)
    return [(source_path, backup_location, basename)], pulled_root

def adb_stream_file(device_name, remote_path, local_dest_path, error_log_path=None, active_process=None):
    """Copy one remote file via exec-out cat (bypasses Windows adb pull path parsing)."""
    dest = ensure_extended_path(local_dest_path)
    parent = os.path.dirname(dest)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            if error_log_path:
                append_error_log(error_log_path, f"makedirs failed for {local_dest_path}: {e}")
            return False

    cmd = [ADB_PATH, "-s", device_name, "exec-out", f"cat {shell_quote(remote_path)}"]
    try:
        with open(dest, "wb") as out:
            process = subprocess.Popen(
                cmd,
                stdout=out,
                stderr=subprocess.PIPE,
            )
            if active_process is not None:
                active_process["proc"] = process
            _, err = process.communicate()
            rc = process.returncode if process.returncode is not None else -1
            if active_process is not None:
                active_process["proc"] = None

        if rc != 0:
            if error_log_path:
                err_text = (err or b"").decode("utf-8", errors="replace").strip()
                append_error_log(
                    error_log_path,
                    f"exec-out cat failed ({rc}) for {remote_path}"
                    + (f": {err_text}" if err_text else "")
                )
            try:
                if os.path.isfile(dest) and os.path.getsize(dest) == 0:
                    os.remove(dest)
            except OSError:
                pass
            return False

        remote_size = get_remote_size(device_name, remote_path)
        try:
            local_size = os.path.getsize(dest)
        except OSError:
            return False
        if remote_size is not None and local_size != remote_size:
            if error_log_path:
                append_error_log(
                    error_log_path,
                    f"Size mismatch after stream {remote_path}: "
                    f"remote={remote_size} local={local_size}"
                )
            return False
        return True
    except Exception as e:
        if error_log_path:
            append_error_log(error_log_path, f"exec-out cat error for {remote_path}: {e}")
        if active_process is not None:
            active_process["proc"] = None
        return False

def adb_pull(device_name, remote_path, local_dest, error_log_path, active_process=None, dest_is_file=False):
    """Pull remote_path to local_dest (directory parent, or file path if dest_is_file)."""
    try:
        if dest_is_file:
            parent = os.path.dirname(local_dest)
            if parent:
                os.makedirs(ensure_extended_path(parent), exist_ok=True)
        else:
            os.makedirs(ensure_extended_path(local_dest), exist_ok=True)
    except OSError as e:
        append_error_log(error_log_path, f"makedirs failed for {local_dest}: {e}")
        return -1

    cmd = [ADB_PATH, "-s", device_name, "pull", remote_path, local_dest]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if active_process is not None:
        active_process["proc"] = process

    error_thread = threading.Thread(
        target=log_errors_thread,
        args=(process.stderr, error_log_path),
        daemon=True
    )
    error_thread.start()
    process.wait()
    error_thread.join(timeout=10)
    if active_process is not None:
        active_process["proc"] = None
    return process.returncode if process.returncode is not None else -1

def tree_complete(device_name, remote_path, local_path):
    remote_count = count_remote_files(device_name, remote_path, False)
    if remote_count is None:
        return True, None, None
    if remote_count == 0:
        return os.path.exists(local_path), 0, 0
    local_count = count_local_files(local_path, False)
    return local_count >= remote_count, remote_count, local_count

def clear_progress_line():
    print("\r" + " " * 160 + "\r", end="", flush=True)

def print_notice(msg):
    """Print a status message without colliding with the progress line."""
    with _CONSOLE_LOCK:
        clear_progress_line()
        print(msg, flush=True)

def collect_missing_files(device_name, remote_dir, local_dir):
    """Return list of (remote_file, local_file) that are missing or empty locally."""
    remote_files = list_remote_files(device_name, remote_dir)
    missing = []
    for remote_file in remote_files:
        local_file = remote_to_local_file(remote_file, remote_dir, local_dir)
        if local_file_ok(local_file):
            try:
                path = local_file if os.path.isfile(local_file) else ensure_extended_path(local_file)
                if os.path.getsize(path) > 0:
                    continue
            except OSError:
                pass
            remote_size = get_remote_size(device_name, remote_file)
            if remote_size == 0:
                continue
        missing.append((remote_file, local_file))
    return missing

def group_missing_by_child(remote_dir, missing_pairs):
    """Group missing files by immediate child name under remote_dir.
    
    Returns: dict[child_name_or_None, list[(remote, local)]]
    None key = files directly under remote_dir.
    """
    remote_dir = remote_dir.rstrip("/")
    groups = {}
    prefix = remote_dir + "/"
    for remote_file, local_file in missing_pairs:
        if remote_file.startswith(prefix):
            rel = remote_file[len(prefix):]
        else:
            rel = remote_file.lstrip("/")
        parts = [p for p in rel.split("/") if p]
        if len(parts) <= 1:
            key = None
        else:
            key = parts[0]
        groups.setdefault(key, []).append((remote_file, local_file))
    return groups

def local_file_ok(local_file, remote_size=None):
    """True if local_file exists and matches remote_size when known."""
    try:
        path = local_file
        if not os.path.isfile(path):
            ext = ensure_extended_path(local_file)
            if ext != local_file and os.path.isfile(ext):
                path = ext
            else:
                return False
        size = os.path.getsize(path)
        if remote_size is None:
            return True
        return size == remote_size
    except OSError:
        return False

def pull_file_list(
    device_name, missing_pairs, error_log_path,
    active_process=None, status_holder=None, label="fill"
):
    """Pull a small list of files individually. Returns (copied, failed).
    
    Uses exec-out streaming when remote names break Windows adb pull.
    """
    copied = 0
    failed = 0
    total = len(missing_pairs)
    for i, (remote_file, local_file) in enumerate(missing_pairs, 1):
        if status_holder is not None:
            status_holder["label"] = f"| {label} {i}/{total}"

        ok = False
        use_stream = remote_path_needs_stream(remote_file)

        if not use_stream:
            for _ in range(_PULL_RETRIES):
                rc = adb_pull(
                    device_name, remote_file, local_file, error_log_path,
                    active_process, dest_is_file=True
                )
                if rc == 0 and local_file_ok(local_file):
                    ok = True
                    break
                if local_file_ok(local_file):
                    # File landed despite non-zero rc
                    ok = True
                    break
                time.sleep(0.5)

        if not ok:
            if use_stream:
                append_error_log(
                    error_log_path,
                    f"Streaming (non-ASCII or illegal name): {remote_file}"
                )
            else:
                append_error_log(
                    error_log_path,
                    f"adb pull failed, trying exec-out stream: {remote_file}"
                )
            for _ in range(_PULL_RETRIES):
                if adb_stream_file(
                    device_name, remote_file, local_file,
                    error_log_path, active_process
                ):
                    ok = True
                    break
                time.sleep(0.5)

        if ok:
            copied += 1
        else:
            failed += 1
            append_error_log(error_log_path, f"Failed to copy file: {remote_file}")
    return copied, failed

def pull_split_tree(device_name, remote_dir, local_dir, error_log_path, active_process=None, status_holder=None):
    """Pull remote_dir into local_dir. adb mangles non-ASCII folder names on Windows, so files under
    them are streamed per file while ASCII subfolders are still pulled with adb."""
    label = os.path.basename(remote_dir)
    if not remote_dir.isascii():
        pairs = [
            (f, remote_to_local_file(f, remote_dir, local_dir))
            for f in list_remote_files(device_name, remote_dir)
        ]
        pull_file_list(device_name, pairs, error_log_path, active_process, status_holder, label=label)
        return

    dirs = set(list_remote_files(device_name, remote_dir, "d"))
    if all(d.isascii() for d in dirs):
        for attempt in range(1, _PULL_RETRIES + 1):
            rc = adb_pull(device_name, remote_dir, os.path.dirname(local_dir), error_log_path, active_process)
            if rc == 0 and os.path.exists(local_dir):
                return
            if attempt < _PULL_RETRIES:
                time.sleep(1)
        return

    os.makedirs(local_dir, exist_ok=True)
    for d in dirs:
        if d.rsplit("/", 1)[0] == remote_dir:
            pull_split_tree(
                device_name, d, os.path.join(local_dir, sanitize_component(os.path.basename(d))),
                error_log_path, active_process, status_holder
            )
    pairs = [
        (f, remote_to_local_file(f, remote_dir, local_dir))
        for f in list_remote_files(device_name, remote_dir)
        if f.rsplit("/", 1)[0] == remote_dir
    ]
    pull_file_list(device_name, pairs, error_log_path, active_process, status_holder, label=label)

def fill_missing_gaps(
    device_name, remote_dir, local_dir, error_log_path,
    active_process=None, status_holder=None, depth=0
):
    """Fill gaps by re-pulling incomplete subdirectories, not every file.
    
    Falls back to per-file pulls only for small leftover sets or root-level files.
    Returns (copied_estimate, failed).
    """
    missing = collect_missing_files(device_name, remote_dir, local_dir)
    if not missing:
        return 0, 0

    print_notice(
        f"{Fore.YELLOW}Gap fill in {os.path.basename(remote_dir) or remote_dir}: "
        f"{len(missing)} missing{Style.RESET_ALL}"
    )

    if len(missing) <= _MAX_INDIVIDUAL_PULLS or depth >= _MAX_GAP_DEPTH or not remote_dir.isascii():
        return pull_file_list(
            device_name, missing, error_log_path,
            active_process, status_holder, label="fill"
        )

    groups = group_missing_by_child(remote_dir, missing)
    copied = 0
    failed = 0
    root_files = groups.pop(None, [])

    child_items = list(groups.items())
    for idx, (child_name, child_missing) in enumerate(child_items, 1):
        remote_child = f"{remote_dir.rstrip('/')}/{child_name}"
        local_child = os.path.join(local_dir, sanitize_component(child_name))
        if status_holder is not None:
            status_holder["label"] = (
                f"| gap dir {idx}/{len(child_items)} {child_name}"
            )
        if remote_child.isascii():
            print_notice(
                f"{Fore.YELLOW}Re-pulling subdirectory: {child_name} "
                f"({len(child_missing)} missing){Style.RESET_ALL}"
            )
            append_error_log(error_log_path, f"Gap-fill subdirectory pull: {remote_child}")
            pull_split_tree(
                device_name, remote_child, local_child, error_log_path, active_process, status_holder
            )

        still = [
            (r, l) for r, l in child_missing
            if not local_file_ok(l)
        ]
        if not still:
            copied += len(child_missing)
            continue

        if len(still) <= _MAX_INDIVIDUAL_PULLS:
            c, f = pull_file_list(
                device_name, still, error_log_path,
                active_process, status_holder, label=f"{child_name}"
            )
            copied += c
            failed += f
        else:
            c, f = fill_missing_gaps(
                device_name, remote_child, local_child, error_log_path,
                active_process, status_holder, depth=depth + 1
            )
            copied += c
            failed += f

    if root_files:
        c, f = pull_file_list(
            device_name, root_files, error_log_path,
            active_process, status_holder, label="root"
        )
        copied += c
        failed += f

    return copied, failed

def repair_tree(
    device_name, remote_path, local_path, label, error_log_path,
    active_process=None, status_holder=None
):
    """Gap-fill an incomplete tree. Avoids full re-pull when data is already present."""
    complete, remote_count, local_count = tree_complete(device_name, remote_path, local_path)
    if complete:
        return True

    missing = 0
    if remote_count is not None and local_count is not None:
        missing = max(remote_count - local_count, 0)

    append_error_log(error_log_path, f"Repairing incomplete path: {remote_path}")
    print_notice(
        f"{Fore.YELLOW}Incomplete: {label}"
        + (f" ({missing} missing)" if missing else "")
        + f"{Style.RESET_ALL}"
    )

    # Full re-pull only when almost nothing landed
    if local_count is not None and remote_count and local_count < max(remote_count * 0.1, 5):
        print_notice(f"{Fore.YELLOW}Re-pulling {label}...{Style.RESET_ALL}")
        pull_split_tree(device_name, remote_path, local_path, error_log_path, active_process, status_holder)
        complete, _, _ = tree_complete(device_name, remote_path, local_path)
        if complete:
            return True

    copied, failed = fill_missing_gaps(
        device_name, remote_path, local_path, error_log_path,
        active_process, status_holder
    )
    if copied or failed:
        print_notice(f" - Gap fill: {copied} recovered, {failed} failed")
    complete, _, _ = tree_complete(device_name, remote_path, local_path)
    return complete

def perform_backup_with_progress(device_name, source_path, backup_location, total_size, exclude_android):
    """Execute the backup with per-folder pulls, retries, and verification.
    
    Returns: "complete", "incomplete", or "failed"
    """
    start_time = time.time()
    error_log_path = os.path.join(backup_location, "backup_errors.log")
    active_process = {"proc": None}
    stop_progress = threading.Event()
    status_holder = {"label": ""}

    try:
        result = adb_shell(
            device_name,
            f"test -d {shell_quote(source_path)} && echo exists",
            timeout=5
        )
        if "exists" not in result.stdout:
            print(f"{Fore.RED}Error: Source path {source_path} not found on device{Style.RESET_ALL}")
            input("Press Enter to exit...")
            return "failed"
    except Exception as e:
        print(f"{Fore.RED}Error verifying source path: {e}{Style.RESET_ALL}")
        input("Press Enter to exit...")
        return "failed"

    jobs, pulled_root = build_pull_jobs(
        device_name, source_path, backup_location, exclude_android
    )
    if not jobs:
        print(f"{Fore.RED}No accessible items to back up under {source_path}{Style.RESET_ALL}")
        input("Press Enter to exit...")
        return "failed"

    print("-" * 60)
    if exclude_android and source_path.rstrip("/") == "/sdcard":
        print(f"{Fore.CYAN}Full backup: pulling {len(jobs)} top-level items (Android/ skipped){Style.RESET_ALL}")
    print("")

    def progress_loop():
        last_size = 0
        last_update_time = start_time
        transfer_rate = 0
        rate_samples = []
        max_samples = 5
        while not stop_progress.wait(1.0):
            current_size, file_count = get_current_backup_size(backup_location, start_time)
            progress = min((current_size / total_size) * 100, 100.0) if total_size else 0
            current_time = time.time()
            time_diff = current_time - last_update_time
            if time_diff >= 1 and current_size >= last_size:
                instant_rate = (current_size - last_size) / time_diff
                rate_samples.append(instant_rate)
                if len(rate_samples) > max_samples:
                    rate_samples.pop(0)
                transfer_rate = sum(rate_samples) / len(rate_samples)
                last_size = current_size
                last_update_time = current_time

            label = status_holder.get("label") or ""
            label_bit = f" {label}" if label else ""
            status = (
                f"{Fore.CYAN}{draw_progress_bar(progress, width=30)} "
                f"{format_size(current_size)}/{format_size(total_size)} "
                f"({file_count} files) "
                f"[{format_size(transfer_rate)}/s]{label_bit}{Style.RESET_ALL}"
            )
            with _CONSOLE_LOCK:
                print("\r" + " " * 160 + "\r" + status, end="", flush=True)

    progress_thread = threading.Thread(target=progress_loop, daemon=True)
    progress_thread.start()

    try:
        any_failure = False
        for index, (remote_path, local_parent, label) in enumerate(jobs, 1):
            status_holder["label"] = f"| {index}/{len(jobs)} {label}"
            append_error_log(error_log_path, f"Pulling {remote_path}")
            safe_label = sanitize_component(label)
            local_item = os.path.join(local_parent, safe_label)
            os.makedirs(local_parent, exist_ok=True)

            # Names illegal on Windows: per-file pull with safe paths
            if safe_label != label:
                append_error_log(
                    error_log_path,
                    f"Windows-unsafe name {label!r} mapped to {safe_label!r}; using per-file pull"
                )
                os.makedirs(local_item, exist_ok=True)
                fill_missing_gaps(
                    device_name, remote_path, local_item, error_log_path,
                    active_process, status_holder
                )
            else:
                pull_split_tree(
                    device_name, remote_path, local_item, error_log_path, active_process, status_holder
                )

            # One completeness check per item (not after every retry)
            status_holder["label"] = f"| {index}/{len(jobs)} {label} (checking)"
            complete, remote_cnt, local_cnt = tree_complete(
                device_name, remote_path, local_item
            )
            if not complete:
                if not repair_tree(
                    device_name, remote_path, local_item, label,
                    error_log_path, active_process, status_holder
                ):
                    any_failure = True
            status_holder["label"] = f"| {index}/{len(jobs)} {label}"

        status_holder["label"] = "| verifying"
        stop_progress.set()
        progress_thread.join(timeout=2)
        with _CONSOLE_LOCK:
            clear_progress_line()
            print()

        current_size, file_count = get_current_backup_size(backup_location, start_time)
        if current_size <= 0:
            print(f"\n{Fore.RED}Backup failed - no files were transferred{Style.RESET_ALL}")
            print("")
            input("Press Enter to exit...")
            return "failed"

        # Final repair for single-folder (partial) backups
        verify_remote = source_path.rstrip("/") or "/sdcard"
        if not (exclude_android and verify_remote == "/sdcard"):
            complete, _, _ = tree_complete(device_name, verify_remote, pulled_root)
            if not complete:
                repair_tree(
                    device_name, verify_remote, pulled_root,
                    os.path.basename(verify_remote), error_log_path,
                    active_process, status_holder
                )

        print(f"\n{Fore.CYAN}Verifying backup completeness...{Style.RESET_ALL}")
        remote_count = count_remote_files(device_name, source_path, exclude_android)
        local_count = count_local_files(pulled_root, exclude_android)
        missing_files = None
        if remote_count is not None:
            missing_files = max(remote_count - local_count, 0)
            print(
                f" - Device files: {remote_count} | Local files: {local_count}"
                + (f" | Missing: {missing_files}" if missing_files else "")
            )
            if exclude_android:
                print(f" - (Android/ excluded from comparison)")
        else:
            print(f"{Fore.YELLOW} - Could not count device files{Style.RESET_ALL}")

        has_error_log = os.path.exists(error_log_path) and os.path.getsize(error_log_path) > 0
        if missing_files is not None:
            incomplete = missing_files > 0
        else:
            incomplete = any_failure

        end_time = time.time()
        total_time = end_time - start_time
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if incomplete:
            print(f"\n{Fore.YELLOW}Backup finished with missing or failed files.{Style.RESET_ALL}")
            if missing_files:
                print(f"{Fore.YELLOW} - {missing_files} file(s) on device were not found in the backup{Style.RESET_ALL}")
            if has_error_log:
                print(f"{Fore.YELLOW} - See backup_errors.log for ADB messages{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}Backup completed successfully!{Style.RESET_ALL}")

        print(f"Summary:")
        print(f" - Elapsed time: {format_time(total_time)}")
        print(f" - Files transferred this run: {file_count} ({format_size(current_size)})")
        print(f"{Fore.WHITE} - Backup location: {backup_location}{Style.RESET_ALL}")
        if has_error_log and not incomplete:
            print(f"{Fore.YELLOW} - ADB reported messages - see backup_errors.log{Style.RESET_ALL}")

        status_name = "backup_incomplete.txt" if incomplete else "backup_completed.txt"
        other_name = "backup_completed.txt" if incomplete else "backup_incomplete.txt"
        try:
            other_path = os.path.join(backup_location, other_name)
            if os.path.exists(other_path):
                os.remove(other_path)
            with open(os.path.join(backup_location, status_name), "w", encoding="utf-8") as f:
                f.write(f"Backup {'incomplete' if incomplete else 'completed'} on {timestamp}\n")
                f.write(f"Device: {device_name}\n")
                f.write(f"Source: {source_path}\n")
                f.write(f"Files transferred this run: {file_count}\n")
                f.write(f"Size transferred this run: {format_size(current_size)}\n")
                f.write(f"Elapsed time: {format_time(total_time)}\n")
                if remote_count is not None:
                    f.write(f"Device file count: {remote_count}\n")
                    f.write(f"Local file count: {local_count}\n")
                    f.write(f"Missing files: {missing_files}\n")
                if exclude_android:
                    f.write("Note: Android/ was skipped intentionally on full backup\n")
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not create status file: {e}{Style.RESET_ALL}")

        print("")
        prompt = "Backup incomplete. Press Enter to exit..." if incomplete else "Backup complete! Press Enter to exit..."
        input(prompt)
        return "incomplete" if incomplete else "complete"

    except KeyboardInterrupt:
        stop_progress.set()
        print_notice(f"{Fore.YELLOW}Backup interrupted by user.{Style.RESET_ALL}")
        proc = active_process.get("proc")
        if proc and proc.poll() is None:
            proc.terminate()
        print("")
        input("Press Enter to exit...")
        return "failed"
    finally:
        stop_progress.set()

def copy_files_from_android(device_name, backup_location, dir_created_by_us):
    """Main backup orchestration function."""
    try:
        if not check_device_compatibility(device_name):
            print(f"{Fore.RED}Device compatibility check failed{Style.RESET_ALL}")
            input("Press Enter to exit...")
            return

        source_path, exclude_android = get_backup_parameters(device_name)
        if not source_path:
            return
        
        total_size = estimate_backup_size()
        
        result = perform_backup_with_progress(
            device_name,
            source_path,
            backup_location,
            total_size,
            exclude_android
        )
        
        # Only wipe a directory we created when nothing usable was left
        if result == "failed" and dir_created_by_us:
            cleanup_interrupted_backup(backup_location, dir_created_by_us)

    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        print("")
        input("Press Enter to exit...")
        return

def format_size(size_bytes):
    """Format bytes to human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"

def format_time(seconds):
    """Format seconds to human-readable time (HH:MM:SS)."""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def draw_progress_bar(progress, width=30):
    """Draw a progress bar with the given progress percentage."""
    filled_width = int(width * progress / 100)
    bar = '█' * filled_width + '░' * (width - filled_width)
    return f"[{bar}] {progress:.1f}%"

def load_config():
    """Load configuration file if it exists, otherwise return default config."""
    config_path = os.path.join(CURRENT_DIR, "android_archiver.cfg")
    config = configparser.ConfigParser()

    try:
        if os.path.exists(config_path):
            config.read(config_path)
            if 'DEFAULT' in config and 'backup_location' in config['DEFAULT']:
                config['DEFAULT']['backup_location'] = os.path.expandvars(config['DEFAULT']['backup_location'])
            return config

        config['DEFAULT'] = {
            'backup_location': os.path.join(
                os.path.expanduser("~"),
                "Documents",
                "AndroidBackup"
            )
        }
        
        try:
            with open(config_path, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not create config file: {e}{Style.RESET_ALL}")
        
        return config

    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Error loading config: {e}. Using defaults.{Style.RESET_ALL}")
        return config

def main():
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'Android Archiver v1.5 BETA (github/mirbyte)':^60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")

    try:
        if not check_adb_version():
            print(f"{Fore.RED}ADB version check failed{Style.RESET_ALL}")
            input("Press Enter to exit...")
            return

        device_name = get_android_device_name()
        if not device_name:
            return

        config = load_config()
        backup_location = select_backup_location(config)
        if not backup_location:
            input("Press Enter to exit...")
            return

        dir_created_by_us = False
        if not os.path.exists(backup_location):
            try:
                os.makedirs(backup_location)
                dir_created_by_us = True
            except Exception as e:
                print(f"{Fore.RED}Failed to create backup directory: {e}{Style.RESET_ALL}")
                input("Press Enter to exit...")
                return
        else:
            if not check_existing_backup(backup_location):
                print(f"{Fore.YELLOW}Backup cancelled. Please restart and choose a different location.{Style.RESET_ALL}")
                input("Press Enter to exit...")
                return

        copy_files_from_android(device_name, backup_location, dir_created_by_us)

    except Exception as e:
        print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        print("")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
