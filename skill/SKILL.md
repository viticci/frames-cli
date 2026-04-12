---
name: frames-cli
description: Frame screenshots with the `frames` CLI. Use this skill when the user asks to add Apple device bezels, frame screenshots, create device mockups, inspect screenshot/device matches, or batch-process screenshot folders with the command line.
---

# Apple Frames CLI

`frames` 1.2.5 is a single-file Python CLI that applies Apple device bezels to screenshots, auto-detects devices from screenshot dimensions, applies masks when needed, and can merge multiple framed results into one composite image.

## What Agents Should Know

- `frames` is the default command. `frames screenshot.png` and `frames frame screenshot.png` are equivalent.
- Use `frames --json` for automation. JSON stays valid even with `--copy`; clipboard status messages go to `stderr`.
- Device support comes from the installed asset bundle, not hardcoded names in this skill. Use `frames list` and `frames list-colors` as the source of truth when exact names matter.
- On macOS, the default asset location is the Apple Frames shortcut folder in iCloud Drive. That avoids downloading a second copy when the user already has the shortcut assets installed.

## Quick Reference

```bash
# Frame one screenshot
frames screenshot.png

# Frame every top-level image in a folder
frames ~/Screenshots/

# Pick a specific color or randomize colors
frames -c "Cosmic Orange" screenshot.png
frames -c random *.png

# Force an exact frame instead of auto-resolving the newest variant
frames -d "iPhone 15 Pro Portrait" screenshot.png

# Merge framed outputs side by side
frames -m shot1.png shot2.png

# Merge without proportional physical scaling
frames -m --no-scale shot1.png shot2.png

# Batch merge sequential groups
frames -b 3 *.png

# Save to a separate output directory
frames -o ~/Framed *.png

# Save to a subfolder next to originals
frames -f *.png
frames --subfolder mockups *.png

# Inspect matches without framing
frames info screenshot.png
frames --json info ~/Screenshots/

# Discover supported devices and colors
frames list
frames list-colors "17 Pro"

# Manage default colors
frames colors

# Diagnose asset/config problems
frames doctor

# Download or re-point assets
frames setup
frames setup /path/to/Frames
```

## Current Feature Surface

- Auto-detect devices from screenshot width, with height-based overlap disambiguation where needed.
- Resolve width-sharing devices to the newest default frame automatically. Pass `--device` to skip variant resolution.
- Apply frame colors by exact name, partial numeric index, or `random`.
- Apply masks when the asset entry requires clipping.
- Merge multiple framed outputs with physical-size normalization by default.
- Use `--no-scale` to disable proportional scaling and keep native framed sizes when merging.
- Use `--batch N` to merge sequential groups. `--batch` implies merge and `N` must be at least `2`.
- Save next to originals, into `--output`, or into a validated single-name subfolder via `-f` or `--subfolder`.
- Copy a single output to the macOS clipboard with `--copy`.
- Inspect screenshots and folders with `info`.
- Diagnose assets and config with `doctor`.
- Save per-device default colors with `colors`.

## Command Notes

- Global flags:
  - `--json` for machine-readable output
  - `--no-color` to disable ANSI color
  - `--assets PATH` to override asset discovery
  - `-v` / `--verbose` for variant, resize, and mask details
- `frames colors` is interactive in a real terminal. If stdin is not a TTY, or `curses` is unavailable, it falls back to a plain printed color list.
- `frames list-colors` does partial device-name matching. `frames list-colors "17 Pro"` is valid.
- Directory inputs are expanded one level deep only. The CLI scans top-level image files inside the directory; it is not recursive.
- Supported input image extensions are `.png`, `.jpg`, `.jpeg`, `.heic`, `.tiff`, and `.webp`.
- Images larger than `20,000px` on either side trigger a warning. Images larger than `50,000px` are rejected.
- `--subfolder` only accepts a single directory name, not a path like `../out` or `foo/bar`.

## JSON Output Behavior

