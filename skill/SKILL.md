---
name: frames-cli
description: Frame screenshots and screen recordings with the `frames` CLI. Use this skill when the user asks to add Apple device bezels, frame screenshots or videos, create device mockups, inspect screenshot/device matches, or batch-process screenshot/video folders with the command line.
---

# Apple Frames CLI

`frames` 1.7.2 is a single-file Python CLI that applies Apple device bezels to screenshots and videos, auto-detects devices from input dimensions, applies masks when needed, and can merge multiple framed results. Video support uses external `ffmpeg` 5.1+ and `ffprobe` 5.1+ with no extra Python media stack.

## What Agents Should Know

- `frames` is the default command. `frames screenshot.png` and `frames frame screenshot.png` are equivalent.
- Use `--json` for automation with `frame`, `info`, `video`, `video-info`, and `doctor`. Global flags `--json`, `--assets`, `--verbose`, and `--no-color` work before or after subcommands. `list`, `list-colors`, `colors`, and `setup` retain human-readable output.
- Device support comes from the installed asset bundle, not hardcoded names in this skill. Use `frames list` and `frames list-colors` as the source of truth when exact names matter.
- The standard asset pack covers iPhone 18 Pro, iPhone 18 Pro Max, and iPhone Duo. After updating the CLI, `frames setup` downloads it; if `frames doctor` says the pack predates these devices, run setup again. Duo capture sizes are verified in the Xcode 27.1 simulator, not on hardware; do not claim real-device verification.
- On macOS, the default asset location is the Apple Frames shortcut folder in iCloud Drive. That avoids downloading a second copy when the user already has the shortcut assets installed.
- Use `frames video ...` for `.mp4`, `.mov`, and `.m4v`; the default `frames ...` path is for images.
- Use `frames video-info ...` to probe videos and resolve the matching frame metadata without rendering.
- Video framing requires external `ffmpeg` 5.1+ and `ffprobe` 5.1+. `frames setup` checks this and can offer a Homebrew install on macOS; `frames doctor` reports video tool readiness.
- `frames video` preserves single-video audio by default. Pass `--strip-audio` when the user asks for silent output, privacy-safe delivery, or validation clips where audio does not matter.
- `frames video --preset compact|balanced|best` controls H.264/HEVC export size/quality, including HEVC-alpha; `best` is the default. The default video canvas is opaque white except with `--alpha` or `--codec hevc-alpha`. For small opaque exports, use `--preset compact` with `--background black` or `--background "#RRGGBB"`. Video exports report output file size and source-vs-output savings in human and JSON output.
- Use `frames video --codec hevc-alpha ...` for transparent HEVC-with-alpha `.mov` delivery on macOS with a compatible ffmpeg build. Use `--alpha` or `--background transparent` for ProRes 4444 `.mov` editing/compositing output unless `--codec hevc-alpha` is explicitly selected. Normal H.264/HEVC MP4 output is opaque; legacy `--alpha --codec hevc` still selects ProRes.
- Explicit ProRes and HEVC-alpha output file paths must use a `.mov` extension. Use an output directory when you want the CLI to pick the `.mov` filename.
- Use `frames video --rotate clockwise|counterclockwise|180 ...` when a screen recording's visual orientation differs from its encoded dimensions. This is common with some landscape iPad recordings that probe as portrait.
- H.264/HEVC MP4 and HEVC-alpha MOV exports pad odd dimensions to even encoded dimensions. Check `output_dimensions` and `padded` for individual outputs, or top-level `dimensions` for merges, in JSON output.

## Quick Reference

