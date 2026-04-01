<pre>
<span style="color:#E8722A"> █████  ██████  ██████  ██      ███████
██   ██ ██   ██ ██   ██ ██      ██
███████ ██████  ██████  ██      █████
██   ██ ██      ██      ██      ██
██   ██ ██      ██      ███████ ███████

███████ ██████   █████  ███    ███ ███████ ███████
██      ██   ██ ██   ██ ████  ████ ██      ██
█████   ██████  ███████ ██ ████ ██ █████   ███████
██      ██   ██ ██   ██ ██  ██  ██ ██           ██
██      ██   ██ ██   ██ ██      ██ ███████ ███████</span>
</pre>

Frame device screenshots with Apple product bezels from the command line. Auto-detects devices, supports colors, merging, and batch processing. By Federico Viticci.

---

## Installation

### Requirements
- Python 3.8+
- Pillow (Python imaging library)

### Option A: Clone the repo (recommended)

```bash
git clone https://github.com/viticci/frames-cli.git
cd frames-cli
pip3 install Pillow
```

Then symlink the script into a directory that's already in your PATH:

```bash
# Check which bin directory is in your PATH (use the first one that exists)
# Common locations: ~/.local/bin, ~/bin, /usr/local/bin

# Create the directory if needed, then symlink
mkdir -p ~/.local/bin
ln -s "$(pwd)/frames" ~/.local/bin/frames
```

If `~/.local/bin` isn't in your PATH yet, add it to `~/.zshrc` (or `~/.bashrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then restart your terminal or run `source ~/.zshrc`.

Verify it works:

```bash
frames --version
```

### Option B: Direct download

```bash
pip3 install Pillow
mkdir -p ~/.local/bin
curl -o ~/.local/bin/frames https://raw.githubusercontent.com/viticci/frames-cli/main/frames
chmod +x ~/.local/bin/frames
```

If `~/.local/bin` isn't in your PATH yet, add it to `~/.zshrc` (or `~/.bashrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then restart your terminal or run `source ~/.zshrc`.

### Setup

Run setup to point the CLI at your Apple Frames asset pack:

```
frames setup /path/to/Frames
```

This writes the path to `~/.config/frames/config.json`. You only need to run this once. The asset folder should contain `NewFrames.json` and the frame PNG files.

You can also set the `FRAMES_ASSETS` environment variable instead of using the config file.

---

## Quick Start

```bash
# Frame a screenshot — auto-detects device, saves as name_framed.png
frames screenshot.png

# Frame all PNGs in a directory
frames *.png

# Frame with a specific color
frames -c "Cosmic Orange" screenshot.png

# Frame with random colors
frames -c random *.png

# Frame and merge side by side
frames -m screenshot1.png screenshot2.png

# Merge in batches of 3 (15 files → 5 merged images)
frames -b 3 *.png

# Copy framed result to clipboard (macOS)
frames --copy screenshot.png

# Save to /framed/ subfolder
frames -f screenshot.png

# Save to custom subfolder
frames --subfolder mockups *.png

# Show device info without framing
frames info screenshot.png

# List all supported devices
frames list
```

---

## Commands

### Default framing

Frame one or more screenshots. The `frame` keyword is optional — passing files directly uses it automatically.

```bash
frames screenshot.png
frames frame screenshot.png   # same thing

# With flags
frames -c "Desert Titanium" -o ~/output/ *.png
frames -m -s 80 screenshot1.png screenshot2.png
```

**Output naming:** `originalname_framed.png` in the same directory as the source. Merged output is `merged_framed.png`.

**Device detection:** Automatic from screenshot pixel width. When multiple devices share a width, height disambiguates. The newest device frame is used when multiple generations share a resolution — override with `--device`.

**Color resolution:** `--color` flag > user default (set via `colors` command) > first color in device's list.

---

### `--color` / `-c`

Specify a frame color by name, 1-based index, or `random`.

```bash
frames -c "Cosmic Orange" screenshot.png
frames -c 2 screenshot.png
frames -c random *.png
```

Partial color name matching is supported. Use `list-colors` to see what's available for a device.

---

### `--merge` / `-m` and `--spacing` / `-s`

Merge all framed images into a single horizontal strip. Default spacing between frames is 60px.

```bash
frames -m screenshot1.png screenshot2.png screenshot3.png
frames -m -s 120 screenshot1.png screenshot2.png
```

The merged output is saved as `merged_framed.png` in the output directory.

---

### `--batch` / `-b`

Merge screenshots in sequential batches of N. Produces multiple merged images instead of one.

```bash
# 15 screenshots → 5 merged images of 3
frames -b 3 *.png

# Batch merge with custom spacing and output directory
frames -b 4 -s 80 -o /output/ *.png

# Batch merge with random colors
frames -b 3 -c random *.png
```

Batch size must be at least 2. If the total isn't evenly divisible, the last batch contains the remainder. Output files are named `merged_1_framed.png`, `merged_2_framed.png`, etc.

`--batch` implies `--merge` — no need to pass both. JSON output includes a `batches` array with per-batch counts and paths.

---

### `--subfolder` / `-f`

Save framed images to a subfolder relative to the source file's directory, instead of next to the originals. Two modes:

- `-f` (shorthand) saves to a `/framed/` subfolder
- `--subfolder NAME` saves to a custom-named subfolder

```bash
frames -f screenshot.png
# saves to ./framed/screenshot_framed.png

frames -f *.png
# saves all to ./framed/

frames --subfolder mockups *.png
# saves all to ./mockups/
```

To make subfolder mode the default, run `frames setup --subfolder`. To revert, run `frames setup --no-subfolder`.

