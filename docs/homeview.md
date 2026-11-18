# Apple HomeView

Frames adds Apple HomeView bezels to screenshots and screen recordings: the tabletop model in Silver, Starlight, Rose Pink, and Space Gray, and the wall-mounted model in Silver and Space Gray. They need Frames 1.8.0 and asset pack 4.3.0. Run `frames setup` after updating to download the pack.

Apple publishes no HomeView bezels. These frames come from Apple's product images on the Apple Store, with the screen picture removed. They are unofficial.

## Sizes

HomeView's display is 1088 × 1088 pixels. Frames detects two capture sizes:

| Input width × height | Source | Automatic frame |
| --- | --- | --- |
| 1088 × 1088 | [HomeView Capture](https://github.com/DylanMcD8/HomeView-Capture) | HomeView, at 1:1 |
| 1080 × 1080 | QuickTime | HomeView, scaled to 1088 × 1088 |

The tabletop model is the automatic choice. Select the wall-mounted model by name. Silver is the default finish for both:

```bash
frames homeview.png
frames -c "Rose Pink" homeview.png
frames -d "HomeView Wall Mounted" -c "Space Gray" homeview.png
frames video quicktime-recording.mov
```

Framed images are 1260 × 1494 pixels for the tabletop model and 1260 × 1260 for the wall-mounted model.

## Capture the screen

HomeView has no screenshot shortcut. There are two ways to get its screen onto a Mac:

- **HomeView Capture**, a free Mac app by Dylan McDonald, saves full-quality 1088 × 1088 PNGs over Wi-Fi. Use it for screenshots.
- **QuickTime Player** can record HomeView's screen in a Movie Recording window, at 1080 × 1080 and with more compression. Use it for recordings.

A QuickTime capture must be exactly the 1080 × 1080 screen. If you crop a screenshot of the QuickTime window by hand, any border you keep shows up inside the frame's screen.

## Rebuild the frames

`scripts/build_homeview_assets.py` builds the frames from six Apple Store images. Its docstring has the download commands. The builder finds the display opening in each image, removes the picture, and scales the image so the opening is exactly 1088 × 1088. The opening is the same size relative to the body as on the real device: 86.3% of its 145.5 mm width.