```bash
# Frame one screenshot
frames screenshot.png

# Frame every top-level image in a folder
frames ~/Screenshots/

# Pick a specific color or randomize colors
frames -c "Cosmic Orange" screenshot.png
frames -c random *.png
frames --colors "Silver,Space Black,random" one.png two.png three.png

# Frame videos
frames video-info recording.mp4
frames --json video-info recording.mp4
frames video recording.mp4
frames video --preset compact recording.mp4
frames video --background black --preset compact recording.mp4
frames video --background "#f5f5f5" --preset compact recording.mp4
frames video --preset balanced recording.mp4
frames video --preset best recording.mp4
frames video --rotate counterclockwise ipad-landscape-recording.mp4
frames video --alpha recording.mp4
frames video --codec hevc-alpha recording.mp4
frames video --codec hevc-alpha --preset compact -o delivery.mov recording.mp4
frames video -m --playback-offset --codec hevc-alpha 1.mp4 2.mp4
frames video -m --alpha 1.mp4 2.mp4
frames video -m --background transparent 1.mp4 2.mp4
frames --json video --strip-audio recording.mp4
frames video --strip-audio recording.mp4
frames video --background "#f5f5f5" --codec hevc recording.mp4
frames video -m --playback-offset 1.mp4 2.mp4
frames video -m --colors "Silver,random" 1.mp4 2.mp4

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
- Apply frame colors by exact name, 1-based numeric index, `default`, or `random`.
- Use `--colors` for per-input colors on images and videos; it maps comma-separated values to expanded inputs by order.
- Apply masks when the asset entry requires clipping.
- Merge multiple framed outputs with physical-size normalization by default.
- Frame `.mp4`, `.mov`, and `.m4v` files through `frames video`; single-video audio is preserved unless `--strip-audio` is passed.
- Use `--preset compact`, `--preset balanced`, or `--preset best` to tune H.264/HEVC export size/quality, including HEVC-alpha. `best` is the default.
- Use `--rotate clockwise|counterclockwise|180` to rotate videos before auto-detection and framing.
- MP4/H.264, MP4/HEVC, and HEVC-alpha MOV outputs use even encoded dimensions. Single-output JSON reports `output_dimensions` and `padded`; merged JSON reports the final size in top-level `dimensions`.
- Report output file size and savings after video export in both human output and `--json` agent output.
- Use `--codec hevc-alpha` for macOS HEVC-alpha MOV delivery, or `--alpha` / `--background transparent` for ProRes 4444 MOV. HEVC-alpha supports single, simultaneous merge, and sequential merge output with the same rotation, color, mask, scaling, and audio rules.
- Show a live terminal progress bar during video renders in interactive mode; JSON and non-TTY runs stay pipeline-friendly.
- Inspect video/device matches without rendering through `frames video-info`.
- Merge videos simultaneously with `frames video -m`, or sequentially left-to-right with `frames video -m --playback-offset`.
- Use `--no-scale` to disable proportional scaling and keep native framed sizes when merging.
- Use `--batch N` to merge sequential groups. `--batch` implies merge and `N` must be at least `2`.
- Save next to originals, into `--output`, or into a validated single-name subfolder via `-f` or `--subfolder`.
- Copy a single output to the macOS clipboard with `--copy`.
- Inspect screenshots and folders with `info`.
- Diagnose assets and config with `doctor`.
- Save per-device default colors with `colors`.

## Command Notes

- Global flags:
  - `--json` for machine-readable output from `frame`, `info`, `video`, `video-info`, and `doctor`
  - `--no-color` to disable ANSI color
  - `--assets PATH` to override asset discovery
  - `-v` / `--verbose` for variant, resize, and mask details
- Use `frames video --help` and `frames video-info --help` for the human-facing video examples and option summaries.
- `frames colors` is interactive in a real terminal. If stdin is not a TTY, or `curses` is unavailable, it falls back to a plain printed color list.
- `frames list-colors` does partial device-name matching. `frames list-colors "17 Pro"` is valid.
- Directory inputs are expanded one level deep only. The CLI scans top-level image files inside the directory; it is not recursive.
- Supported input image extensions are `.png`, `.jpg`, `.jpeg`, `.heic`, `.tiff`, and `.webp`.
- Supported input video extensions are `.mp4`, `.mov`, and `.m4v`.
- Images larger than `20,000px` on either side trigger a warning. Images larger than `50,000px` are rejected.
- `--subfolder` only accepts a single directory name, not a path like `../out` or `foo/bar`.

## Video Notes

- `frames video-info FILE` reports dimensions, duration, fps, codec, audio state, matched device, selected color, frame size, mask state, and resize metadata without creating an output video.
- `frames video-info --rotate counterclockwise FILE` reports the post-rotation dimensions and matched device before spending time rendering.
- `frames video FILE` writes `FILE_framed.mp4` by default, or `.mov` when `--alpha`, `--codec prores`, `--codec hevc-alpha`, or `--background transparent` is used.
- `--alpha` and `--codec hevc-alpha` default the background to transparent unless the user explicitly passes another `--background`. An explicit opaque background also applies to any even-dimension padding.
- Explicit ProRes and HEVC-alpha output files must end in `.mov`; otherwise `frames video` fails before rendering.
- For one video, `--output` may be an explicit output file path or a directory. For multiple individual videos, use an output directory. Conflicts that would overwrite another input or send distinct inputs to the same output are rejected before rendering; choose a separate output directory or distinct source filenames.
- `--merge` creates one horizontal video. Without `--playback-offset`, videos play simultaneously and duration is the longest input.
- `--playback-offset` requires `--merge`; videos play left to right, inactive future videos hold their first frame, and completed videos hold their final frame.
- Merged videos are proportionally scaled by device `physicalHeight`, measured against each device's visible body rather than its padded frame canvas, and bottom-aligned by default. Use `--no-scale` only when native framed pixel sizes matter more than physical proportion.
- Single-video output preserves audio unless `--strip-audio` is passed. Sequential `--playback-offset` merges concatenate audio and generate silence for inputs without audio. Simultaneous merges omit mixed audio in this version.
- `--background` accepts only `white`, `black`, `transparent`, or `#RRGGBB`. The default canvas is opaque white, including with `--codec prores`; `--alpha` or `--codec hevc-alpha` changes the default to transparent. `--background transparent` selects ProRes MOV unless `--codec hevc-alpha` is explicit.
- `--codec h264` is the default. Plain `--codec hevc` selects opaque HEVC MP4. `--codec prores` selects alpha-capable ProRes 4444 MOV; use `--alpha` or `--background transparent` for a transparent canvas. Explicit `--codec hevc-alpha` selects macOS VideoToolbox HEVC-with-alpha MOV, even when combined with `--alpha`. Without explicit `hevc-alpha`, `--alpha` takes precedence over `--codec hevc` and selects ProRes.
- Use HEVC-alpha for compact delivery to Apple-compatible software that supports HEVC-with-alpha. Use ProRes 4444 (`yuva444p12le`) for editing and compositing. Verify the intended receiving app; HEVC-alpha support is not universal.
- `--preset compact|balanced|best` controls H.264/HEVC hardware bitrate and software CRF. For HEVC-alpha, these presets set target bitrates of 4M, 7M, and 10M respectively; `best` is the default. Targets are not guaranteed file sizes. ProRes MOV files can be much larger; all presets keep the same ProRes settings.
- `--quality N` is an expert software H.264/HEVC CRF override; lower is higher quality. HEVC-alpha rejects `--quality`; use `--preset` instead.
- HEVC-alpha requires macOS and an ffmpeg build with `hevc_videotoolbox`, its `alpha_quality` option, and BGRA input support. The CLI checks these before rendering and reports unsupported configurations without silently falling back to an opaque codec. If unavailable, update ffmpeg or explicitly choose ProRes with `--alpha` and remove `--codec hevc-alpha`. `doctor` checks general video tool readiness; it does not certify HEVC-alpha support.
- `--rotate clockwise|counterclockwise|180` is applied before device matching, resizing, masks, and framing.
- `--color random` randomizes independently per input. `--colors "A,B,random"` maps values to expanded inputs by order and the count must match after directory expansion.
- `video-info` accepts `--device`, `--color`, `--colors`, and `--rotate`; it uses the same resolution rules as `frames video`.
- Taildrop or other delivery is separate from `frames`; render first, verify the output, then use the delivery workflow the user requested.

