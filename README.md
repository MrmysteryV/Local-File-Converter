# Local-File-Converter
A python app with HTML frontend that allows you to host your own file converter locally on your machine or over your LAN

<img width="461" height="229" alt="image" src="https://github.com/user-attachments/assets/84a8e61e-5cfb-4003-915e-57b11fd8220a" />
<img width="461" height="229" alt="image" src="https://github.com/user-attachments/assets/9712295d-a38d-44a3-b2e7-ec949dd0eeb1" />
<img width="461" height="229" alt="image" src="https://github.com/user-attachments/assets/88cb76dc-4448-476d-b121-eba1ea8f69d0" />


## Features

* Convert images, videos, and audio through a HTML interface.
* Select and convert multiple files of the same input format.
* Preview images and videos before conversion.
* Crop images and videos.
* Clip a section from a video.
* Configure quality, frame rate, video bitrate, audio bitrate, sample rate, GIF frame rate, and GIF looping where supported.
* View live conversion progress.
* Rename converted files before downloading.
* Download files individually or together as a ZIP archive.
* Switch between light and dark themes.
* Run in local-only mode or LAN mode.
* Choose the network mode interactively or through command line arguments.

---

# Compatibility

## Operating Systems

| OS      | Supported  | Notes                                                                                                                        |
| ------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Windows | ✅ Yes      | Primary target and includes an automatic Windows Firewall rule attempt in LAN mode.                                          |
| macOS   | ⚠️ Unknown | Expected to work with Python and FFmpeg installed, but not tested. You may need to allow incoming connections.         |
| Linux   | ⚠️ Unknown | Expected to work with Python and FFmpeg installed, but not tested. Firewall configuration depends on the distribution. |

## Python Version

* Tested with **Python 3.12**.

## Browser

Use a modern version of Chrome, Edge, Firefox, or Safari. JavaScript, file uploads, and browser downloads must be enabled.

---

# Supported Formats

Actual codec and format support depends on the installed FFmpeg build. Some formats, particularly HEIF, HEIC, AVIF, RAW, and SVG, may require additional codec support or may not be available as an output format in every FFmpeg build.

| Type   | Formats shown by the converter                                         |
| ------ | ---------------------------------------------------------------------- |
| Images | WEBP, JFIF, JPEG, JPG, PNG, GIF, SVG, TIFF, BMP, HEIF, HEIC, RAW, AVIF |
| Video  | MP4, MOV, MKV, AVI, WMV, WEBM, FLV, AVCHD, MPEG-2, 3GP, Animated GIF   |
| Audio  | MP3, OGG                                                               |

---

# Installation and Setup

## 1. Install Python 3.12 (should work with any other version)