---

### `--output` / `-o`

Save framed images to a specific output directory.

```bash
frames -o ~/Desktop/framed/ screenshot.png
frames -o /tmp/output/ *.png
```

---

### `--copy`

Copy the framed image directly to the macOS clipboard. Works with a single image only. The success/failure message prints to stderr, so it won't corrupt `--json` output.

```bash
frames --copy screenshot.png
frames --json --copy screenshot.png   # valid JSON on stdout
```

---

### `--device` / `-d`

Force a specific device frame instead of auto-detecting from the screenshot dimensions. Skips automatic variant resolution, so the exact device you specify is used. Useful when multiple devices share a resolution.

```bash
frames -d "iPhone 17 Pro Portrait" screenshot.png
frames -d "MacBook Pro M5 14" screenshot.png
```

Use `frames list` to see exact device names.

---

### `--json`

Output machine-readable JSON instead of human-readable text. Designed for AI agent pipelines and scripting.

```bash
frames --json screenshot.png
# → {"source": "screenshot.png", "device": "iPhone 17 Pro Portrait", "color": "Cosmic Orange", "output": "/path/to/screenshot_framed.png", ...}

frames --json -m screenshot1.png screenshot2.png
# → {"merged": "/path/to/merged_framed.png", "count": 2, "frames": [...]}

frames --json info screenshot.png
# → {"file": "screenshot.png", "device": "iPhone 17 Pro Portrait", "width": 1290, "height": 2796, ...}
```

---

### `list`

List all supported devices grouped by category. Shows pixel dimensions and available color counts.

```bash
frames list
```

---

### `colors`

Interactive TUI color picker (curses). Navigate with arrow keys, select with space, confirm with enter. Sets per-device default colors stored in `~/.config/frames/config.json`.

```bash
frames colors
```

---

### `list-colors`

Show all available colors for a specific device. Supports partial name matching.

```bash
frames list-colors "17 Pro"
frames list-colors "MacBook"
frames list-colors "Watch Ultra"
```

---

### `info`

Detect the device for a screenshot without framing it. Shows device name, pixel dimensions, available colors, mask and resize info.

```bash
frames info screenshot.png
frames --json info screenshot.png
```

---

### `setup`

Configure the path to the Frames assets folder. Validates that `NewFrames.json` exists inside it and reports asset counts. Also controls the subfolder default behavior.

```bash
frames setup /path/to/Frames
frames setup --subfolder /path/to/Frames     # enable subfolder mode by default
frames setup --no-subfolder /path/to/Frames  # disable subfolder mode (default)
```

---

## Configuration

The `setup` and `colors` commands write to `~/.config/frames/config.json`:

```json
{
  "assets_path": "/path/to/Frames",
  "use_subfolder": false,
  "default_colors": {
    "iPhone 17 Pro": "Deep Blue",
    "MacBook Pro M5 14": "Space Black"
  }
}
```

**Assets priority order:** `--assets` flag > `FRAMES_ASSETS` env var > config file > default iCloud Shortcuts path.

**Color priority order:** `--color` flag > config default (set via `colors` command) > first color in device list.

The `FRAMES_ASSETS` environment variable takes precedence over the config file and is useful for CI or non-standard setups:

```bash
FRAMES_ASSETS=/path/to/assets frames screenshot.png
```

---

## For AI Agents

The `--json` flag makes `frames` pipeline-friendly. All output goes to stdout; errors go to stderr.

```bash
# Frame a screenshot, capture the output path
OUTPUT=$(frames --json screenshot.png | python3 -c "import sys,json; print(json.load(sys.stdin)['output'])")

# Get device info as JSON
frames --json info screenshot.png

# Frame and merge, get merged path
frames --json -m *.png
```

**Batch processing patterns:**

```bash
# Frame everything into a separate directory
frames -o ~/framed/ ~/screenshots/*.png

# Frame and merge all into one image
frames -m -o ~/framed/ ~/screenshots/*.png

# Random colors for visual variety
frames -c random -o ~/framed/ ~/screenshots/*.png

# Subfolder mode — outputs land in ./framed/ next to sources
frames -f ~/screenshots/*.png
```

**Claude Code skill:** A skill file is included in `skill/SKILL.md`. Install it to `~/.claude/skills/frames-cli/SKILL.md` to give Claude Code native awareness of the CLI, its flags, and batch patterns.

---

## Supported Devices

| Category | Devices | Notes |
|----------|---------|-------|
| iPhone 17 | 17, 17 Pro, 17 Pro Max | Portrait + landscape |
| iPhone Air | Air | Portrait + landscape |
| iPhone 16 | 16, 16 Plus, 16 Pro, 16 Pro Max | Portrait + landscape |
| iPhone 12-13 | 12/13 mini, 12/13, 12/13 Pro, 12/13 Pro Max | Portrait + landscape |
| iPhone 8 / SE | iPhone 8, SE | Portrait |
| iPad | Pro 11" / 13" (2018-2024), Air, mini | Portrait + landscape |
| MacBook | Neo, Air M5 13"/15", Pro M5 14"/16", Pro 2021, Air 2020-2022, Pro 13 | Front-facing |
| iMac | iMac 2021 | 7 colors |
| Apple Watch | Ultra 3, Ultra 2024, Series 11, Series 10, Series 7 | Including band combinations |

Watch Ultra 3 supports 13 case + band combinations. Watch Series 11 supports 22 case + band combinations per size. All devices that have landscape variants support both orientations.

---

## Credits

by Federico Viticci, [MacStories.net](https://www.macstories.net)