## JSON Output Behavior

- Successful `frame`, `info`, `video`, `video-info`, and `doctor` commands emit JSON on stdout when `--json` is set. Verbose details and warnings go to stderr, so `--json --verbose` remains parseable. `list`, `list-colors`, `colors`, and `setup` retain human-readable output.
- Check the exit status and stderr as well as stdout: config and missing-asset errors can return JSON error objects, while other failures report text on stderr. Do not assume every failure returns JSON.
- `frames --json screenshot.png` returns one framed-image object with fields such as `source`, `device`, `color`, `dimensions`, `frame_size`, `resized`, `masked`, `physicalHeight`, and `output`.
- `frames --json *.png` returns `{ "frames": [...] }` for multiple individual outputs.
- `frames --json -m ...` returns a merged result with `merged`, `count`, and `frames`.
- `frames --json -b N ...` returns `batches`, `batch_size`, `total`, and `frames` when there are multiple groups. A single group returns `merged`, `count`, and `frames`.
- When proportional merge scaling is applied, per-frame `scale_factor` values are included in the JSON output. Image batch factors describe each frame within its own batch.
- `frames --json info ...` returns either one object or a list of objects, including `device`, `primary_match`, `colors`, `color_count`, `has_mask`, `resize_width`, `variants`, and `is_variant`. `variants` lists every frame the pack can render for that input, the selected one included; it is empty when there is no other choice.
- `frames --json video-info ...` returns one video metadata object, or a list for multiple videos, including `dimensions`, `source_dimensions`, `rotation`, `duration`, `fps`, `codec`, `audio`, `device`, `primary_match`, `color`, `frame_size`, `output_dimensions`, `padded`, `resize_width`, and `mask_missing`.
- `frames --json doctor` returns asset path/source/version, PNG count, config presence, issues, notes, and suggested next steps.
- `frames --json video ...` returns one video object, or `{ "videos": [...] }` for multiple individual outputs, including `output_codec`, `rotation`, `source_dimensions`, `output_dimensions`, `padded`, `preset`, `output_size_bytes`, `output_size`, `source_size_bytes`, `source_size`, `savings_bytes`, `savings`, and `savings_percent`.
- `frames --json video -m ...` returns `merged`, `duration`, `dimensions`, `output_codec`, `playback_offset`, audio state, top-level output size/savings fields, and per-input `frames`. Top-level `dimensions` is the actual encoded output size, including any final even-dimension padding.
- `output_codec` identifies the effective render choice (`h264`, `hevc`, `prores`, or `hevc-alpha`) on individual outputs and merged top-level/per-input objects. Existing per-input `codec` remains the source codec. `video-info` inspects source metadata and does not emit `output_codec`.
- For HEVC-alpha merges, per-input `output_dimensions` describes raw framed tiles before physical scaling, and per-input `padded` is `false`; only the final merge is padded. For single HEVC-alpha outputs, `output_dimensions` and `padded` describe the encoded output normally.
- `alpha: true` marks an alpha-capable ProRes or HEVC-alpha output, including when an explicit opaque background is selected. Read `background` to determine the requested canvas; verify decoded pixels when actual transparency matters.

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