Download Python from [python.org](https://www.python.org/downloads/).

On Windows, enable **Add Python to PATH** during installation. The standard Python launcher can then be used with `py -3.12`.

## 2. Install FFmpeg

FFmpeg and FFprobe must be installed separately and available through the system `PATH`.

### Windows

1. Open the [FFmpeg download page](https://ffmpeg.org/download.html).
2. Select a Windows build provider and download a complete build.
3. Extract the archive.
4. Add the extracted `bin` directory to the Windows user or system `PATH`.
5. Close and reopen Command Prompt or PowerShell.

### macOS with Homebrew

Install Homebrew if it is not already installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install FFmpeg:

```bash
brew install ffmpeg
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

### Arch Linux

```bash
sudo pacman -S ffmpeg
```

---

## 3. Download the python file from the repository

Download main.py by clicking on it and going to "Download Raw" in the top right corner

## 4. Install Python Dependencies

### Windows

```bash
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r flask waitress
```

### macOS / Linux

```bash
python3.12 -m pip install --upgrade pip
python3.12 -m pip install -r flask waitress
```

# Running the Converter

## Interactive Mode

Start the program without a network mode argument:

### Windows

```bash
py -3.12 main.py
```

### macOS / Linux

```bash
python3.12 main.py
```

The program will ask:

```text
Enter LAN to allow other devices, or LOCAL for this machine only [LOCAL]:
```

* Enter `LOCAL` to allow access only from the host computer.
* Enter `LAN` to allow devices on the same local network.
* Press Enter without typing anything to use local only mode.

---

## Local-Only Mode

### Windows

```bash
py -3.12 main.py local
```

### macOS / Linux

```bash
python3.12 main.py local
```

Open:

```text
http://127.0.0.1:8089
```

You can also use the shortcut flag:

```bash
python main.py --local
```

---

## LAN Mode

### Windows

```bash
py -3.12 main.py lan
```

### macOS / Linux

```bash
python3.12 main.py lan
```

The code will print a LAN address similar to:

```text
LAN access: http://192.168.1.25:8089
```

Open that address on another device connected to the same network.

You can also use:

```bash
python main.py --lan
```

---

## Other Command-Line Forms

The mode names are case insensitive.

```bash
python main.py lan
python main.py local
python main.py --mode lan
python main.py --mode local
python main.py --network-mode lan
python main.py --network-mode local
python main.py --lan
python main.py --local
```

Do not give conflicting modes, such as `local --lan`.

---

# Starting from a Script or Shortcut

Command line mode selection stops an interactive prompt when the converter is launched automatically.

## Windows Batch File

Create `run_converter.bat` in the same directory:

```bat
@echo off
cd /d "%~dp0"
py -3.12 "%~dp0main.py" %*
pause
```

Run it without an argument to show the normal prompt:

```bat
run_converter.bat
```

Run directly in LAN mode:

```bat
run_converter.bat lan
```

Run directly in local mode:

```bat
run_converter.bat local
```

A desktop shortcut can point to the batch file. Add `lan` or `local` after the batch file path in the shortcut target to select a mode automatically.

## macOS / Linux Shell Script

Create `run_converter.sh`:

```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3.12 "$SCRIPT_DIR/main.py" "$@"
```

Make it executable:

```bash
chmod +x run_converter.sh
```

Show the normal prompt:

```bash
./run_converter.sh
```

Start in LAN mode:

```bash
./run_converter.sh lan
```

Start in local mode:

```bash
./run_converter.sh local
```

---

# How to Use

1. Start the converter in local or LAN mode.
2. Open the address printed in the terminal.
3. Drop files into the upload area or click it to browse.
4. Select the input format if it was not detected automatically.
5. Select an output format.
6. Open **Preview & Edit** to preview, crop, or clip a file where supported.
7. Expand the file's output settings to adjust available conversion options.
8. Press **Convert Files**.
9. Keep the page open while the upload and conversion are in progress.
10. Rename the completed files if needed.
11. Download each file separately or select **Download All (ZIP)**.

All files selected in one batch must have the same input extension. Use a separate conversion batch for files with different input formats.

---

# Preview and Editing

## Images

The preview window can be used to select a crop area before conversion. Crop dimensions are passed to FFmpeg when the conversion starts.

## Videos

The preview window supports:

* Normal browser video playback.
* Capturing the current frame for crop selection.
* Selecting a crop region.
* Setting clip start and end times.
* Previewing the crop area.

Preview availability depends on whether the browser can decode the source video. FFmpeg may still be able to convert a file that the browser cannot preview.

---

# Output Settings

Available settings depend on the selected output format and may include:

| Setting       | Description                                                                  |
| ------------- | ---------------------------------------------------------------------------- |
| Quality       | Image quality or video CRF value, depending on the output type.              |
| FPS           | Output video frame rate.                                                     |
| Video Bitrate | Output video bitrate, such as `5000k` or `5M`.                               |
| Audio Bitrate | Output audio bitrate, such as `128k`, `192k`, or `320k`.                     |
| Sample Rate   | Audio sample rate, commonly `44100` or `48000`.                              |
| GIF FPS       | Frame rate for an animated GIF. Lower values generally create smaller files. |
| GIF Loop      | Loop forever or play once.                                                   |

Cropping and output dimensions are controlled through **Preview & Edit**. The expand arrow is hidden when a format has no additional settings to display.

---

# Network and Privacy Notes

## Local Mode

In local mode, the browser and converter run on the same computer. Files are uploaded to the local Python server, processed by FFmpeg on that computer, and stored temporarily in the project's `temp_conversions` directory.

## LAN Mode

In LAN mode, a file selected on another device is transferred across the local network to the computer running the converter. It is processed on the host computer rather than by an external cloud service.

LAN mode does **not** include authentication, user accounts, access controls, or HTTPS. Use it only on a trusted private network.

* Do not expose port `8089` directly to the internet.
* Do not configure router port forwarding for the converter.
* Avoid public Wi-Fi, guest networks, or other untrusted networks.
* Stop the program when LAN access is no longer needed.

Temporary conversion folders are cleared when the server starts and during normal shutdown. Downloads and session resets also remove temporary files. If the process is terminated abnormally, remaining temporary files are cleared the next time the program starts.

---

# Firewall Setup for LAN Mode

## Windows

In LAN mode, the program attempts to add an inbound Windows Firewall rule for TCP port `8089`. Adding the rule may require running the program as Administrator once.

If the automatic rule cannot be added, open Command Prompt or PowerShell as Administrator and run:

```bat
netsh advfirewall firewall add rule name="LocalFileConverter_8089" dir=in action=allow protocol=TCP localport=8089
```

To remove that rule later:

```bat
netsh advfirewall firewall delete rule name="LocalFileConverter_8089"
```

## Ubuntu with UFW

```bash
sudo ufw allow 8089/tcp
```

Remove the rule later with:

```bash
sudo ufw delete allow 8089/tcp
```

## macOS

macOS may display a firewall prompt when Python starts listening for incoming connections. Select **Allow** when using LAN mode on a trusted network.

---

# Stopping the Server

Return to the terminal running the converter and press:

```text
Ctrl + C
```

Close any browser tabs connected to the converter. In LAN mode, stopping the Python process immediately removes network access.

---

# Notes

* Conversion is powered by the FFmpeg installation on the host computer.
* Output quality and available codecs vary by FFmpeg build.
* Batch files must share the same input extension.
* LAN mode is intended only for trusted local networks.
* Do not close or reload the browser page while an upload or conversion is running.
* The converter is not intended to be exposed as a public internet service.
