#!/usr/bin/env python3
"""Spot verticale 1080x1920 per Drive Organizer — Pillow + FFmpeg raw piping."""
import subprocess
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BVM = Path("D:/BACHATA_VIBES_SUITE")
HERE = Path(__file__).parent

FFMPEG = BVM / "scripts/ffmpeg/bin/ffmpeg.exe"
OUT = HERE / "spot_drive_organizer.mp4"

FONT_DIR = Path("C:/Windows/Fonts")
FBOLD = str(FONT_DIR / "segoeuib.ttf")
FREG = str(FONT_DIR / "segoeui.ttf")

W, H = 1080, 1920
FPS = 25
DUR = 17
FRAMES = FPS * DUR

# Google Drive palette
BLUE = (66, 133, 244)
GREEN = (52, 168, 83)
YELLOW = (251, 188, 4)
RED = (234, 67, 53)
WHITE = (255, 255, 255)
GRAY = (180, 180, 180)
BG = (18, 18, 18)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def center_text(draw, text, y, f, color=WHITE, shadow=True):
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    if shadow:
        draw.text((x + 2, y + 2), text, font=f, fill=(0, 0, 0))
    draw.text((x, y), text, font=f, fill=color)


def make_bg():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    # yellow accent lines top/bottom, like the Canva graphic
    draw.rectangle([0, 300, W, 306], fill=YELLOW)
    draw.rectangle([0, H - 500, W, H - 494], fill=YELLOW)
    return img


SCENES = [
    (0.0, 3.0, [(200, FBOLD, 62, "IL TUO GOOGLE DRIVE", WHITE, True)]),
    (0.0, 3.0, [(280, FBOLD, 62, "E' NEL CAOS?", RED, True)]),
    (3.0, 17.0, [(850, FBOLD, 90, "DRIVE", WHITE, True)]),
    (3.0, 17.0, [(950, FBOLD, 90, "ORGANIZER", WHITE, True)]),
    (5.5, 17.0, [(1120, FREG, 42, "riorganizza Google Drive con AI", GRAY, False)]),
    (8.0, 12.5, [(1230, FREG, 36, "Ollama locale + cloud solo se serve", BLUE, False)]),
    (8.0, 12.5, [(1290, FREG, 36, "i tuoi file non lasciano il PC", GREEN, False)]),
    (12.5, 17.0, [(1230, FREG, 36, "organizza  ·  rinomina  ·  deduplica", YELLOW, False)]),
    (12.5, 17.0, [(1290, FREG, 32, "open source  ·  gratis", GRAY, False)]),
    (14.5, 17.0, [(1450, FREG, 30, "github.com/giandemoncell-prog", WHITE, False)]),
    (14.5, 17.0, [(1495, FREG, 30, "/drive-organizer", WHITE, False)]),
]


def render_frame(t_sec, bg):
    img = bg.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    for t_start, t_end, items in SCENES:
        if t_start <= t_sec < t_end:
            for y, fp, size, text, color, shadow in items:
                center_text(draw, text, y, font(fp, size), color, shadow)
    return img


def main():
    print("1/2  Avvio FFmpeg encoder...")
    cmd = [
        str(FFMPEG), "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "pipe:0",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(DUR), "-movflags", "+faststart",
        "-shortest",
        str(OUT),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    print("2/2  Generazione frame con Pillow...")
    bg = make_bg()
    for i in range(FRAMES):
        t = i / FPS
        frame = render_frame(t, bg)
        proc.stdin.write(frame.tobytes())
        if i % 125 == 0:
            print(f"     {int(i / FRAMES * 100)}%  ({i}/{FRAMES})", end="\r")

    proc.stdin.close()
    _, stderr = proc.communicate()
    print()
    if proc.returncode == 0:
        size_mb = os.path.getsize(OUT) / (1024 * 1024)
        print(f"OK  Spot pronto: {OUT}  ({size_mb:.1f} MB)")
    else:
        print("ERRORE FFmpeg:")
        print(stderr.decode(errors="replace")[-1500:])


if __name__ == "__main__":
    main()