- `frames setup` downloads the current asset archive from `__PACK_URL__` (AppleFrames422.zip, __PACK_BYTES__ bytes, SHA-256 `__PACK_SHA256__`), pack version 4.2.2. It is the same pack the Apple Frames shortcut uses and covers iPhone 18 Pro, 18 Pro Max, iPhone Duo and its Book and Laptop poses, MacBook Pro with PROLED XDR Display, iPad mini (A20 Pro), and Apple Watch Ultra 4. It has __PACK_PNG_COUNT__ PNGs. Device frames are cropped to the device so canvases carry no empty border. If `frames doctor` notes that the pack predates one of these devices or poses, re-run `frames setup` to update it.
- `frames setup /path/to/Frames` points the CLI at an existing asset folder instead of downloading.
- `--assets` and `setup PATH` take a local folder, not a URL or ZIP file. The separate `Frames-Duo-Experimental` pack from 1.4.1 is superseded; switch users to the standard pack with `frames setup`.
- The asset folder must contain `NewFrames.json`, `version.txt`, and the frame/mask PNGs.
- Setup checks `ffmpeg`/`ffprobe` for video framing and can install ffmpeg through Homebrew on macOS when run interactively.
- `frames setup --subfolder` and `frames setup --no-subfolder` update the default save behavior in config.
- Invalid config produces an actionable error instead of silently discarding saved settings. `frames doctor` remains usable and reports config problems; fix the reported config issue before retrying.
- `frames doctor` is the first command to run when assets were moved, edited, corrupted, or when video dependencies need verification.

