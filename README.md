# Apple Frames CLI

A Python command-line tool that frames device screenshots with Apple product bezels. It auto-detects devices from screenshot dimensions, applies colored frames with transparency masks, and can merge multiple framed screenshots side by side. Built as the terminal/AI-agent counterpart to the [Apple Frames](https://www.macstories.net/tag/apple-frames/) shortcut by Federico Viticci.

## Installation

**Requirements:** Python 3 and [Pillow](https://pillow.readthedocs.io/).

```bash
pip3 install Pillow
```

**Install the CLI:**

```bash
cp frames ~/bin/frames
chmod +x ~/bin/frames
```

**Set up assets:**

The CLI needs Apple device frame PNGs and a `NewFrames.json` dictionary. If you already have the Apple Frames shortcut installed, the assets are in your Shortcuts iCloud container:

```bash
frames setup ~/Library/Mobile\ Documents/iCloud~is~workflow~my~workflows/Documents/Frames
```

This saves the path to `~/.config/frames/config.json` so you never have to specify it again.

## Quick Start

```bash
# Frame a screenshot (auto-detects device, saves as name_framed.png)
frames screenshot.png

# Frame all PNGs in a directory
frames *.png

# Frame with a specific color
frames -c "Cosmic Orange" screenshot.png

# Frame with random colors
frames -c random *.png

# Frame and merge side by side
frames -m screenshot1.png screenshot2.png

# Copy framed result to clipboard (macOS)
frames --copy screenshot.png
```

## Commands

### `frame` (default)

Frame one or more screenshots. This is the default command — you can omit the `frame` keyword.

```bash
frames screenshot.png                    # Same as: frames frame screenshot.png
frames -c Silver -m -o ~/output/ *.png
```

### `list`

List all supported devices, grouped by category, with pixel widths and available color counts.

```bash
frames list
```

### `colors`

Interactive TUI color picker (curses). Navigate with arrow keys, select with space, save with enter. Sets per-device default colors stored in `~/.config/frames/config.json`.

```bash
frames colors
```

### `list-colors`

Show available colors for a specific device. Supports partial name matching.

```bash
frames list-colors "17 Pro"
frames list-colors "MacBook"
frames list-colors "Watch Ultra"
```

### `info`

Detect the device for a screenshot without framing it. Shows device name, coordinates, available colors, mask/resize info.

```bash
frames info screenshot.png
frames --json info screenshot.png
```

### `setup`

Configure the path to the NewFrames assets folder. Validates that `NewFrames.json` exists and reports asset counts.

```bash
frames setup /path/to/NewFrames
```

## Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--color` | `-c` | Frame color: name (e.g. `"Cosmic Orange"`), 1-based index, or `random` |
| `--merge` | `-m` | Merge all framed images into a single horizontal strip |
| `--spacing` | `-s` | Pixel spacing between merged frames (default: 60) |
| `--output` | `-o` | Output directory (default: same directory as source) |
| `--copy` | | Copy result to macOS clipboard (single image only) |
| `--device` | `-d` | Force a specific device frame instead of auto-detecting |
| `--json` | | Machine-readable JSON output |
| `--verbose` | `-v` | Verbose output (shows resize, mask, variant info) |
| `--assets` | | Override assets directory for this invocation |
| `--no-color` | | Disable ANSI color output (also respects `NO_COLOR` env) |
| `--version` | | Print version and exit |

## Default Behavior

- **Output naming:** `originalname_framed.png` in the same directory as the source file. Merged output is `merged_framed.png`.
- **Device detection:** Automatic from screenshot pixel width. When multiple devices share a width, height is used to disambiguate.
- **Color resolution:** CLI `--color` flag > user defaults (set via `colors` command) > first color in the device's list.
- **Variant resolution:** When multiple device generations share a resolution (e.g. iPhone 16 Pro and 17 Pro), the newest device frame is used by default. Override with `--device`.

## Configuration

The `setup` command and `colors` command write to `~/.config/frames/config.json`:

```json
{
  "assets_path": "/path/to/NewFrames",
  "default_colors": {
    "iPhone 17 Pro": "Deep Blue",
    "MacBook Pro M5 14": "Space Black"
  }
}
```

You can also set the assets path via the `FRAMES_ASSETS` environment variable, which takes precedence over the config file.

**Priority order for assets:** `--assets` flag > `FRAMES_ASSETS` env var > config file > default iCloud Shortcuts path.

**Priority order for colors:** `--color` flag > config default > first color in device list.

## For AI Agents

Use `--json` for machine-readable output in pipelines:

```bash
# Frame and get output path
frames --json screenshot.png
# → {"source": "screenshot.png", "device": "iPhone 17 Pro Portrait", "color": "Cosmic Orange", ...}

# Get device info
frames --json info screenshot.png

# Frame and merge, get merged path
frames --json -m *.png
# → {"merged": "/path/to/merged_framed.png", "count": 3, "frames": [...]}
```

**Batch processing pattern:**

```bash
# Frame everything into a separate directory
frames -o ~/framed/ ~/screenshots/*.png

# Frame and merge all into one image
frames -m -o ~/framed/ ~/screenshots/*.png

# Random colors for visual variety
frames -c random -o ~/framed/ ~/screenshots/*.png
```

## Supported Devices

| Category | Devices | Colors |
|----------|---------|--------|
| iPhone 17 | 17, 17 Pro, 17 Pro Max (portrait + landscape) | 3-5 per model |
| iPhone Air | Air (portrait + landscape) | 4 |
| iPhone 16 | 16, 16 Plus, 16 Pro, 16 Pro Max (portrait + landscape) | 4-5 per model |
| iPhone 12-13 | 12/13 family | varies |
| iPhone 8/SE | iPhone 8, SE | varies |
| iPad | Pro (2018-2024), Air, mini | varies |
| MacBook | Neo, Pro M5 14"/16", Pro 2021, Air M5 13"/15" | 2-4 per model |
| iMac | iMac 2021 | 7 |
| Apple Watch | Series 7-10, Ultra, Ultra 3 | varies (including band combos) |

All devices support portrait and landscape orientations where applicable. Watch Ultra 3 has 13 case + band combinations.

## Credits

by Federico Viticci, [MacStories.net](https://www.macstories.net)
