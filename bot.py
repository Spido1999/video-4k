import os
import logging
import subprocess
import asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DOWNLOAD_DIR = Path("downloads")
OUTPUT_DIR = Path("outputs")
TARGET_RES = os.environ.get("TARGET_RES", "2k")   # "2k" or "4k"

RESOLUTIONS = {
    "2k": (2560, 1440),
    "4k": (3840, 2160),
}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_dirs():
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def upscale_video(input_path: Path, output_path: Path, target: str = "2k") -> bool:
    width, height = RESOLUTIONS.get(target, RESOLUTIONS["2k"])

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf",
        f"scale={width}:{height}:flags=lanczos,unsharp=5:5:1.5:5:5:0.0",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-c:a", "copy",
        str(output_path),
    ]

    log.info("Running FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error("FFmpeg error:\n%s", result.stderr)
        return False

    log.info("Upscale complete → %s", output_path)
    return True


# ── Bot Handlers ──────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Video Upscaler Bot*\n\n"
        "Send me any MP4 video (< 1 min) and I'll upscale it to *2K or 4K*!\n\n"
        "Commands:\n"
        "  /set2k  – target 2K (2560×1440)  ← default\n"
        "  /set4k  – target 4K (3840×2160)\n"
        "  /res    – show current target resolution",
        parse_mode="Markdown",
    )


async def set_2k(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["target"] = "2k"
    await update.message.reply_text("✅ Target set to *2K (2560×1440)*", parse_mode="Markdown")


async def set_4k(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["target"] = "4k"
    await update.message.reply_text("✅ Target set to *4K (3840×2160)*", parse_mode="Markdown")


async def show_res(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    target = ctx.user_data.get("target", TARGET_RES)
    w, h = RESOLUTIONS[target]
    await update.message.reply_text(f"🎯 Current target: *{target.upper()} ({w}×{h})*", parse_mode="Markdown")


async def handle_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user

    file_obj = msg.video or msg.document
    if not file_obj:
        await msg.reply_text("⚠️ Please send a video file (.mp4)")
        return

    if msg.video and msg.video.duration and msg.video.duration > 65:
        await msg.reply_text("⏱️ Video must be under 1 minute. Please trim it first.")
        return

    target = ctx.user_data.get("target", TARGET_RES)
    w, h = RESOLUTIONS[target]

    status_msg = await msg.reply_text(
        f"⬇️ Downloading your video...\n"
        f"🎯 Will upscale to *{target.upper()} ({w}×{h})*",
        parse_mode="Markdown",
    )

    file_id = file_obj.file_id
    tg_file = await ctx.bot.get_file(file_id)

    input_path = DOWNLOAD_DIR / f"{user.id}_{file_id[-8:]}_input.mp4"
    output_path = OUTPUT_DIR / f"{user.id}_{file_id[-8:]}_{target}.mp4"

    await tg_file.download_to_drive(input_path)

    await status_msg.edit_text(
        f"✅ Downloaded!\n🔄 Upscaling to *{target.upper()}*... (this may take 30–90s)",
        parse_mode="Markdown",
    )

    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(
        None, upscale_video, input_path, output_path, target
    )

    if not success:
        await status_msg.edit_text("❌ Upscaling failed. Make sure the video is a valid MP4 file.")
        input_path.unlink(missing_ok=True)
        return

    await status_msg.edit_text(f"⬆️ Uploading your {target.upper()} video...")

    file_size_mb = output_path.stat().st_size / 1e6

    if file_size_mb > 50:
        await status_msg.edit_text(
            f"⚠️ Output file is {file_size_mb:.1f} MB (Telegram limit: 50 MB).\n"
            "Consider using /set2k for smaller output."
        )
    else:
        with open(output_path, "rb") as f:
            await ctx.bot.send_video(
                chat_id=msg.chat_id,
                video=f,
                caption=(
                    f"🎬 *Upscaled to {target.upper()} ({w}×{h})*\n"
                    f"📦 Size: {file_size_mb:.1f} MB"
                ),
                parse_mode="Markdown",
                supports_streaming=True,
            )
        await status_msg.delete()

    input_path.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        log.error("❌ Set TELEGRAM_BOT_TOKEN environment variable first!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("set2k", set_2k))
    app.add_handler(CommandHandler("set4k", set_4k))
    app.add_handler(CommandHandler("res", show_res))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    log.info("🤖 Bot started! Waiting for videos...")
    app.run_polling()


if __name__ == "__main__":
    main()
