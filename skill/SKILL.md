---
name: frames-cli
description: Frame screenshots with Apple device bezels using the `frames` CLI. Use this skill when the user asks to frame screenshots, add device frames to images, create framed mockups, or batch-process screenshot directories. Triggers on "frame this screenshot", "add bezels", "frame these images", "device mockup", or any request involving putting screenshots inside Apple device frames via the command line.
---

# Apple Frames CLI

`frames` is a Python CLI that frames device screenshots with Apple product bezels. It replicates the Apple Frames shortcut functionality for terminal and AI agent workflows.

## Quick Reference

```bash
# Frame a single screenshot (auto-detect device, save as name_framed.png)
frames screenshot.png

# Frame all PNGs in a directory
frames /path/to/screenshots/*.png

# Frame all images in a folder (expands directory to all image files)
frames ~/Screenshots/

# Frame with a specific color
frames -c "Cosmic Orange" screenshot.png

# Frame with random colors
frames -c random *.png

# Frame and merge side by side
frames -m screenshot1.png screenshot2.png

# Frame, merge with custom spacing, save to specific dir
frames -m -s 80 -o /output/dir/ *.png

# Merge in batches of 3 (15 files → 5 merged images)
frames -b 3 *.png

# Batch merge with custom spacing and output directory
frames -b 4 -s 80 -o /output/ *.png

# Frame and copy to clipboard (macOS)
frames --copy screenshot.png

# Force a specific device frame (skips variant auto-resolution)
frames -d "iPhone 17 Pro Portrait" screenshot.png

# Show device info without framing
frames info screenshot.png

# Scan a folder for device matches
frames info ~/Screenshots/

# JSON output (for piping to other tools)
frames --json screenshot.png

# List all supported devices
frames list

# Show available colors for a device
frames list-colors "17 Pro"

# Browse/set default colors (interactive TUI)
frames colors

# Save to /framed/ subfolder
frames -f screenshot.png

# Save to custom subfolder
frames --subfolder mockups screenshot.png

# Download + configure assets (interactive)
frames setup

# Or point to existing assets folder
frames setup /path/to/Frames

# Verbose output
frames -v screenshot.png
```

## Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output (for AI agents) |
| `--no-color` | Disable ANSI colors (also respects `NO_COLOR` env var) |
| `-v, --verbose` | Verbose output (variant resolution, resize, mask info) |
| `--assets PATH` | Override assets directory |
| `--version` | Print version and exit |

## Default Behavior

- **Output**: `originalname_framed.png` in the same directory as the source file
- **Device detection**: Automatic from screenshot pixel width (+ height for overlap disambiguation)
- **Color**: First color in the device's color array, overridable via `frames colors` TUI or config
- **Variant resolution**: Newest device frame is default when multiple devices share a resolution; skipped when `--device` is explicitly set
- **Directory input**: Passing a directory expands to all image files inside it (png, jpg, jpeg, heic, tiff, webp)

## Configuration

Config file: `~/.config/frames/config.json`

Set up via `frames setup` (downloads assets interactively) or `frames setup /path/to/assets`. Re-run `frames setup` to re-download if assets get corrupted. Keys:

- `assets_path` — path to the Frames assets folder
- `default_colors` — per-device default color choices (set via `frames colors` TUI)
- `use_subfolder` — `true` for "framed", or a custom string like "mockups"

Environment variables:
- `FRAMES_ASSETS` — override assets directory (takes precedence over config, lower than `--assets` flag)
- `NO_COLOR` — disable ANSI color output

## For AI Agent Pipelines

Use `--json` for machine-readable output:

```bash
# Get device info as JSON
frames --json info screenshot.png

# Frame and get output path as JSON
frames --json screenshot.png

# Frame, copy to clipboard, and get valid JSON (clipboard message goes to stderr)
frames --json --copy screenshot.png
```

The JSON output includes: source path, detected device, color used, dimensions, and output path. The `--copy` flag's success/failure message prints to stderr so it never corrupts JSON output.

## Batch Processing Pattern

Point the CLI at a directory of screenshots:

```bash
# Frame everything, output to a separate directory
frames -o ~/framed/ ~/screenshots/*.png

# Frame and merge all into one image
frames -m -o ~/framed/ ~/screenshots/*.png

# Random colors for variety
frames -c random -o ~/framed/ ~/screenshots/*.png

# Merge in sequential batches of N (e.g. 15 files → 5 merged images)
frames -b 3 ~/screenshots/*.png

# Batch merge with random colors
frames -b 3 -c random *.png
```

`--batch` / `-b` implies `--merge` — no need to pass both. Batch size must be >= 2. If the total isn't evenly divisible, the last batch contains the remainder. Output files are named `merged_1_framed.png`, `merged_2_framed.png`, etc. JSON output includes a `batches` array with per-batch counts and paths.

## Error Handling

- Corrupt/non-image files are skipped with a clean error; valid files in the same batch still process
- Corrupted assets JSON prints a targeted error instead of a traceback
- Read-only output directories are caught with a clear message
- Images exceeding 50,000px in either dimension are refused; images over 20,000px trigger a warning
- Missing Pillow dependency prints an install instruction and exits cleanly

## Assets

On first run, the CLI auto-detects missing or outdated assets and offers to download Apple Frames 4 (~40 MB) from `cdn.macstories.net`. Run `frames setup` to download interactively, or re-download if assets get corrupted.

Default location: `~/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/Frames/`

The folder contains `NewFrames.json` (device dictionary), `version.txt`, and hundreds of frame/mask PNGs.

Override with `--assets /path/to/assets/`, `FRAMES_ASSETS` env var, or `frames setup /path`.

## Supported Devices (v1.1)

iPhone 17 family (17, 17 Pro, 17 Pro Max), iPhone Air, iPhone 16 family (16, 16 Plus, 16 Pro, 16 Pro Max), iPhone 12-13 family, iPhone 8/SE, iPad Pro (2018-2024), iPad Air, iPad mini, MacBook Neo, MacBook Pro M5 14"/16", MacBook Pro 2021, MacBook Air M5 13"/15", MacBook Air 2022, iMac M4 (7 colors), Studio Display, Studio Display XDR, Apple Watch Series 10-11, Apple Watch Ultra 2024, Apple Watch Ultra 3.
