# Changelog

## 1.6.0 — 2026-11-02

Frames adds Apple device bezels to screenshots and screen recordings from the command line. Version 1.6.0 adds MacBook Pro with PROLED XDR Display, fixes iPad mini alignment, and moves to asset pack 4.1.0, the same pack the Apple Frames shortcut uses. Run `frames setup` after updating to download it.

### MacBook Pro with PROLED XDR Display

- Frames MacBook Pro with PROLED XDR Display screenshots with Apple's official bezels in Silver and Space Black. 14-inch screenshots are 3024 × 1986 and 16-inch screenshots are 3472 × 2266. The Dynamic Island is part of Apple's frame.
- The 14-inch shares its width with the M5 MacBook Pro, so 3024-wide screenshots now match by height: 3024 × 1964 still uses the M5 frame.
- `scripts/build_proled_assets.py` adds Apple's PNGs to the standard pack, and `frames doctor` notes when a pack predates these frames.

### One asset pack, 17% smaller

`frames setup` now downloads [AppleFrames410.zip](https://cdn.macstories.net/images/uploads/2026/11/02/appleframes410-1793619065631-29622fdbc3.zip) (50.2 MB, down from 60.8 MB), pack version 4.1.0. The Apple Frames shortcut uses the same pack, so the CLI and the shortcut no longer ship different files.

- `scripts/optimize_pack.py` recompresses every frame. A frame is reduced to 256 colors only when that change is invisible: its worst 32-pixel block may differ by at most 2/255 on white and black backgrounds. The rest, including every mask, are recompressed losslessly. PNG data went from 66.1 MB to 51.3 MB.
- The ZIP is 50,212,957 bytes with SHA-256 `3baf1d730cf5769582b37570841cc8a7e2c4c6e9000364412ff489bfbf861b0d`.

### Fixes

Thanks to [Gianpiero Spinelli](https://github.com/gianpispi) ([#11](https://github.com/viticci/frames-cli/pull/11)):

- **iPad mini screenshots line up with the bezel.** Older packs swapped the x and y offsets, which clipped 4 pixels off two edges and left a 4-pixel gap on the other two. Pack 4.1.0 has the correct offsets, and the CLI corrects older packs when it loads them. Screenshots and videos both benefit.

## 1.5.1 — 2026-10-23

Frames adds Apple device bezels to screenshots and screen recordings from the command line. Version 1.5.1 makes video framing and merges faster and fixes video support on Arch Linux. It uses the same asset pack as 1.5.0, so there is nothing to download after updating the CLI.

### Faster video framing and merges

Thanks to [Finn Voorhees](https://github.com/finnvoor) ([#10](https://github.com/viticci/frames-cli/pull/10)):

- **Bezels and masks are decoded once** per export instead of once per frame. Output frames are unchanged.
- **Transparent ProRes uses the hardware encoder on macOS.** Macs without a ProRes engine fall back to the software encoder automatically. On an M5 Ultra, a transparent merge of two 4-second iPhone recordings dropped from 12.4s to 3.2s. Opaque pixels stay fully opaque, and hardware-encoded files are tagged with the BT.601 color matrix they already used.
- **Merges composite each device at 30fps in RGBA**, the merge's own frame rate, instead of compositing at full rate and dropping frames afterwards. A merge of two 11-second recordings went from about 7s to 5.5s with H.264, and from about 8.3s to 6.6s with HEVC.

H.264 and HEVC merges still use the software encoder. The hardware encoder saved about a second but made merged screen recordings 5 to 9 times larger.

### Fixes

- `frames doctor` and `frames video` accept ffmpeg version strings with an `n` prefix, such as `ffmpeg version n9.0.1` on Arch Linux. Before, Frames reported video tools as missing on those systems. Thanks to [guitaripod](https://github.com/guitaripod) for the report ([#9](https://github.com/viticci/frames-cli/issues/9)).

## 1.5.0 — 2026-09-30

Frames adds Apple device bezels to screenshots and screen recordings from the command line. Version 1.5.0 adds **iPhone 18 Pro, iPhone 18 Pro Max, and iPhone Duo** using Apple's official artwork. The 18 Pro models become the default for their screen sizes, Duo joins the standard asset pack, and merged frames now match real-world proportions more precisely.

### Update the CLI and the asset pack

The new devices need **Frames 1.5.0 or later plus the new standard asset pack**. Updating the CLI alone does not download the new artwork.

1. Update Frames using your existing [installation method](README.md#installation), then check that `frames --version` prints `frames v1.5.0`.
2. Run `frames setup` and accept the download. It fetches [AppleFrames402.zip](https://cdn.macstories.net/images/uploads/2026/09/30/appleframes402-1790756136687-572a1ccddd.zip) (60.8 MB): the previous pack plus 16 iPhone 18 Pro bezels, 10 iPhone Duo bezels, nine screen masks, and Apple's Design Resources License.
3. Run `frames doctor`. If it says your pack predates iPhone 18 Pro or iPhone Duo, the CLI is still reading an older folder; run `frames setup` again or point it at the new one.

The ZIP is 60,821,581 bytes with SHA-256 `5fecdd29acf4c3c6215a05629a07e2c5b30439597933859a7a71e153adad8fd3`.

### iPhone 18 Pro is the new default

iPhone 18 Pro and 18 Pro Max share screen sizes with the 17 Pro models, so these inputs now use the new frames automatically:

| Input width × height | Automatic frame |
| --- | --- |
| 1206 × 2622 | iPhone 18 Pro Portrait |
| 2622 × 1206 | iPhone 18 Pro Landscape |
| 1320 × 2868 | iPhone 18 Pro Max Portrait |
| 2868 × 1320 | iPhone 18 Pro Max Landscape |

Both models come in **Burgundy** (the default), **Glacier**, **Silver**, and **Black**, in portrait and landscape, for images and videos. The 17 Pro frames remain available with `--device`:

```bash
frames -c Glacier screenshot.png
frames video recording.mp4
frames -d "iPhone 17 Pro Portrait" screenshot.png
```

With an older pack, these sizes keep using the 17 Pro frames. `frames list` shows the defaults your installed pack provides, and `frames info` lists only the variants it can render.

### iPhone Duo

Both displays work in portrait and landscape, in **Night Sky** (the default) and **Star White**, for images and videos:

| Input width × height | Automatic frame |
| --- | --- |
| 1398 × 2034 | iPhone Duo Outer Portrait |
| 2034 × 1398 | iPhone Duo Outer Landscape |
| 2007 × 2853 | iPhone Duo Inner Portrait |
| 2853 × 2007 | iPhone Duo Inner Landscape |

These are the sizes the Xcode 27.1 iPhone Duo simulator captures, and they match the screen openings in Apple's artwork exactly. Mockups at Apple's announced inner resolution, 1878 × 2670, are still detected and scaled. A manual view shows the phone's back beside the outer screen:

```bash
frames -d "iPhone Duo Outer Open" outer-portrait.png
```

Duo is no longer a separate, experimental pack. If you selected `Frames-Duo-Experimental` from 1.4.1, run `frames setup` to switch to the standard pack; JSON output no longer includes an `experimental` field. Simulator recordings of the inner display aren't detected automatically yet; select their frame with `--device`. See the [iPhone Duo guide](docs/iphone-duo.md) for capturing screenshots in the simulator and known limitations.

### More accurate proportional merges

Merged images and videos scale each device to its real-world size. Frames now measures each device by its visible body instead of its frame image, because Apple pads each image differently, and it aligns the bottoms of the devices themselves. Previously, an iPhone Duo next to an iPhone 18 Pro came out about 1% too small and 10 pixels out of alignment.

## 1.4.1 — 2026-09-10

Frames adds Apple device bezels to screenshots and screen recordings from the command line. Version 1.4.1 adds **experimental iPhone Duo support** using Apple's official artwork and published display resolutions. Developers can test both displays in both orientations, choose either finish, and show the outer screen alone or beside the phone's back.

### Install the separate Duo pack

Duo requires **Frames 1.4.1 or later plus the new asset pack**. Updating the CLI alone does not install the artwork. The standard `frames setup` download remains AppleFrames401.zip, so existing users keep their current setup unless they select the Duo pack.

1. Update Frames using your existing [installation method](README.md#installation), then check `frames --version`.
2. Download [Frames-Duo-Experimental.zip](https://cdn.macstories.net/images/uploads/2026/09/09/frames-duo-experimental-1788997654596-a33ef863e7.zip) (95.2 MB) and extract it.
3. Select the enclosed `Frames-Duo-Experimental` folder with `--assets` for one command, or save it as your default with `frames setup`.

```bash
# Verify and use the pack without changing your saved default
frames --assets /path/to/Frames-Duo-Experimental --json doctor
frames --assets /path/to/Frames-Duo-Experimental --json info duo.png
frames --assets /path/to/Frames-Duo-Experimental duo.png

# Optional: save the pack as your default
frames setup /path/to/Frames-Duo-Experimental
```

The path must identify the **extracted folder**, not the ZIP or CDN URL. The pack includes all existing frames and has 519 PNGs. Its asset format version remains 4. See the [complete Duo guide](https://github.com/viticci/frames-cli/blob/1.4.1/docs/iphone-duo-experimental.md) for copyable download commands, checksums, setup verification, and restoring a previous pack.

### Choose the outer-screen view

Once the Duo pack is selected, a **1398 × 2034** input automatically uses the single outer-screen frame. Both examples below use the same screenshot; separate output folders retain both results:

```bash
# Outer screen only
frames --device "iPhone Duo Outer Portrait" -o outer-screen outer-portrait.png

# Back of the phone on the left, outer screen on the right
frames --device "iPhone Duo Outer Open" -o outer-and-back outer-portrait.png
```

`--device` also works with `frames video` and `frames video-info`. The outer-and-back view is an explicit choice; automatic detection always selects the single-screen view.

### Displays, colors, and videos

| Exact input width × height | Automatic frame |
| --- | --- |
| 1398 × 2034 | iPhone Duo Outer Portrait |
| 2034 × 1398 | iPhone Duo Outer Landscape |
| 1878 × 2670 | iPhone Duo Inner Portrait |
| 2670 × 1878 | iPhone Duo Inner Landscape |

All five views support **Night Sky** and **Star White**. Night Sky is the default unless another color preference is saved. Existing merge, batch, output, and video options work with the pack:

```bash
frames --color "Star White" inner-landscape.png
frames --merge --colors "Star White,Night Sky" outer-portrait.png inner-landscape.png
frames --json video-info outer-recording.mp4
frames video --device "iPhone Duo Outer Open" outer-recording.mp4
frames video --alpha inner-recording.mp4
```

Use `--assets /path/to/Frames-Duo-Experimental` with these examples if the pack is not your saved default. Video framing requires ffmpeg 5.1+ and ffprobe 5.1+. Normal video output has an opaque white canvas; `--alpha` produces transparent ProRes MOV.

### Framing and asset changes

- Detection checks both native dimensions, including orientation, instead of accepting a matching width with an unrelated height.
- Duo image/video metadata reports `experimental: true`. `frames list` labels the installed experimental views and lists the outer-and-back view as a manual choice.
- Added explicit asset `resizeHeight` support alongside `resizeWidth`. Inner screenshots scale to the larger openings in Apple's supplied artwork; existing entries without an explicit height keep their previous proportional behavior.
- Screen masks follow the enclosed openings in Apple's PNGs. The asymmetric outer corners, camera, and partly transparent bezel edges are preserved. Frames does not add concept interface controls to screenshots.
- Added a reproducible asset builder. It preserves existing frame files, checks the expected artwork dimensions, includes provenance and Apple's license, and refuses to overwrite an existing destination.
- Removed unused descriptive metadata from the ten Duo bezel PNGs and applied lossless compression where smaller. This saves 248,931 bytes (1.82%), with identical decoded RGBA pixels. The complete asset archive is 95,246,128 bytes.
- Updated the README, agent skill, help, splash, and dedicated Duo guide with installation and view-selection instructions.

### Experimental status and verification

The mappings use Apple's announced resolutions and official artwork. Generated screenshots and recordings verify framing geometry; they do not establish real-device capture behavior, Display Zoom support, or shipping iOS interface placement. Keep native input dimensions and let Frames perform the inner-display scaling.

The release checks include a fresh download from the final CDN URL, matching ZIP checksum and contents, temporary and saved-default asset selection, all five views in both finishes, an existing iPhone frame, image merging, and four Duo test-video exports. All 87 tests pass on Python 3.8 and 3.14, including native HEVC-alpha verification on the verification Mac. The complete CLI, builder, and tests compile under Python 3.8 through 3.14.

[Full comparison with 1.4.0](https://github.com/viticci/frames-cli/compare/1.4.0...1.4.1)

## 1.4.0 — 2026-09-08

Frames adds Apple device bezels to screenshots and screen recordings from the command line. Version 1.4.0 adds compressed video with transparency through an optional HEVC-alpha export mode on macOS. It also improves video merging, image transparency, output file handling, and scripting reliability.

### Compressed transparent video

- Added `frames video --codec hevc-alpha` for transparent HEVC-with-alpha MOV exports. This provides a smaller delivery format for compatible Apple apps and devices.
- Supports single videos, simultaneous merges, and sequential merges with `--playback-offset`, including device masks, rotation, per-input colors, and scaling by physical size.
- Defaults to a transparent canvas. An explicit `--background white`, `--background black`, or `--background "#RRGGBB"` overrides the whole canvas, including padding.
- Uses `.mov` filenames automatically. Explicit output files must also use `.mov`.
- Supports the existing size/quality presets with these HEVC-alpha bitrate targets:

| Preset | Target bitrate |
| --- | --- |
| `compact` | 4 Mbps |
| `balanced` | 7 Mbps |
| `best` (default) | 10 Mbps |

These are encoder bitrate targets, not file-size guarantees. Lower presets trade image detail for smaller files. HEVC-alpha rejects `--quality`; use `--preset` instead.

```bash
# Transparent HEVC MOV at the default best preset
frames video --codec hevc-alpha recording.mp4

# Smaller transparent export
frames video --codec hevc-alpha --preset compact recording.mp4

# Transparent side-by-side merge
frames video -m --codec hevc-alpha first.mp4 second.mp4

# Transparent merge with sequential playback
frames video -m --playback-offset --codec hevc-alpha first.mp4 second.mp4
```

HEVC-alpha requires macOS and an FFmpeg build with HEVC alpha support through VideoToolbox, Apple's video encoding framework. Frames checks alpha-encoder support before rendering. Unsupported configurations produce an error; Frames does not silently substitute opaque HEVC or ProRes. The receiving app must support HEVC with alpha.

HEVC-alpha output uses even encoded dimensions. Individual exports pad the device frame when necessary. Merges keep each device's original frame geometry for physical scaling and pad only the final canvas. Padding uses the selected background.

### File size example

Before release, a 20.27-second iPhone recording was framed at 1350 × 2760 pixels with its original audio:

| Export | File size |
| --- | --- |
| ProRes 4444 with transparency | 3.70 GB |
| HEVC-alpha, `best` | 30.3 MB |
| HEVC-alpha, `balanced` | 22.8 MB |
| HEVC-alpha, `compact` | 15.8 MB |

Sizes use decimal units and describe this recording, not a guaranteed compression ratio. Apple's native decoder verified that sampled transparency matched exactly for every HEVC-alpha preset. Copied audio packets matched the source.

### Existing export behavior

- The default H.264 MP4 still has a white canvas outside the device bezel. Use `--background` to choose another color.
- `--alpha` and `--background transparent` still select ProRes 4444 MOV unless `--codec hevc-alpha` is explicitly selected. `--alpha --codec hevc` also remains ProRes.
- ProRes is an editing and compositing format that can produce much larger files than the source recording. Its large size is expected, and `--preset compact` does not change ProRes encoding settings.
- Plain `--codec hevc` still creates opaque HEVC MP4. Select `--codec hevc-alpha` for compressed transparency.
- Single-video exports preserve audio unless `--strip-audio` is passed. Sequential merges concatenate audio and provide silence for inputs without audio. Simultaneous merges continue to omit mixed audio.

### Video rendering and output files

- Video merges now frame and combine their sources in one FFmpeg operation. This removes the temporary encoded video for each input and the extra encoding pass.
- Direct merges retain device masks, transparent spacing, bottom alignment, and sequential playback holds for future and completed videos.
- Video metadata inspection reads frame-image headers without decoding and caching full frame images.
- Fixed a progress-reporting stall that could occur when FFmpeg produced enough diagnostic output to fill its error pipe. Error details remain available, and interrupted renders stop the child process.
- When an output refers to an input file, including through a symbolic or hard link, rendering uses a temporary destination and replaces the output only after success. Failed renders preserve the original input.
- Multiple individual exports reject paths that would overwrite another input or send distinct inputs to the same output filename before any rendering begins.
- Source-size and savings reports use the original input sizes, including when an export replaces an input.

### Image framing

- Fixed merged images applying transparency twice. Partly transparent bezel pixels now retain their original alpha and color values.
- Reduced retained frame/mask images and avoided unnecessary image copies to limit memory use during repeated framing.
- Corrected batch-merge JSON so each frame's `scale_factor` describes the batch that was actually written.

### Command-line and configuration fixes

- Global `--json`, `--assets`, `--verbose`/`-v`, and `--no-color` options now work before or after every command without discarding earlier values.
- Verbose device, resize, and mask diagnostics go to standard error, keeping JSON on standard output parseable.
- Invalid configuration produces an actionable error that identifies the configuration file. Saved settings are no longer silently ignored. `frames doctor` remains usable to diagnose the problem.
- `frames setup --subfolder` and `frames setup --no-subfolder`, when used without an asset path, update only the saved output preference. They no longer enter interactive setup or check video dependencies.
- Asset checks handle unreadable version files and malformed metadata more reliably.

### JSON, documentation, and validation

- Added `output_codec` to rendered-video JSON for individual exports, merged output, and each merged input. Values are `h264`, `hevc`, `prores`, or `hevc-alpha`; the existing per-input `codec` field still describes the source.
- Documented HEVC-alpha merge geometry: per-input `output_dimensions` describes the original framed tile with `padded: false`; top-level `dimensions` describes the final encoded canvas.
- Updated the README, agent skill, CLI help, and splash with export recipes, format tradeoffs, configuration behavior, and JSON guidance.
- Documented native alpha verification. `ffprobe` and software HEVC decoders can expose only the opaque base layer; that alone does not show whether an HEVC-alpha file contains transparency.
- All 82 tests passed on Python 3.8 and 3.14, with no skipped tests on the verification Mac. The complete CLI and all six test modules compiled under CPython 3.8 through 3.14.
- Added an optional macOS regression test that decodes real HEVC-alpha exports with AVFoundation and checks masks, partly transparent pixels, merged geometry, and opaque padding. It requires FFmpeg, ffprobe, and a working Swift compiler, and skips when those prerequisites are unavailable.
- Verified all ten help pages, the splash, real screenshot and video exports, native transparency, audio preservation, rotation, both merge playback modes, and the installed CLI and skill.

Thanks to @iTwenty for the report and use case in [issue #5](https://github.com/viticci/frames-cli/issues/5).

[Full comparison with 1.3.2](https://github.com/viticci/frames-cli/compare/1.3.2...1.4.0)
