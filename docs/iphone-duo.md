# iPhone Duo

Frames adds Apple's iPhone Duo bezels to screenshots and screen recordings of both displays, in portrait and landscape, in Night Sky and Star White. A separate view shows the phone's back beside the outer screen. The artwork is part of the standard asset pack starting with Frames 1.5.0.

## Set up

Update Frames using your [installation method](../README.md#installation), then run `frames setup` to download the current pack, [AppleFrames420.zip](https://cdn.macstories.net/images/uploads/2026/11/04/appleframes420-1793823397151-4b30e2106a.zip). `frames doctor` tells you when your pack predates iPhone Duo.

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

Screenshots follow the interface orientation, so rotate the simulator for landscape. Apps built for iPhone-size screens, like Settings, stay in portrait on the outer display; Safari rotates. Book posture produces the same inner screenshot as Open. Apple's artwork has no half-folded view.

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

The builder copies the base PNGs unchanged and adds ten bezels, five screen masks, and six size entries to `NewFrames.json`. It checks each opening against the expected geometry, keeps the camera in the bezel, preserves the outer display's asymmetric corners, and verifies that lossless optimization leaves every decoded pixel unchanged. The ZIP has a fixed file order and timestamps. Apple's Design Resources License, included in the pack, governs the artwork; the repository's MIT license does not replace it.