## Current Supported Device Families

iPhone Duo screenshots are detected by exact width and height:

| Input width × height | Frame |
| --- | --- |
| 1398 × 2034 | iPhone Duo Outer Portrait |
| 2034 × 1398 | iPhone Duo Outer Landscape |
| 2007 × 2853 | iPhone Duo Inner Portrait |
| 2853 × 2007 | iPhone Duo Inner Landscape |

All four have Night Sky (default) and Star White finishes. The inner sizes are the Xcode 27.1 simulator's captures and frame at 1:1; mockups at Apple's announced 1878 × 2670 or 2670 × 1878 are scaled to the same frames. Do not resize the input yourself or add a camera cutout; the outer camera is part of Apple's frame. `--device "iPhone Duo Outer Open"` frames a 1398 × 2034 input in Apple's rear view, with the display on the right; it is never selected automatically, and `frames list` shows it under manual frames. Simulator inner-display recordings (2006 × 2852, rotation-tagged) are not detected automatically; pass `--device` with the matching inner orientation. Outer landscape artwork has the camera at the top left, so screenshots taken in the opposite landscape orientation show the frame's camera over content.

```bash
frames --json info duo.png
frames -c "Star White" duo.png
frames -d "iPhone Duo Outer Open" outer-portrait.png
frames --merge iphone-18-pro.png duo-outer.png
```

Two partially open poses frame inner-display screenshots on a folded phone. They need `frames` 1.7.2 and asset pack 4.2.2, and they are never selected automatically:

| `--device` | Input width × height | Full frame name |
| --- | --- | --- |
| `iPhone Duo Book Pose` | 2853 × 2007 or 2670 × 1878 | iPhone Duo Inner Partially Open Landscape |
| `iPhone Duo Laptop Pose` | 2007 × 2853 or 1878 × 2670 | iPhone Duo Inner Partially Open Portrait |

Both have Night Sky (default) and Star White finishes, and use the saved default color of iPhone Duo Inner until they have their own. Any other input size fails with an error that names the accepted sizes. Framed images are __BOOK_CANVAS__ pixels (Book Pose) and __LAPTOP_CANVAS__ pixels (Laptop Pose); screenshots are never upscaled. The poses also frame recordings: `frames video -d "iPhone Duo Book Pose" recording.mov`. Video accepts any recording with the inner display's shape, such as the simulator's 2852 × 2006, reads rotation metadata for these two poses, rejects other shapes, and takes several times longer than flat frames. JSON output reports the full frame name as `device`. `frames list` shows the poses under manual frames when the pack has them; with an older pack, `--device "iPhone Duo Book Pose"` fails with an error that says to run `frames setup`.

```bash
frames -d "iPhone Duo Book Pose" inner-landscape.png
frames -d "iPhone Duo Laptop Pose" -c "Star White" inner-portrait.png
```

To capture from the simulator: `xcrun simctl io booted screenshot --display=1` for the outer display and `--display=3` for the inner display. Fold state comes from Device Hub's Closed, Book, and Open buttons. See the repository's `docs/iphone-duo.md` for capture, video, merge, and rebuild details.

The standard v4 asset bundle used by `frames` 1.7.2 includes these primary families:

- iPhone: iPhone Duo (inner and outer displays), iPhone 18 Pro, iPhone 18 Pro Max, iPhone 17, iPhone 17 Pro, iPhone 17 Pro Max, iPhone Air, iPhone 16, iPhone 16 Plus, iPhone 12-13 Pro, iPhone 12-13 Pro Max, iPhone 12-13 mini, iPhone 8 / 2020 SE
- iPad: iPad mini A20 Pro, iPad mini 2021, iPad 2021, iPad Air 2020, iPad Pro 2018-2021 11-inch, iPad Pro 2018-2021 12.9-inch, iPad Pro 2024 11-inch, iPad Pro 2024 13-inch
- Mac: MacBook Pro PROLED 14, MacBook Pro PROLED 16, MacBook Neo, MacBook Pro 13, MacBook Air 2020, MacBook Air M5 13, MacBook Air M5 15, MacBook Pro M5 14, MacBook Pro M5 16, iMac M4, Studio Display, Studio Display XDR
- Watch: Watch Series 7 41, Watch Series 7 45, Watch Series 11 42, Watch Series 11 46, Watch Ultra 2024, Watch Ultra 3, Watch Ultra 4