- `frames --json screenshot.png` returns one framed-image object with fields such as `source`, `device`, `color`, `dimensions`, `frame_size`, `resized`, `masked`, `physicalHeight`, and `output`.
- `frames --json *.png` returns `{ "frames": [...] }` for multiple individual outputs.
- `frames --json -m ...` returns a merged result with `merged`, `count`, and `frames`.
- `frames --json -b N ...` returns `batches`, `batch_size`, `total`, and `frames`.
- When proportional merge scaling is applied, per-frame `scale_factor` values are included in the JSON output.
- `frames --json info ...` returns either one object or a list of objects, including `device`, `primary_match`, `colors`, `color_count`, `has_mask`, `resize_width`, `variants`, and `is_variant`.
- `frames --json doctor` returns asset path/source/version, PNG count, config presence, issues, notes, and suggested next steps.

## Assets and Config

Config file:

```text
~/.config/frames/config.json
```

Config keys:

- `assets_path`: explicit asset folder path
- `default_colors`: saved default frame colors by base device name
- `use_subfolder`: `true` for `framed`, or a custom folder name string

Asset resolution order:

1. `--assets`
2. `FRAMES_ASSETS`
3. `assets_path` from config
4. macOS default: `~/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/Frames`
5. macOS fallback if valid: `~/Library/Application Support/frames/assets`
6. On non-macOS platforms, the standard per-platform app-data directory is the default

Setup behavior:

- `frames setup` downloads the current asset archive from `https://cdn.macstories.net/Frames40.zip`.
- `frames setup /path/to/Frames` points the CLI at an existing asset folder instead of downloading.
- The asset folder must contain `NewFrames.json`, `version.txt`, and the frame/mask PNGs.
- `frames setup --subfolder` and `frames setup --no-subfolder` update the default save behavior in config.
- `frames doctor` is the first command to run when assets were moved, edited, or corrupted.

## Current Supported Device Families

The current v4 asset bundle used by `frames` 1.2.5 includes these primary families:

- iPhone: iPhone 17, iPhone 17 Pro, iPhone 17 Pro Max, iPhone Air, iPhone 16, iPhone 16 Plus, iPhone 12-13 Pro, iPhone 12-13 Pro Max, iPhone 12-13 mini, iPhone 8 / 2020 SE
- iPad: iPad mini 2021, iPad 2021, iPad Air 2020, iPad Pro 2018-2021 11-inch, iPad Pro 2018-2021 12.9-inch, iPad Pro 2024 11-inch, iPad Pro 2024 13-inch
- Mac: MacBook Neo, MacBook Pro 13, MacBook Air 2020, MacBook Air M5 13, MacBook Air M5 15, MacBook Pro M5 14, MacBook Pro M5 16, iMac M4, Studio Display, Studio Display XDR
- Watch: Watch Series 7 41, Watch Series 7 45, Watch Series 11 42, Watch Series 11 46, Watch Ultra 2024, Watch Ultra 3

Current default variant resolution favors the newest matching frame for shared screenshot sizes:

- `iPhone 17 Portrait` resolves to `iPhone 17 Pro Portrait`
- `iPhone 17 Landscape` resolves to `iPhone 17 Pro Landscape`
- `iPhone 17 Pro Max` shares sizes with `iPhone 16 Pro Max`
- `iPhone 16` shares sizes with `iPhone 15 Pro`
- `iPhone 16 Plus` shares sizes with `iPhone 15 Pro Max`
- `MacBook Pro M5` shares sizes with `MacBook Pro 2021`
- `MacBook Air M5 13` shares sizes with `MacBook Air 2022`
- `Studio Display` shares sizes with `Studio Display XDR`
- `Watch Series 11` shares sizes with `Watch Series 10`

If an exact older variant is required, pass `--device` with the exact frame name instead of relying on auto-detection.

## Recommended Agent Workflow

1. Run `frames --json info ...` first when you do not control the screenshot source.
2. If the user asks for a specific device or color, confirm the exact names with `frames list` or `frames list-colors`.
3. Use `frames doctor` before changing config or re-downloading assets.
4. Use `--device` only when the user wants an exact frame, older variant, or a non-default shared-size match.
5. Use `--no-scale` only when the user explicitly wants native framed sizes instead of physically proportionate merges.
