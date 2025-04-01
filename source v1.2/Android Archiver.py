import os
import subprocess
import time
import sys
import shutil
from datetime import datetime, timedelta
from colorama import init, Fore, Style
import re
import platform
import configparser

# Initialize colorama
init()

# Get the correct base directory
if getattr(sys, 'frozen', False):
    # Running as executable
    CURRENT_DIR = os.path.dirname(sys.executable)
    PLATFORM_TOOLS_PATH = os.path.join(CURRENT_DIR, "platform-tools")
else:
    # Running as script
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    PLATFORM_TOOLS_PATH = os.path.join(CURRENT_DIR, "platform-tools")

ADB_PATH = os.path.join(PLATFORM_TOOLS_PATH, "adb.exe")

if not os.path.exists(PLATFORM_TOOLS_PATH):
    print(f"{Fore.RED}Error: platform-tools directory not found at {PLATFORM_TOOLS_PATH}{Style.RESET_ALL}")
    print("Please ensure the platform-tools folder exists in the same directory")
    print("as this script/executable and contains adb.exe")
    sys.exit(1)

def get_android_device_name():
    """Get the name of the connected Android device using adb and display device info."""
    try:
        # First try standard ADB devices command
        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=10
        )
        
        # If no devices found, try restarting ADB server
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
            
            selection = input("Enter device number: ")
            try:
                device_index = int(selection) - 1
                if 0 <= device_index < len(device_lines):
                    device_name = device_lines[device_index].split("\t")[0]
                else:
                    print(f"{Fore.RED}Invalid selection.{Style.RESET_ALL}")
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
        print(f"  - {Fore.WHITE}Manufacturer: {Fore.GREEN}{get_device_prop('ro.product.manufacturer')}{Style.RESET_ALL}")
        print(f"  - {Fore.WHITE}Model: {Fore.GREEN}{get_device_prop('ro.product.model')}{Style.RESET_ALL}")
        print(f"  - {Fore.WHITE}Android Version: {Fore.GREEN}{get_device_prop('ro.build.version.release')}{Style.RESET_ALL}")
        print(f"  - {Fore.WHITE}Build Number: {Fore.GREEN}{get_device_prop('ro.build.display.id')}{Style.RESET_ALL}")
        print(f"  - {Fore.WHITE}Serial Number: {Fore.GREEN}{device_name}{Style.RESET_ALL}")
        
        return device_name
    except Exception as e:
        print(f"{Fore.RED}Error detecting Android device: {e}{Style.RESET_ALL}")
        return None

