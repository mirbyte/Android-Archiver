# Android-Archiver
Fast and reliable Android device backup tool for Windows. Transfer files from your Android device to your PC faster than Windows File Explorer. Android Platform Tools are official and provided unmodified - you can download them yourself from [Google's official site](https://developer.android.com/tools/releases/platform-tools) if you prefer. Please check known issues near the end of README.

[![License](https://img.shields.io/github/license/mirbyte/Android-Archiver?color=34A853&maxAge=604800)](https://raw.githubusercontent.com/mirbyte/Android-Archiver/master/LICENSE)
![Size](https://img.shields.io/github/repo-size/mirbyte/Android-Archiver?label=size&color=34A853&maxAge=86400)
![Last Commit](https://img.shields.io/github/last-commit/mirbyte/Android-Archiver?color=34A853&label=repo+updated)

## Features

### Core Functionality
- **Full or Partial Backups** - Full `/sdcard` (skips `Android/`) or a selected top-level folder
- **Per-folder ADB pulls** - Full backup pulls each top-level item separately instead of one giant `/sdcard` pull
- **Fast Transfer** - Uses ADB protocol for faster speeds than MTP
- **Real-time Progress** - Live transfer rate, progress bar, file count, and current folder
- **Completeness verification** - Compares device vs local file counts after transfer
- **Gap fill / repair** - Re-pulls incomplete subdirectories; streams problem filenames via `adb exec-out`
- **Smart Existing Backup Handling** - Merge, replace, or cancel when files already exist
- **Safe Operation** - Critical system directory protection and confirmation prompts

### Safety Features
- Prevents backup to critical system directories
- Disk space checking with warnings
- Safe cleanup on hard failure (only if the directory was created by the tool and nothing usable transferred)
- Incomplete backups are kept (not deleted) and marked with `backup_incomplete.txt`
- Network drive detection and performance warnings
- Automatic USB debugging verification / ADB server restart

## Requirements

- Windows 10 or later
- Android device with USB debugging enabled
- USB cable for device connection

## Installation
1. [Download](https://github.com/mirbyte/Android-Archiver/archive/refs/heads/main.zip) the project zip
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
   - **Option 1**: Full backup (entire `/sdcard`, excludes `Android/` folder)
   - **Option 2**: Partial backup (select specific folder)
6. Enter estimated backup size in GB (used for the progress bar only)
7. Wait for transfer to complete
8. Review verification output (device vs local file counts). Check `backup_errors.log` if anything was skipped or repaired.

### Example Output

```
============================================================
        Android Archiver v1.5 BETA (github/mirbyte)        
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

Full backup: pulling 15 top-level items (Android/ skipped)

[███████░░░░░░░░░░░░░░░░░░░░░░░] 23.4% 56.12 GB/240.00 GB (3950 files) [120.5 MB/s] | 4/15 Download

Verifying backup completeness...
 - Device files: 12040 | Local files: 12040
 - (Android/ excluded from comparison)

Backup completed successfully!
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

Environment variables are supported using Windows `%VAR%` syntax (expanded with `os.path.expandvars`):

```ini
backup_location = %USERPROFILE%\Documents\AndroidBackup
```

Note: `${USERPROFILE}` style placeholders are **not** expanded on Windows. Use `%USERPROFILE%`.

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
- Gap-fill / per-file streaming of problem names is slower than bulk `adb pull`

### Incomplete Backup / Missing Files

- Read `backup_errors.log` and `backup_incomplete.txt` in the backup folder
- Filenames illegal on Windows (`? : * " < > |`) are streamed via `adb exec-out` into sanitized local names
- Re-run with **merge** to fill gaps, or use a partial backup of just `Download`
- Very long paths may still fail even with extended-path handling

### Permission Errors

- Run as administrator if backing up to protected locations
- Ensure the backup location isn't a system directory
- Protected paths under `Android/` are skipped on full backup by design

## Technical Details

- **Language**: Python 3.x (compiled to Windows executable)
- **Version**: 1.5 BETA
- **Transfer Method**: Per-folder `adb pull`, with subdirectory gap-fill and `adb exec-out cat` fallback for problematic files
- **Progress Tracking**: Destination size sampling with a moving average over 5 samples (progress % depends on your size estimate)
- **Verification**: Device `find` file count vs local file count (`Android/` excluded for full backups)

## Known Issues

- Progress % depends on the manual GB estimate; a bad guess makes the bar misleading (speed/file count are still useful)
- Progress bar and speed can stall during verification or gap-fill (device `find` / subdirectory re-pulls)
- File modification times may not be preserved exactly
- Some files may still be skipped due to Android permissions or unreadable paths
- Very large transfers (100GB+) may take several hours
- Windows MAX_PATH and odd OEM storage layouts can still leave gaps; check verification counts


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
