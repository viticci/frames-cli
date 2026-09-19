![](https://cdn.macstories.net/friday-10-apr-2026-14-28-25-1775824188552.png)

Frame device screenshots and screen recordings with Apple product bezels from the command line. Auto-detects devices, supports colors, merging, and batch processing. Based on the Apple Frames shortcut by me for MacStories.net, not affiliated with Apple.

[Read the changelog](CHANGELOG.md) for release details.

---

## Installation

### Requirements
- Python 3.8+
- Pillow (Python imaging library)
- ffmpeg 5.1+ and ffprobe 5.1+ for video framing (`frames setup` checks this and can install ffmpeg with Homebrew on macOS)

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

The CLI offers to download Apple Frames 4 assets when a command needs them and you run it interactively. Setup also checks video requirements and, on macOS, can install ffmpeg for you with Homebrew if it is missing. You can also set up manually:

```bash
# Guided download (interactive — downloads ~40 MB from cdn.macstories.net)
frames setup

# Or point to an existing assets folder
frames setup /path/to/Frames
```

The guided setup downloads the asset pack, extracts it, and saves the path to `~/.config/frames/config.json`. If assets get corrupted or you need a fresh copy, run `frames setup` again to re-download.

You can also set the `FRAMES_ASSETS` environment variable instead of using the config file.

### iPhone 18 Pro support

iPhone 18 Pro uses the same native screenshot dimensions as iPhone 17 Pro: **1206 × 2622** in portrait and **2622 × 1206** in landscape. With an asset pack containing the new variants, automatic detection selects iPhone 18 Pro; pass `--device "iPhone 17 Pro Portrait"` or `--device "iPhone 17 Pro Landscape"` to keep using the older frame explicitly.

Apple's bezel artwork is not stored in this repository. Put the eight portrait/landscape PNGs for Black, Silver, Glacier, and Burgundy in a source folder using names such as `iPhone 18 Pro Portrait Black.png`, then build a complete pack without modifying the base pack:

```bash
python3 scripts/build_iphone_18_pro_assets.py \
  --source /path/to/iphone-18-pro-pngs \
  --base-assets /path/to/Frames \
  --output /path/to/Frames-iPhone-18-Pro
frames setup /path/to/Frames-iPhone-18-Pro
```

The builder validates the official canvas and display geometry, generates enclosed-screen masks, records checksums in `iPhone-18-Pro.json`, and refuses to overwrite an existing output folder.

### Experimental iPhone Duo support

Frames **1.4.1 or later** supports Duo with a separate, opt-in asset pack. It includes both displays in portrait and landscape, Night Sky and Star White finishes, and a view showing the phone's back beside its outer screen. Updating the CLI alone does not install the pack; normal `frames setup` still downloads AppleFrames401.zip.

Download [Frames-Duo-Experimental.zip](https://cdn.macstories.net/images/uploads/2026/09/09/frames-duo-experimental-1788997654596-a33ef863e7.zip) (95.2 MB) and unzip it. The enclosed `Frames-Duo-Experimental` folder contains the existing frames too. Select that folder for an individual command:

```bash
frames --assets /path/to/Frames-Duo-Experimental -c "Star White" duo.png
frames --assets /path/to/Frames-Duo-Experimental --json info duo.png
frames --assets /path/to/Frames-Duo-Experimental -d "iPhone Duo Outer Portrait" outer-portrait.png
frames --assets /path/to/Frames-Duo-Experimental -d "iPhone Duo Outer Open" outer-portrait.png
```

The two outer portrait commands use the same **1398 × 2034** screenshot. `Outer Portrait` shows only the screen; `Outer Open` adds the back of the phone beside it. Without `--device`, the single-screen view is selected automatically. The option also works with `frames video`.

To save the pack as your default, run `frames setup /path/to/Frames-Duo-Experimental` once. Detection requires the exact native width **and** height: outer portrait **1398 × 2034**, outer landscape **2034 × 1398**, inner portrait **1878 × 2670**, or inner landscape **2670 × 1878**. These mappings are experimental until real Duo screenshots can be checked.

See the [complete Duo setup and usage guide](docs/iphone-duo-experimental.md) for copyable download commands, verification, both selection methods, colors, videos, restoring your previous pack, and asset provenance.

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

# Assign colors per input
frames --colors "Silver,Space Black,random" one.png two.png three.png

# Tip: frame a screen recording with the same auto-detected device bezel
frames video recording.mp4

# Tip: tune MP4 export size/quality; best is the default
frames video --preset compact recording.mp4
frames video --preset balanced recording.mp4
frames video --preset best recording.mp4

# Tip: export compressed video with transparency on macOS
frames video --codec hevc-alpha recording.mp4

# Tip: inspect the video match before spending time rendering
frames --json video-info recording.mp4

# Tip: rotate landscape iPad screen recordings that are encoded as portrait
frames video --rotate counterclockwise ipad-landscape-recording.mp4

# Tip: merge framed videos and play them left to right
frames video -m --playback-offset 1.mp4 2.mp4

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

**Color resolution:** `--colors` per-input value > `--color` flag > user default (set via `colors` command) > first color in device's list.

---

### `--color` / `-c` and `--colors`

Specify a frame color by exact name, 1-based index, `default`, or `random`.

```bash
frames -c "Cosmic Orange" screenshot.png
frames -c 2 screenshot.png
frames -c random *.png
frames --colors "Silver,Space Black,random" one.png two.png three.png
```

`--color random` randomizes independently per input. `--colors` maps comma-separated values to expanded inputs by order, and it cannot be combined with `--color`. Use `list-colors` to see what's available for a device.

---

### `video`

Frame screen recordings or videos with the same Apple Frames assets used for screenshots.

```bash
frames video recording.mp4
frames video -c Silver recording.mp4
frames video --colors "Silver,random" 1.mp4 2.mp4
frames video --strip-audio recording.mp4
frames video --preset compact recording.mp4
frames video --preset balanced recording.mp4
frames video --preset best recording.mp4
frames video --rotate counterclockwise ipad-landscape-recording.mp4
frames video -m --alpha 1.mp4 2.mp4
frames video -m --background transparent 1.mp4 2.mp4
```

Video support requires `ffmpeg` 5.1+ and `ffprobe` 5.1+. `frames setup` checks for both and can install ffmpeg with Homebrew on macOS. Supported input extensions are `.mp4`, `.mov`, and `.m4v`.

Single-video output is `originalname_framed.mp4` by default, or `.mov` for `--alpha`, `--codec prores`, `--codec hevc-alpha`, or `--background transparent`. Audio is preserved unless `--strip-audio` is passed.

When framing several videos individually, Frames rejects output paths that would overwrite another input or share a name with another output before rendering. Use a separate output directory, or distinct source filenames if outputs would share a name.

The canvas outside the device bezel is white by default, or transparent with `--alpha` or `--codec hevc-alpha`. Use `--background white`, `--background black`, or a hex color such as `--background "#f5f5f5"` to choose an opaque background. An explicit background applies to the entire canvas, including any padding.

Some iPad screen recordings are visually landscape but encoded as portrait video frames. In that case, inspect with `frames --json video-info recording.mp4`; if the match is portrait while the content is landscape, pass `--rotate counterclockwise` or `--rotate clockwise` so Frames rotates before device detection and framing.

Use `--alpha` or `--background transparent` to create transparent ProRes 4444 `.mov` output unless you explicitly select `--codec hevc-alpha`. This works for single videos and merged videos. `--alpha --codec hevc` still selects ProRes; `--codec hevc` alone remains opaque HEVC MP4. If you pass an explicit output file for ProRes or HEVC-alpha, it must use a `.mov` extension.

ProRes 4444 preserves transparency for editing and compositing, but its files can be much larger than the source MP4. Use `--codec hevc-alpha` for compressed transparent delivery to compatible Apple apps and devices. Support varies by app; use ProRes when your editing workflow requires it. Use an opaque MP4 export when you only need a different background color. Presets do not reduce ProRes file sizes.

HEVC-alpha requires macOS and an ffmpeg build with VideoToolbox HEVC alpha support. Frames checks encoder support before rendering and reports an error if it is unavailable; it never silently switches to opaque HEVC or ProRes. Rotation, per-input colors, device masks, single exports, and both merge playback modes are supported. Audio follows the existing rules below.

HEVC stores transparency in an auxiliary layer. `ffprobe` may report `yuv420p` without exposing that alpha layer. Verify transparency with a compatible native Apple decoder; the optional regression test uses AVFoundation.

Interactive video renders show a live progress bar. The live progress bar is disabled for JSON and non-interactive runs. Completed video exports report output size and source-vs-output savings in both human output and JSON.

Video presets tune export size and quality. `best` is the default. For MP4, `balanced` and `compact` lower H.264/HEVC bitrate for hardware encoding and use higher CRF values for software encoding. `--quality N` remains an expert CRF override for software MP4 encoders only; lower is higher quality. For HEVC-alpha, `compact`, `balanced`, and `best` target 4, 7, and 10 Mbps respectively; these are bitrate targets, not file-size guarantees. HEVC-alpha rejects `--quality`; use `--preset` instead.

For MP4/H.264, MP4/HEVC, and HEVC-alpha MOV output, Frames pads odd dimensions to even encoded dimensions so the encoder preserves the full frame and, where supported, transparency. Single-video JSON reports the encoded `output_dimensions` and whether it was `padded`. In HEVC-alpha merges, per-input `output_dimensions` describe the raw device frame before physical scaling, with `padded: false`; only the final canvas is padded as needed, and the top-level `dimensions` report its encoded size.

Common video recipes:

| Goal | Command |
| --- | --- |
| Check the match before rendering | `frames --json video-info recording.mp4` |
| Frame one video | `frames video recording.mp4` |
| Use compact MP4 export | `frames video --preset compact recording.mp4` |
| Use balanced MP4 export | `frames video --preset balanced recording.mp4` |
| Use best MP4 export | `frames video --preset best recording.mp4` |
| Rotate before matching/framing | `frames video --rotate counterclockwise recording.mp4` |
| Frame silently | `frames video --strip-audio recording.mp4` |
| Merge videos simultaneously | `frames video -m 1.mp4 2.mp4` |
| Play merged videos left to right | `frames video -m --playback-offset 1.mp4 2.mp4` |
| Assign per-input colors | `frames video --colors "Silver,random" 1.mp4 2.mp4` |
| Compressed transparent HEVC MOV (macOS) | `frames video --codec hevc-alpha recording.mp4` |
| Transparent HEVC merge (macOS) | `frames video -m --codec hevc-alpha 1.mp4 2.mp4` |
| Transparent ProRes MOV | `frames video --alpha recording.mp4` |
| Transparent merged ProRes MOV | `frames video -m --alpha 1.mp4 2.mp4` |
| Transparent merged canvas | `frames video -m --background transparent 1.mp4 2.mp4` |

```bash
# Transparent ProRes MOV
frames video --alpha recording.mp4

# Transparent merged ProRes MOV
frames video -m --alpha 1.mp4 2.mp4
frames video -m --background transparent 1.mp4 2.mp4

# Compressed transparent HEVC MOV (macOS)
frames video --codec hevc-alpha --preset compact recording.mp4

# Transparent HEVC merge with sequential playback (macOS)
frames video -m --playback-offset --codec hevc-alpha 1.mp4 2.mp4

# HEVC output
frames video --codec hevc recording.mp4

# Compact HEVC output
frames video --codec hevc --preset compact recording.mp4

# Custom background
frames video --background "#f5f5f5" recording.mp4
```

### Video merging

Merge multiple framed videos into a horizontal canvas. By default, videos play simultaneously and the output duration is the longest input.

```bash
frames video -m 1.mp4 2.mp4
frames video -m --no-scale 1.mp4 2.mp4
frames video -m --alpha 1.mp4 2.mp4
frames video -m --background transparent 1.mp4 2.mp4
```

When merging different devices, videos are proportionally scaled using the same physical-height model as image merges and bottom-aligned.

Use `--playback-offset` to play videos one at a time from left to right. Inactive videos hold on their first frame before playback and their final frame after playback.

```bash
frames video -m --playback-offset 1.mp4 2.mp4
```

With `--playback-offset`, audio is concatenated sequentially and videos without audio contribute silence, unless `--strip-audio` is passed. Simultaneous video merges omit mixed audio in this version.

Transparent merges use ProRes 4444 MOV with `yuva444p10le` pixels by default, or compressed HEVC-alpha MOV with `--codec hevc-alpha` on macOS. Both support simultaneous and sequential playback. Choose a format supported by the app where you will use the merged devices over transparency.

---

### `video-info`

Probe videos and report matching Apple frame metadata without rendering.

```bash
frames video-info recording.mp4
frames --json video-info recording.mp4
frames --json video-info --colors "Silver,random" 1.mp4 2.mp4
```

`video-info` uses the same device, variant, color, ffmpeg, and ffprobe checks as `frames video`. It reports dimensions, duration, fps, codec, audio state, matched device, selected color, frame size, mask state, and resize metadata.

`video-info` inspects the source and frame match; it does not select an output codec. Its output geometry assumes the default MP4 export. For rendered-video presets and transparency options, see `video` above.

Rendered-video JSON includes `output_codec` (`h264`, `hevc`, `prores`, or `hevc-alpha`) for single exports, merged output, and each merged input. The existing per-input `codec` field still describes the source. `alpha` indicates an alpha-capable output format; `background` reports `transparent` or the explicit opaque background.

`frames --json video ...` returns the selected `preset` plus `output_size_bytes`, `output_size`, `source_size_bytes`, `source_size`, `savings_bytes`, `savings`, and `savings_percent` after export. Merged JSON output includes the same top-level size and savings fields.

---

### `--merge` / `-m` and `--spacing` / `-s`

Merge all framed images into a single horizontal strip. Default spacing between frames is 60px.

When merging **different devices**, frames are automatically scaled to reflect real-world physical proportions and bottom-aligned. An iPhone next to an iPad will be proportionally shorter, just like in real life. Same-device merges are unaffected.

```bash
frames -m screenshot1.png screenshot2.png screenshot3.png
frames -m -s 120 screenshot1.png screenshot2.png
```

The merged output is saved as `merged_framed.png` in the output directory.

---

### `--no-scale`

Disable proportional scaling when merging. All frames render at native pixel size and are center-aligned (pre-v1.2 behavior).

```bash
frames -m --no-scale iphone.png ipad.png
```

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

To make subfolder mode the default, run `frames setup --subfolder`. To revert, run `frames setup --no-subfolder`. These commands only update the saved setting; they do not download assets or check video tools.

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

Output machine-readable JSON for `frame`, `video`, `info`, `video-info`, and `doctor`. The `list`, `list-colors`, `colors`, and `setup` commands keep their human-readable or interactive output even with `--json`.

The global options `--json`, `--assets`, `--verbose` (`-v`), and `--no-color` work before or after a command name. For example, `frames --json video-info recording.mp4` and `frames video-info --json recording.mp4` are equivalent.

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

Download assets or configure the assets folder path. Without arguments, starts an interactive download from `cdn.macstories.net` (~40 MB). With a path, points the CLI at an existing assets folder. With only `--subfolder` or `--no-subfolder`, updates that setting without starting setup.

```bash
# Download assets interactively (first-time setup or re-download)
frames setup

# Point to an existing assets folder
frames setup /path/to/Frames

# With subfolder mode
frames setup --subfolder /path/to/Frames     # enable subfolder mode by default
frames setup --no-subfolder /path/to/Frames  # disable subfolder mode (default)
```

If assets are missing or outdated, commands that need them offer to download them in an interactive terminal. JSON and non-interactive runs fail instead; JSON output includes `setup_required: true`.

---

### `doctor`

Check the configuration file, assets, saved colors, and video tools without changing them. This command also works when the configuration file is malformed.

```bash
frames doctor
frames doctor --json
```

The report lists issues and suggested next steps. In scripts, inspect the JSON `ok` field: `doctor` can exit successfully while reporting `ok: false`.

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

**Color priority order:** `--colors` per-input value > `--color` flag > config default (set via `colors` command) > first color in device list.

The `FRAMES_ASSETS` environment variable takes precedence over the config file and is useful for CI or non-standard setups:

```bash
FRAMES_ASSETS=/path/to/assets frames screenshot.png
```

---

## For AI Agents

For commands that support `--json`, successful results go to stdout. Verbose diagnostics and clipboard status go to stderr. Errors can appear on stderr or as JSON with an `error` field on stdout, so check both the exit status and error fields.

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
| iPhone Duo (experimental pack) | Inner and outer displays | Portrait + landscape; optional rear view |
| iPhone 18 | 18 Pro | Portrait + landscape; 4 finishes |
| iPhone 17 | 17, 17 Pro, 17 Pro Max | Portrait + landscape |
| iPhone Air | Air | Portrait + landscape |
| iPhone 16 | 16, 16 Plus, 16 Pro, 16 Pro Max | Portrait + landscape |
| iPhone 12-13 | 12/13 mini, 12/13, 12/13 Pro, 12/13 Pro Max | Portrait + landscape |
| iPhone 8 / SE | iPhone 8, SE | Portrait |
| iPad | Pro 11" / 13" (2018-2024), Air, mini | Portrait + landscape |
| MacBook | Neo, Air M5 13"/15", Pro M5 14"/16", Pro 2021, Air 2020-2022, Pro 13 | Front-facing |
| iMac | iMac M4 | 7 colors (Silver default) |
| Studio Display | Studio Display, Studio Display XDR | 2 colors each (Light default); XDR is a variant |
| Apple Watch | Ultra 3, Ultra 2024, Series 11, Series 10, Series 7 | Including band combinations |

Watch Ultra 3 supports 13 case + band combinations. Watch Series 11 supports 22 case + band combinations per size. All devices that have landscape variants support both orientations.

---

## Development

From a repository checkout with Pillow installed, run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

The video rendering tests also need `ffmpeg` and `ffprobe`; they are skipped when either tool is missing. Tests create temporary inputs and assets. The optional native HEVC-alpha test also requires macOS, a working `swiftc`, and ffmpeg HEVC alpha support. It skips when prerequisites are unavailable; otherwise, failures fail the suite. It decodes exports through AVFoundation to check transparency, masks, geometry, and opaque backgrounds.

The iPhone 18 Pro tests cover shared-resolution default selection, explicit iPhone 17 Pro selection, finishes, catalog listing, and enclosed screen masks. The Duo tests cover device listing, exact resolution matching, both finishes, the manual rear view, explicit image/video resize dimensions, enclosed screen masks, and metadata removal. They use small synthetic assets; full artwork verification is described in the [Duo guide](docs/iphone-duo-experimental.md).

---

## Credits

by Federico Viticci, [MacStories.net](https://www.macstories.net)
