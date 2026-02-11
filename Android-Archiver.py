"""
Android Archiver - A tool for backing up Android device storage via ADB.
Supports full and partial backups with real-time progress tracking and error logging.
"""

import os
import subprocess
import time
import sys
import shutil
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
                    [ADB_PATH, "-s", device_name, "shell", f"getprop {prop}"],
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
            result = subprocess.run(
                [ADB_PATH, "-s", device_name, "shell", "ls -1 /sdcard"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10
            )
            folders = [
                f.strip() for f in result.stdout.splitlines()
                if f.strip()
                and not f.startswith(('.', 'Android'))
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

def log_errors_thread(stderr_stream, log_file):
    """Background thread to capture stderr and log errors."""
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            for line in stderr_stream:
                line = line.strip()
                if line and ('Permission denied' in line or 'failed' in line.lower() or 'cannot' in line.lower()):
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    f.write(f"[{timestamp}] {line}\n")
                    f.flush()
    except Exception:
        pass

def get_current_backup_size(backup_location, backup_start_time):
    """Get total size of files created/modified during this backup.
    
    Returns: (total_size, file_count)
    """
    total_size = 0
    file_count = 0
    
    try:
        for dirpath, _, filenames in os.walk(backup_location):
            for filename in filenames:
                if filename == "backup_errors.log":
                    continue
                filepath = os.path.join(dirpath, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    # Only count files modified after backup started
                    if mtime >= backup_start_time:
                        size = os.path.getsize(filepath)
                        total_size += size
                        file_count += 1
                except (FileNotFoundError, PermissionError, OSError):
                    continue
    except (FileNotFoundError, PermissionError):
        pass
    
    return total_size, file_count

def perform_backup_with_progress(device_name, source_path, backup_location, total_size, exclude_android):
    """Execute the backup with real-time progress tracking.
    
    Returns: True if successful, False otherwise
    """
    start_time = time.time()
    error_log_path = os.path.join(backup_location, "backup_errors.log")
    
    try:
        result = subprocess.run(
            [ADB_PATH, "-s", device_name, "shell", f"test -d {source_path} && echo exists"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "exists" not in result.stdout:
            print(f"{Fore.RED}Error: Source path {source_path} not found on device{Style.RESET_ALL}")
            input("Press Enter to exit...")
            return False
    except Exception as e:
        print(f"{Fore.RED}Error verifying source path: {e}{Style.RESET_ALL}")
        input("Press Enter to exit...")
        return False

    print("-" * 60)
    print("")
    
    cmd = [ADB_PATH, "-s", device_name, "pull", source_path, backup_location]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    
    error_thread = threading.Thread(
        target=log_errors_thread,
        args=(process.stderr, error_log_path),
        daemon=True
    )
    error_thread.start()
    
    last_size = 0
    last_update_time = start_time
    transfer_rate = 0
    rate_samples = []
    max_samples = 5
    
    try:
        while True:
            time.sleep(1)
            
            current_size, file_count = get_current_backup_size(backup_location, start_time)
            
            progress = min((current_size / total_size) * 100, 100.0)
            current_time = time.time()
            elapsed_time = current_time - start_time
            time_diff = current_time - last_update_time

            if time_diff >= 1 and current_size >= last_size:
                size_diff = current_size - last_size
                instant_rate = size_diff / time_diff
                rate_samples.append(instant_rate)
                
                if len(rate_samples) > max_samples:
                    rate_samples.pop(0)
                
                transfer_rate = sum(rate_samples) / len(rate_samples)
                last_size = current_size
                last_update_time = current_time

            if transfer_rate > 0:
                remaining_bytes = total_size - current_size
                eta = remaining_bytes / transfer_rate
            else:
                eta = 0

            progress_bar = draw_progress_bar(progress, width=30)
            status = (
                f"\r{Fore.CYAN}{progress_bar} "
                f"{format_size(current_size)}/{format_size(total_size)} "
                f"({file_count} files) "
                f"[{format_size(transfer_rate)}/s] "
                f"ETA: {format_time(eta)}{Style.RESET_ALL}"
            )
            
            print(status, end='', flush=True)

            if process.poll() is not None:
                break

        current_size, file_count = get_current_backup_size(backup_location, start_time)
        print()
        
        if current_size > 0:
            end_time = time.time()
            total_time = end_time - start_time
            print(f"\n{Fore.GREEN}Backup completed successfully!{Style.RESET_ALL}")
            
            if exclude_android:
                print(f"{Fore.YELLOW}Note: Some protected files in Android folder were skipped{Style.RESET_ALL}")
            
            print(f"Summary:")
            # print(f" - Total files backed up: {file_count} files ({format_size(current_size)})")
            print(f" - Elapsed time: {format_time(total_time)}")
            # print(f" - Average speed: {format_size(current_size/total_time)}/s")
            print(f"{Fore.WHITE} - Backup location: {backup_location}{Style.RESET_ALL}")
            
            if os.path.exists(error_log_path) and os.path.getsize(error_log_path) > 0:
                print(f"{Fore.YELLOW} - Some files were skipped - see backup_errors.log for details{Style.RESET_ALL}")
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            try:
                with open(os.path.join(backup_location, "backup_completed.txt"), "w") as f:
                    f.write(f"Backup completed on {timestamp}\n")
                    f.write(f"Device: {device_name}\n")
                    f.write(f"Total files: {file_count}\n")
                    f.write(f"Total size: {format_size(current_size)}\n")
                    f.write(f"Elapsed time: {format_time(total_time)}\n")
                    if exclude_android:
                        f.write(f"Note: Android folder was excluded due to permission restrictions\n")
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Could not create completion file: {e}{Style.RESET_ALL}")
            
            print("")
            input("Backup complete! Press Enter to exit...")
            return True
        else:
            print(f"\n{Fore.RED}Backup failed - no files were transferred{Style.RESET_ALL}")
            print("")
            input("Press Enter to exit...")
            return False
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Backup interrupted by user.{Style.RESET_ALL}")
        if process and process.poll() is None:
            process.terminate()
        print("")
        input("Press Enter to exit...")
        return False

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
        
        success = perform_backup_with_progress(
            device_name,
            source_path,
            backup_location,
            total_size,
            exclude_android
        )
        
        if not success and dir_created_by_us:
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
    print(f"{Fore.GREEN}{'Android Archiver v1.4 (github/mirbyte)':^60}{Style.RESET_ALL}")
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
