# iPhone Duo

Frames adds Apple's iPhone Duo bezels to screenshots and screen recordings of both displays, in portrait and landscape, in Night Sky and Star White. A separate view shows the phone's back beside the outer screen, and two partially open poses show inner screenshots on a folded phone. The artwork is part of the standard asset pack starting with Frames 1.5.0; the poses need Frames 1.7.2 and asset pack 4.2.2.

## Set up

Update Frames using your [installation method](../README.md#installation), then run `frames setup` to download the current pack, [AppleFrames422.zip](__PACK_URL__). `frames doctor` tells you when your pack predates iPhone Duo or the partially open poses.

If you used the separate `Frames-Duo-Experimental` pack from Frames 1.4.1, run `frames setup` too. It saves the standard pack as your default, and you can delete the old folder. An existing `FRAMES_ASSETS` environment variable takes precedence over the saved path; update or unset it if it points at the old pack.

## Sizes

Frames detects the display and orientation from both input dimensions:

| Input width × height | Automatic frame |
| --- | --- |
| 1398 × 2034 | iPhone Duo Outer Portrait |
| 2034 × 1398 | iPhone Duo Outer Landscape |
| 2007 × 2853 | iPhone Duo Inner Portrait |
| 2853 × 2007 | iPhone Duo Inner Landscape |

These are the sizes the Xcode 27.1 iPhone Duo simulator captures, and they match the screen openings in Apple's artwork exactly. Apple's specifications list the inner display at 1878 × 2670; mockups made at that size, or 2670 × 1878, are also detected and scaled to the same frames. Do not resize screenshots yourself or add a camera cutout; the outer camera is part of Apple's frame.

## Views and finishes

The outer screen alone is the automatic choice for a 1398 × 2034 screenshot. To show the phone's back beside it, select the rear view by name. Night Sky is the default finish:

```bash
frames outer-portrait.png
frames -d "iPhone Duo Outer Open" outer-portrait.png
frames -c "Star White" inner-landscape.png
frames --merge outer-portrait.png inner-landscape.png
```

`--device` (or `-d`) selects one frame for the whole command. To export both outer views, run two commands with different output folders.

## Capture screenshots in the simulator

Xcode 27.1 includes an iPhone Duo simulator. It needs the iOS 27.1 simulator runtime, which `xcodebuild -downloadPlatform iOS` installs. In Xcode 27's Device Hub app, the Closed, Book, and Open buttons fold and unfold the phone. The inner display is off while the phone is closed, and the outer display is off while it is open or in Book posture.

```bash
xcrun simctl io booted screenshot --display=1 outer.png   # outer display
xcrun simctl io booted screenshot --display=3 inner.png   # inner display
```

Screenshots follow the interface orientation, so rotate the simulator for landscape. Apps built for iPhone-size screens, like Settings, stay in portrait on the outer display; Safari rotates. Book posture captures the inner display as a flat image at the same resolution as Open. Some apps adjust their layout in Book posture.

## Partially open poses

The partially open poses are manual frames for inner-display screenshots. They use the perspective geometry and reflections sampled from the original previews in Apple's Photoshop templates. Select Book Pose for landscape screenshots or Laptop Pose for portrait screenshots:

```bash
frames -d "iPhone Duo Book Pose" -c "Star White" inner-landscape.png
frames -d "iPhone Duo Laptop Pose" -c "Star White" inner-portrait.png
```

`iPhone Duo Book Pose` and `iPhone Duo Laptop Pose` are aliases for `iPhone Duo Inner Partially Open Landscape` and `iPhone Duo Inner Partially Open Portrait`.

Book Pose accepts 2853 × 2007 screenshots and Laptop Pose accepts 2007 × 2853 screenshots, plus mockups at Apple's announced 2670 × 1878 and 1878 × 2670. Both come in Night Sky (the default) and Star White.

The poses need Frames 1.7.2 or later and asset pack 4.2.2. Run `frames setup` to download the pack. `frames doctor` notes when your pack predates the poses, and `frames list` shows them under Manual frames once they are installed. Framing uses Pillow only.

Both poses are for still images. `frames video` stops with a message that they are available for screenshots only.

## Videos

`frames video` and `frames video-info` use the same sizes, views, and finishes:

```bash
frames video outer-recording.mp4
frames video -d "iPhone Duo Outer Open" outer-recording.mp4
frames video --alpha -c "Star White" outer-recording.mp4
```

Simulator recordings of the inner display (`xcrun simctl io booted recordVideo --display=3`) are 2006 × 2852, because video encoders need even dimensions, and they carry rotation metadata. Frames doesn't detect them automatically yet, so select the frame that matches the recording's orientation, for example `frames video -d "iPhone Duo Inner Landscape" inner-recording.mov`.

## Merging with other devices

Merged images and videos show devices at their real relative sizes. From Apple's specifications, iPhone Duo is 117.8 mm tall, 84.1 mm wide closed, and 164.6 mm wide open. Next to an iPhone 18 Pro, which is 150.0 mm tall, a closed Duo in portrait or an open Duo in landscape is about 79% of its height. Frames measures each device by its visible body, so differently padded frame images don't skew the result, and it aligns device bottoms.

## Known limitations

- Apple's outer landscape artwork has the camera at the top left. Screenshots taken in the opposite landscape orientation are the same size, but their camera area is at the bottom right, so the frame's camera covers part of the screenshot.
- Capture sizes are verified in the Xcode 27.1 simulator, not on iPhone Duo hardware. Display Zoom modes are untested.

## Rebuild the pack

The standard pack adds Apple's iPhone Duo artwork to the previous pack with `scripts/build_duo_assets.py`. Download Apple's [iPhone Duo artwork](https://devimages-cdn.apple.com/design/resources/download/Bezel-iPhone-Duo.dmg) and keep its `PNG` folder next to `Apple Design Resources License.rtf`. The base pack must not already include Duo, and the output folder and ZIP must not exist:

```bash
python3 scripts/build_duo_assets.py \
  --source /path/to/Bezel-iPhone-Duo/PNG \
  --base-assets /path/to/Frames \
  --output /path/to/new/Frames \
  --archive /path/to/AppleFrames402.zip
```

This builder copies the base PNGs unchanged and adds ten bezels, five screen masks, and six size entries to `NewFrames.json`. It checks each opening against the expected geometry, keeps the camera in the bezel, preserves the outer display's asymmetric corners, and verifies that lossless optimization leaves every decoded pixel unchanged. The ZIP has a fixed file order and timestamps. Apple's Design Resources License, included in the pack, governs the artwork; the repository's MIT license does not replace it.

The partially open poses come from the Photoshop templates in the same download. `scripts/build_duo_folded_assets.py` adds them to a pack that already has iPhone Duo. It needs Python, Pillow, and ImageMagick (`magick` on your PATH) to read the templates' layers; ImageMagick is a build-time dependency only. It writes each pose's frames, screen masks, and camera overlay, plus one catalog entry per pose with the perspective and reflection data:

```bash
python3 scripts/build_duo_folded_assets.py \
  --source /Volumes/Bezel-iPhone-Duo/Photoshop \
  --base-assets /path/to/Frames \
  --output /path/to/Frames-with-folded-Duo
```

Use `frames --assets /path/to/Frames-with-folded-Duo -d "iPhone Duo Book Pose" inner-landscape.png` to try the built pack.

`scripts/release_pack.py` turns a built pack into a release. It checks that every file of the previous pack is still there and byte-identical, that the catalog only gains the named entries, and that every new file is a PNG for one of them. Then it copies the pack to a new folder, sets `version.txt`, writes the ZIP, and prints its size and SHA-256. The previous pack can be its published ZIP or a folder:

```bash
python3 scripts/release_pack.py /path/to/Frames-with-folded-Duo \
  --base /path/to/AppleFrames421.zip \
  --version 4.2.2 \
  --added "iPhone Duo Inner Partially Open Landscape" \
  --added "iPhone Duo Inner Partially Open Portrait" \
  --output /path/to/Frames-4.2.2 \
  --archive /path/to/AppleFrames422.zip
```