def select_backup_location():
    """Select the backup location using interactive prompts."""
    config = load_config()
    
    user_home = os.path.expanduser("~")
    default_backup_dir = os.path.join(user_home, "Documents", "AndroidBackup")
    
    print(f"{Style.RESET_ALL}Default backup location: {Fore.CYAN}{default_backup_dir}{Style.RESET_ALL}")
    
    try:
        if not getattr(sys, 'frozen', False):
            # Running as script - use tkinter file dialog
            import tkinter as tk
            from tkinter import filedialog
            
            print(f"Opening selector window in 3 seconds...")
            time.sleep(3)
            
            root = tk.Tk()
            root.withdraw()
            
            print(f"Please select a backup location in the dialog window...{Style.RESET_ALL}")
            selected_dir = filedialog.askdirectory(title="Select Backup Location")
            
            if selected_dir:
                backup_location = selected_dir
            else:
                backup_location = default_backup_dir
                print(f"{Fore.YELLOW}No location selected, using default.{Style.RESET_ALL}")
            
            root.destroy()
        else:
            # Running as executable - use console interface
            print(f"\n{Fore.GREEN}Available options:{Style.RESET_ALL}")
            print(f"1. Use default location:{Fore.CYAN} {default_backup_dir} {Style.RESET_ALL}")
            print("2. Enter custom path")
            print("3. Browse current directory")
            print("")
            
            choice = input("Select option (1-3): ").strip()
            
            if choice == "1":
                backup_location = default_backup_dir
            elif choice == "2":
                backup_location = input("Enter full path: ").strip()
                if not backup_location:
                    backup_location = default_backup_dir
                    print(f"{Fore.YELLOW}No path entered, using default.{Style.RESET_ALL}")
            elif choice == "3":
                print(f"\n{Fore.GREEN}Current directory contents:{Style.RESET_ALL}")
                dir_items = [item for item in os.listdir('.') if os.path.isdir(item)]
                for i, item in enumerate(dir_items):
                    print(f"{i+1}. {item}")
                selected = input("\nEnter directory number or name (or press Enter for default): ").strip()
                if selected.isdigit() and 1 <= int(selected) <= len(dir_items):
                    selected_item = dir_items[int(selected)-1]
                    backup_location = os.path.abspath(selected_item)
                elif selected:
                    if os.path.isdir(selected):
                        backup_location = os.path.abspath(selected)
                    else:
                        print(f"{Fore.RED}Directory not found. Using default.{Style.RESET_ALL}")
                        backup_location = default_backup_dir
                else:
                    backup_location = default_backup_dir
                    print(f"{Fore.YELLOW}No selection made, using default.{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Invalid choice. Using default location.{Style.RESET_ALL}")
                backup_location = default_backup_dir
            
    except Exception as e:
        print(f"{Fore.YELLOW}Error selecting location: {e}. Using default location.{Style.RESET_ALL}")
        backup_location = default_backup_dir
    
    print(f"{Fore.CYAN}Backup location: {backup_location}{Style.RESET_ALL}")
    
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
        return select_backup_location()

    # Check for network drives
    if backup_location.startswith('\\\\'):
        print(f"{Fore.YELLOW}Warning: Network drive selected. Performance may be slower.{Style.RESET_ALL}")
        confirm = input("Continue with network backup? (y/n): ").lower()
        if confirm != 'y':
            return select_backup_location()
    
    # disk space check
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
            
        if free_space < 10 * 1024**3:  # 10GB in bytes
            print(f"{Fore.YELLOW}Warning: Less than 10GB free space ({format_size(free_space)}) in backup location.{Style.RESET_ALL}")
            confirm = input("Continue anyway? (y/n): ").lower()
            if confirm != 'y':
                return select_backup_location()
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not verify free space: {e}{Style.RESET_ALL}")

    if not os.path.exists(backup_location):
        try:
            os.makedirs(backup_location)
        except Exception as e:
            print(f"{Fore.RED}Failed to create backup directory: {e}{Style.RESET_ALL}")
            return select_backup_location()

    return backup_location

def get_total_size():
    """Prompt the user for the total size of the /sdcard directory on the Android device."""
    while True:
        try:
            user_input = input(f"{Style.RESET_ALL}Enter estimated backup size in GB: ")
            estimated_gb = float(user_input)
            if estimated_gb <= 0:
                print(f"{Fore.RED}Size must be greater than 0.{Style.RESET_ALL}")
                continue
            return estimated_gb * 1024 * 1024 * 1024
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a numeric value.{Style.RESET_ALL}")

