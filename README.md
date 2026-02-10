# Android-Archiver
Fast and reliable Android device backup tool for Windows. Transfer files from your Android device to your PC faster than Windows File Explorer. Android Platform Tools are official and provided unmodified - you can download them yourself from [Google's official site](https://developer.android.com/tools/releases/platform-tools) if you prefer.

[![License](https://img.shields.io/github/license/mirbyte/Android-Archiver?color=34A853&maxAge=604800)](https://raw.githubusercontent.com/mirbyte/Android-Archiver/master/LICENSE)
![Size](https://img.shields.io/github/repo-size/mirbyte/Android-Archiver?label=size&color=34A853&maxAge=86400)
![Last Commit](https://img.shields.io/github/last-commit/mirbyte/Android-Archiver?color=34A853&label=repo+updated)

## Features

### Core Functionality
- **Full or Partial Backups** - Backup entire `/sdcard` or select specific folders
- **Fast Transfer** - Uses ADB protocol for faster speeds than MTP
- **Real-time Progress** - Live transfer rate, progress bar, and ETA
- **Smart Existing Backup Handling** - Merge, replace, or cancel when files already exist
- **Safe Operation** - Critical system directory protection and confirmation prompts

### Safety Features
- Prevents backup to critical system directories
- Disk space checking with warnings
- Safe cleanup on interruption (only if directory was created by the tool)
- Network drive detection and performance warnings
- Automatic USB debugging verification

## Requirements

- Windows 10 or later
- Android device with USB debugging enabled
- USB cable for device connection

## Installation
1. Download the project zip
2. Unzip and run the .exe
3. The folder structure should be:
   ```
   Android-Archiver/
   ├── Android Archiver.exe
   └── platform-tools/
       ├── adb.exe
       ├── AdbWinApi.dll
       ├── AdbWinUsbApi.dll
       └── ...
   ```
4. Keep the `.exe` and `platform-tools` folder together

## Usage
### First Time Setup

1. **Enable USB Debugging on your Android device:**
   - Go to Settings → About Phone
   - Tap "Build Number" 7 times to enable Developer Options
   - Go to Settings → Developer Options
   - Enable "USB Debugging"

2. **Connect your device:**
   - Connect via USB cable
   - Set USB mode to "File Transfer" or "MTP"
   - Approve the USB debugging authorization prompt on your device

### Running a Backup

1. Run `Android Archiver.exe`
2. Device information will be displayed automatically
3. Choose backup location (default: `Documents/AndroidBackup`)
4. If location already has files, choose to merge, replace, or cancel
5. Select backup type:
   - **Option 1**: Full backup (entire `/sdcard`)
   - **Option 2**: Partial backup (select specific folder)
6. Enter estimated backup size in GB
7. Wait for transfer to complete

### Example Output

```
============================================================
           Android Archiver v1.2 (github/mirbyte)          
============================================================
ADB Version: 35.0.1

Device Information:
 - Manufacturer: Samsung
 - Model: SM-G991B
 - Android Version: 14
 - Build Number: UP1A.231005.007
 - Serial Number: R5CT1234567

Backup Location:
Default: C:\Users\YourName\Documents\AndroidBackup

Press Enter to use default, or type a custom path: 

[████████████████████████░░░░░░] 82.3% 24.5 GB/29.8 GB [156.2 MB/s] ETA: 00:00:34
```

## Platform Tools

This application bundles the [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools), which are provided by Google and distributed under the Android Software Development Kit License.

**Platform Tools are included unmodified** from the official Android developer distribution. The tools are redistributed here for convenience and are subject to Google's licensing terms.

## Configuration

The application creates a config file `android_archiver.cfg` on first run. You can edit this to change the default backup location:

```ini
[DEFAULT]
backup_location = C:\Users\YourName\Documents\AndroidBackup
```

Environment variables are supported:
```ini
backup_location = %USERPROFILE%\Documents\AndroidBackup
```

## Troubleshooting

### Device Not Detected

- Ensure USB debugging is enabled
- Check that you've authorized the computer on your device
- Try a different USB cable or port
- Restart ADB server (automatically attempted by the tool)

### Transfer Speed Slower Than Expected

- Use a USB 3.0 or faster port and cable
- Close other applications using the device
- Avoid network drives as backup destinations
- Check if antivirus is scanning files during transfer

### Permission Errors

- Run as administrator if backing up to protected locations
- Ensure the backup location isn't a system directory

## Technical Details

- **Language**: Python 3.x (compiled to Windows executable)
- **ADB Version**: Latest as of 10.2.2026 (DD.MM.YYYY)
- **Transfer Method**: ADB pull protocol
- **Progress Tracking**: Moving average over 5 samples for smooth rate display

## Known Issues

- Progress bar sometimes works sometimes not
- File modification times may not be preserved exactly
- Some system files may be skipped due to Android permissions
- Very large transfers (100GB+) may take several hours


## Disclaimer

The author of this software is not responsible for any data loss, device damage, or other issues that may occur while using this application. Use at your own risk. Always ensure you have backups of important data before performing device operations.

## Acknowledgments

- Android Debug Bridge (ADB) by Google
- Colorama for terminal colors
- The Android developer community
- Built with Python
- Packaged with PyInstaller

---

**Repository**: [github.com/mirbyte/Android-Archiver](https://github.com/mirbyte/Android-Archiver)

If you found this project useful, please consider giving a ⭐ !



