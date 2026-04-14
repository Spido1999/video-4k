# 🎬 video-4k

Upscale any MP4 video to 2K or 4K using GitHub Actions + FFmpeg. Free. No server needed.

## How to use

1. Upload your `.mp4` into the `input/` folder
2. GitHub Actions triggers automatically
3. Go to **Actions** tab → click the run → download from **Artifacts**

## Want 4K?

Also upload an empty file named `4k.txt` into `input/` alongside your video.

## Notes

- Videos must be under **1 minute** and under **100 MB**
- Artifacts (upscaled videos) are kept for **7 days** then auto-deleted
- Delete your video from `input/` after downloading to keep repo clean