def get_android_storage_paths(device_name):
    """Get all possible storage paths on the Android device with improved robustness."""
    # Primary paths we want to check (in order of preference)
    preferred_paths = [
        "/sdcard",
        "/storage/emulated/0",
        "/storage/self/primary"
    ]
    secondary_paths = [
        "/mnt/sdcard",
        "/mnt/storage"
    ]
    
    try:
        # Try getting EXTERNAL_STORAGE first
        result = subprocess.run(
            [ADB_PATH, "-s", device_name, "shell", "echo $EXTERNAL_STORAGE"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=10
        )
        primary_path = result.stdout.strip()
        if primary_path and primary_path not in preferred_paths:
            preferred_paths.insert(0, primary_path)
        
        # Verify which paths actually exist
        valid_paths = []
        for path in preferred_paths + secondary_paths:
            try:
                result = subprocess.run(
                    [ADB_PATH, "-s", device_name, "shell", f"test -d {path} && echo exists"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=5
                )
                if "exists" in result.stdout:
                    valid_paths.append(path)
            except Exception:
                continue
        
        # Return only verified paths, with /sdcard first if it exists
        if valid_paths:
            # Sort to put /sdcard first if it exists
            valid_paths.sort(key=lambda x: x != "/sdcard")
            return valid_paths
        else:
            return ["/sdcard"]  # Fallback to /sdcard even if we couldn't verify
        
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not detect storage paths: {e}. Using fallback paths.{Style.RESET_ALL}")
        return ["/sdcard"]  # Default fallback

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
        # Check device state
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

def get_free_space(path):
    """Get free space in bytes for given path (cross-platform)"""
    if platform.system() == 'Windows':
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(path), 
            None, 
            None, 
            ctypes.pointer(free_bytes)
        )
        return free_bytes.value
    else:
        stat = os.statvfs(path)
        return stat.f_bavail * stat.f_frsize

def verify_storage_paths(device_name, paths):
    """Verify which storage paths actually exist on the device."""
    valid_paths = []
    for path in paths:
        try:
            result = subprocess.run(
                [ADB_PATH, "-s", device_name, "shell", f"test -d {path} && echo exists"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5
            )
            if "exists" in result.stdout:
                valid_paths.append(path)
        except Exception:
            continue
    return valid_paths if valid_paths else paths[:1]  # Return at least one path


def cleanup_interrupted_backup(backup_location):
    """Clean up partially transferred files after an interrupted backup."""
    if os.path.exists(backup_location):
        print(f"{Fore.YELLOW}Cleaning up interrupted backup...{Style.RESET_ALL}")
        shutil.rmtree(backup_location)
    else:
        print(f"No backup files found. Skipping cleanup.")


def copy_files_from_android(device_name, backup_location):
    try:
        start_time = time.time()
        last_update_time = start_time  # Initialize last_update_time here
        
        if not check_device_compatibility(device_name):
            print(f"{Fore.RED}Device compatibility check failed{Style.RESET_ALL}")
            return
            
        print(f"\n{Fore.GREEN}Backup Type:{Style.RESET_ALL}")
        print("1. Full backup (entire /sdcard)")
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
                    return
                
                print(f"\n{Fore.CYAN}Available folders in /sdcard:{Style.RESET_ALL}")
                for i, folder in enumerate(folders, 1):
                    print(f"{i}. {folder}")
                
                # Get user selection
                selection = input("\nSelect folder number: ").strip()
                try:
                    folder_index = int(selection) - 1
                    if 0 <= folder_index < len(folders):
                        source_path = f"/sdcard/{folders[folder_index]}"
                    else:
                        print(f"{Fore.RED}Invalid selection{Style.RESET_ALL}")
                        return
                except ValueError:
                    print(f"{Fore.RED}Please enter a valid number{Style.RESET_ALL}")
                    return
            except Exception as e:
                print(f"{Fore.RED}Error listing folders: {e}{Style.RESET_ALL}")
                return
        else:
            # Default to full backup
            source_path = "/sdcard"
            
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
                total_size = estimated_gb * 1024**3  # Convert GB to bytes
                break
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number{Style.RESET_ALL}")
                
        # Add verification that source_path exists on device
        try:
            result = subprocess.run(
                [ADB_PATH, "-s", device_name, "shell", f"test -d {source_path} && echo exists"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "exists" not in result.stdout:
                print(f"{Fore.RED}Error: Source path {source_path} not found on device{Style.RESET_ALL}")
                return
        except Exception as e:
            print(f"{Fore.RED}Error verifying source path: {e}{Style.RESET_ALL}")
            return

        # Just replace "/sdcard" with "source_path" in the subprocess.Popen call:
        process = subprocess.Popen(
            [ADB_PATH, "-s", device_name, "pull", source_path, backup_location],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        
        # Monitor the backup progress
        last_size = 0
        last_update_time = start_time
        last_status_length = 0
        
        while True:
            # Check the size of the backup directory periodically
            time.sleep(1)  # Update progress every second
            
            try:
                current_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, _, filenames in os.walk(backup_location)
                                for filename in filenames)
            except (FileNotFoundError, PermissionError):
                continue
                
            progress = min((current_size / total_size) * 100, 100.0)
            
            # Calculate transfer rate
            current_time = time.time()
            elapsed_time = current_time - start_time  # Calculate total elapsed time
            time_diff = current_time - last_update_time
            if time_diff >= 1:  # Update rate calculation every second
                size_diff = current_size - last_size
                transfer_rate = size_diff / time_diff
                last_size = current_size
                last_update_time = current_time
                if progress > 0:
                    eta = (elapsed_time / progress) * (100 - progress)
                else:
                    eta = 0
                
                # Create progress display with optimized format
                progress_bar = draw_progress_bar(progress, width=30)
                status = (
                    f"\r{Fore.CYAN}{progress_bar} "
                    f"{format_size(current_size)}/{format_size(total_size)} "
                    f"[{format_size(transfer_rate)}/s] "
                    f"ETA: {format_time(eta)}{Style.RESET_ALL}"
                )
                
                print(status, end='', flush=True)
                last_status_length = len(status) - len(Fore.CYAN) - len(Style.RESET_ALL)
            
            if process.poll() is not None:
                break
        
        # Wait for the process to complete
        stdout, stderr = process.communicate()
        
        # Print final status with newline
        print()  # Add newline after completion
        
        if process.returncode == 0:
            end_time = time.time()
            total_time = end_time - start_time
            print(f"\n{Fore.GREEN}Backup completed successfully!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Summary:{Style.RESET_ALL}")
            print(f"  - Total files backed up: {format_size(current_size)}")
            print(f"  - Elapsed time: {format_time(total_time)}")
            print(f"  - Average speed: {format_size(current_size/total_time)}/s")
            print(f"{Fore.WHITE}  - Backup location: {backup_location}{Style.RESET_ALL}")
            
            # Create a timestamp file to mark successful backup
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            with open(os.path.join(backup_location, "backup_completed.txt"), "w") as f:
                f.write(f"Backup completed on {timestamp}\n")
                f.write(f"Device: {device_name}\n")
                f.write(f"Total size: {format_size(current_size)}\n")
                f.write(f"Elapsed time: {format_time(total_time)}\n")
        else:
            print(f"\n{Fore.RED}Backup failed with error: {stderr}{Style.RESET_ALL}")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Backup interrupted by user.{Style.RESET_ALL}")
        if process and process.poll() is None:
            process.terminate()
            try:
                cleanup_interrupted_backup(backup_location)
            except Exception as e:
                print(f"{Fore.YELLOW}Cleanup failed: {e}{Style.RESET_ALL}")
        print("")
        input("Press Enter to exit...")
        return
    
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
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def draw_progress_bar(progress, width=50):  # Default width reduced to 30
    """Draw a progress bar with the given progress percentage."""
    filled_width = int(width * progress / 100)
    bar = '█' * filled_width + '░' * (width - filled_width)
    return f"[{bar}] {progress:.1f}%"  # Reduced decimal places to 1


def load_config():
    """Load configuration file if it exists, otherwise return default config."""
    config_path = os.path.join(CURRENT_DIR, "android_archiver.cfg")
    config = configparser.ConfigParser()
    
    try:
        if os.path.exists(config_path):
            config.read(config_path)
            # Expand environment variables in backup_location
            if 'DEFAULT' in config and 'backup_location' in config['DEFAULT']:
                config['DEFAULT']['backup_location'] = os.path.expandvars(config['DEFAULT']['backup_location'])
            return config
        # Create default config if running as executable
        if getattr(sys, 'frozen', False):
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
                return config
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Could not create config file: {e}{Style.RESET_ALL}")
                return config
        
        # For script mode, return empty config
        return config
        
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Error loading config: {e}. Using defaults.{Style.RESET_ALL}")
        return config



# BANNERRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR
def main():
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'Android Archiver v1.2 (github/mirbyte)':^60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    
    try:
        # Initialize
        if not check_adb_version():
            print(f"{Fore.RED}ADB version check failed{Style.RESET_ALL}")
            return
            
        device_name = get_android_device_name()
        if not device_name:
            return
            
        backup_location = select_backup_location()
        if not backup_location:
            return
            
        copy_files_from_android(device_name, backup_location)
    except Exception as e:
        print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
    
    print("")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()

