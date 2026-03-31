---
name: frames-cli
description: Frame screenshots with Apple device bezels using the `frames` CLI. Use this skill when Federico asks to frame screenshots, add device frames to images, create framed mockups, or batch-process screenshot directories. Triggers on "frame this screenshot", "add bezels", "frame these images", "device mockup", or any request involving putting screenshots inside Apple device frames via the command line.
---

# Apple Frames CLI

`frames` is a Python CLI at `~/bin/frames` that frames device screenshots with Apple product bezels. It replicates the Apple Frames shortcut functionality for terminal and AI agent workflows.

## Quick Reference

```bash
# Frame a single screenshot (auto-detect device, save as name_framed.png)
frames screenshot.png

# Frame all PNGs in a directory
frames /path/to/screenshots/*.png

# Frame with a specific color
frames -c "Cosmic Orange" screenshot.png

# Frame with random colors
frames -c random *.png

# Frame and merge side by side
frames -m screenshot1.png screenshot2.png

# Frame, merge with custom spacing, save to specific dir
frames -m -s 80 -o /output/dir/ *.png

# Frame and copy to clipboard (macOS)
frames --copy screenshot.png

# Force a specific device frame
frames -d "iPhone 17 Pro Portrait" screenshot.png

# Show device info without framing
frames info screenshot.png

# JSON output (for piping to other tools)
frames --json screenshot.png

# List all supported devices
frames list

# Show available colors for a device
frames list-colors "17 Pro"
```

## Default Behavior

- **Output**: `originalname_framed.png` in the same directory as the source file
- **Device detection**: Automatic from screenshot pixel width (+ height for overlap disambiguation)
- **Color**: First color in the device's color array (newest/most popular)
- **Variant resolution**: Newest device frame is default when multiple devices share a resolution

## For AI Agent Pipelines

Use `--json` for machine-readable output:

```bash
# Get device info as JSON
frames --json info screenshot.png

# Frame and get output path as JSON
frames --json screenshot.png
```

The JSON output includes: source path, detected device, color used, dimensions, and output path.

## Batch Processing Pattern

Point the CLI at a directory of screenshots:

```bash
# Frame everything, output to a separate directory
frames -o ~/framed/ ~/screenshots/*.png

# Frame and merge all into one image
frames -m -o ~/framed/ ~/screenshots/*.png

# Random colors for variety
frames -c random -o ~/framed/ ~/screenshots/*.png
```

## Assets

The CLI reads frame assets from the Shortcuts iCloud container:
`~/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/NewFrames/`

Override with `--assets /path/to/assets/` or `FRAMES_ASSETS` env var.

## Supported Devices (v1.0)

iPhone 17 family (17, 17 Pro, 17 Pro Max), iPhone Air, iPhone 16 family, iPhone 12-13 family, iPhone 8/SE, iPad Pro (2018-2024), iPad Air, iPad mini, MacBook Neo, MacBook Pro M5 14"/16", MacBook Pro 2021, MacBook Air, iMac, Apple Watch Series 7-10, Apple Watch Ultra.