Current default variant resolution favors the newest matching frame for shared screenshot sizes:

- `iPhone 17 Portrait` (1206 × 2622) and `iPhone 17 Landscape` resolve to `iPhone 18 Pro Portrait` and `iPhone 18 Pro Landscape`
- `iPhone 17 Pro Max Portrait` (1320 × 2868) and `iPhone 17 Pro Max Landscape` resolve to `iPhone 18 Pro Max Portrait` and `iPhone 18 Pro Max Landscape`
- iPhone 18 Pro colors are Burgundy (default), Glacier, Silver, and Black
- With a pack that predates iPhone 18 Pro, the same sizes fall back to `iPhone 17 Pro` and `iPhone 17 Pro Max`; 16 Pro frames remain selectable with `--device`
- `iPhone 16` shares sizes with `iPhone 15 Pro`
- `iPhone 16 Plus` shares sizes with `iPhone 15 Pro Max`
- `MacBook Pro M5` shares sizes with `MacBook Pro 2021`
- Asset pack 4.2.1 also recognizes the verified 16-inch PROLED Default-setting CleanShot capture (3822 × 2478), its downsampled 2000 × 1297 copy, and 4128 × 2694 More Space. Each requires an exact width and height and resizes to the entire 3472 × 2266 opening.
- `MacBook Pro PROLED 14` (3024 × 1986) and `MacBook Pro PROLED 16` (3472 × 2266) come in Silver (default) and Space Black. The 14-inch shares its width with `MacBook Pro M5 14` (3024 × 1964), so width 3024 is matched by height
- `MacBook Air M5 13` shares sizes with `MacBook Air 2022`
- `Studio Display` shares sizes with `Studio Display XDR`
- `Watch Series 11` shares sizes with `Watch Series 10`
- `Watch Ultra 3` (422 × 514) resolves to `Watch Ultra 4`; Ultra 3 stays selectable with `--device`. iPad mini A20 Pro is 1512 × 2316 and 2316 × 1512 and shares no size

If an exact older variant is required, pass `--device` with the exact frame name instead of relying on auto-detection.

## Recommended Agent Workflow

1. Run `frames --json info ...` first when you do not control the screenshot source. For videos, run `frames --json video-info ...` when you need dimensions, duration, audio state, or the matched frame before rendering.
2. If the user asks for a specific device or color, confirm the exact names with `frames list` or `frames list-colors`.
3. Use `frames doctor` before changing config or re-downloading assets.
4. Use `--device` only when the user wants an exact frame, older variant, or a non-default shared-size match.
5. Use `--no-scale` only when the user explicitly wants native framed sizes instead of physically proportionate merges.
6. Choose `--preset compact` for smaller video exports. For transparency, use `--codec hevc-alpha` for Apple-compatible delivery on macOS, or `--alpha` for ProRes editing/compositing output. Use an explicit opaque `--background black` or `--background "#RRGGBB"` when requested.
7. For multi-video previews, choose `frames video -m` for simultaneous playback and `frames video -m --playback-offset` for left-to-right sequential playback.
8. Prefer `--strip-audio` for generated test artifacts unless the user specifically wants audio preserved.
9. After video rendering, verify with `ffprobe` when final output audio state, duration, codec, or stream count matters. For HEVC-alpha transparency, verify with a native Apple decoder or the intended Apple app: `ffprobe` and software HEVC decoding may expose only the opaque `yuv420p` base layer. That alone does not prove alpha is missing.
10. If an iPad screen recording probes as portrait but the visible content is landscape, rerun `video-info` with `--rotate counterclockwise` or `--rotate clockwise` and verify it resolves to the landscape frame before rendering.
