"""Generate branded BMP images for WiX installer dialogs.

Layout notes (WixUI_InstallDir):
  - WelcomeDlg / ExitDialog: dialog.bmp displayed at (0,0) 370x234 dialog-units.
    WiX places its OWN text starting at X≈135 du (≈180 px).
    So LEFT 0-163 px = our branded panel, RIGHT 164-493 = clean for WiX text.
  - Interior dialogs: banner.bmp at top 493x58 px.
    WiX title text at X≈15, Y≈6 and description at X≈25, Y≈23.
    So keep LEFT 0-340 px clean; put branding on the RIGHT side.
"""
from PIL import Image, ImageDraw, ImageFont
import os, math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Brand colours
PRIMARY   = (16, 24, 48)      # Deep navy
ACCENT    = (0, 120, 215)     # Modern blue
ACCENT2   = (0, 153, 255)     # Lighter blue
WHITE     = (255, 255, 255)
LIGHT     = (230, 240, 250)
GRAY      = (180, 195, 210)
BG_RIGHT  = (246, 249, 252)   # Very light blue-gray for right panel

# Left panel width in pixels (must stay under WiX text start ≈180 px)
PANEL_W = 164

def _gradient(draw, box, c1, c2, vertical=True):
    x0, y0, x1, y1 = box
    steps = (y1 - y0) if vertical else (x1 - x0)
    for i in range(max(steps, 1)):
        t = i / max(steps - 1, 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        if vertical:
            draw.line([(x0, y0 + i), (x1, y0 + i)], fill=(r, g, b))
        else:
            draw.line([(x0 + i, y0), (x0 + i, y1)], fill=(r, g, b))

def _try_font(size, bold=False):
    names = [
        "segoeui" + ("b" if bold else ""),
        "calibri" + ("b" if bold else ""),
        "arial" + ("bd" if bold else ""),
    ]
    for name in names:
        try:
            return ImageFont.truetype(name + ".ttf", size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()

def _draw_circle(draw, cx, cy, r, fill):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

def _center_text(draw, text, font, cx, y, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, y), text, fill=fill, font=font)


def generate_dialog_bmp():
    """493x312 — Welcome & Finish pages.

    Left 164 px: branded navy panel with logo, title, features.
    Right 329 px: clean light background (WiX puts its text here).
    """
    W, H = 493, 312
    img = Image.new("RGB", (W, H), BG_RIGHT)
    draw = ImageDraw.Draw(img)

    # ── Right side: subtle gradient for a modern feel ──
    _gradient(draw, (PANEL_W, 0, W, H), WHITE, BG_RIGHT)

    # ── Left panel: deep navy gradient ──
    _gradient(draw, (0, 0, PANEL_W, H), PRIMARY, (10, 35, 70))

    # Subtle diagonal texture on left panel
    for i in range(0, PANEL_W + H, 4):
        alpha = int(6 + 3 * math.sin(i * 0.03))
        c = tuple(min(255, ch + alpha) for ch in PRIMARY)
        draw.line([(min(i, PANEL_W), 0), (max(0, i - H), min(H, i))], fill=c, width=1)

    # Top accent stripe across left panel
    _gradient(draw, (0, 0, PANEL_W, 3), ACCENT, ACCENT2, vertical=False)

    # ── Logo circle ──
    cx = PANEL_W // 2  # center of left panel
    cy = 70
    # Glow
    for r in range(44, 34, -1):
        alpha = int(18 * (44 - r) / 10)
        c = tuple(min(255, ch + alpha) for ch in ACCENT)
        _draw_circle(draw, cx, cy, r, c)
    _draw_circle(draw, cx, cy, 34, ACCENT)
    _draw_circle(draw, cx, cy, 30, WHITE)
    # "SM" inside circle
    sm_font = _try_font(22, bold=True)
    _center_text(draw, "SM", sm_font, cx, cy - 13, ACCENT)

    # ── Title text ──
    title_font = _try_font(16, bold=True)
    sub_font   = _try_font(10)
    small_font = _try_font(9)

    _center_text(draw, "SM Scolers", title_font, cx, 120, WHITE)
    _center_text(draw, "Attendance", sub_font, cx, 143, LIGHT)
    _center_text(draw, "Management System", sub_font, cx, 158, LIGHT)

    # ── Feature badges (vertical stack) ──
    features = ["\u2022 Biometric", "\u2022 Firebase Sync", "\u2022 SMS Alerts", "\u2022 PDF Reports"]
    feat_y = 186
    for feat in features:
        draw.text((16, feat_y), feat, fill=ACCENT2, font=small_font)
        feat_y += 16

    # ── Bottom: version & copyright ──
    _center_text(draw, "v13.0", small_font, cx, H - 42, GRAY)
    _center_text(draw, "\u00a9 2026 SM Scolers", small_font, cx, H - 26, GRAY)

    # ── Accent line at panel edge ──
    draw.line([(PANEL_W - 1, 0), (PANEL_W - 1, H)], fill=ACCENT, width=2)

    path = os.path.join(SCRIPT_DIR, "dialog.bmp")
    img.save(path, "BMP")
    print(f"  Created: dialog.bmp ({W}x{H})")


def generate_banner_bmp():
    """493x58 — Top banner for License / InstallDir / Verify pages.

    WiX places title at X≈15 and description at X≈25, so keep LEFT clean.
    Put branding on the RIGHT side of the banner.
    """
    W, H = 493, 58
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # Subtle gradient
    _gradient(draw, (0, 0, W, H), WHITE, (245, 249, 253))

    # Bottom accent line
    _gradient(draw, (0, H - 2, W, H), ACCENT, ACCENT2, vertical=False)

    # Right side: small SM circle
    cx = W - 32
    cy = H // 2
    _draw_circle(draw, cx, cy, 18, ACCENT)
    _draw_circle(draw, cx, cy, 15, WHITE)
    sm_font = _try_font(11, bold=True)
    _center_text(draw, "SM", sm_font, cx, cy - 8, ACCENT)

    # Decorative dots
    for i in range(3):
        _draw_circle(draw, W - 60 - i * 10, cy, 2, ACCENT2)

    path = os.path.join(SCRIPT_DIR, "banner.bmp")
    img.save(path, "BMP")
    print(f"  Created: banner.bmp ({W}x{H})")


def generate_exclamation_icon():
    """32x32 exclamation icon for validation dialogs."""
    W = H = 32
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    _draw_circle(draw, 16, 16, 14, ACCENT)
    f = _try_font(18, bold=True)
    draw.text((12, 2), "!", fill=WHITE, font=f)
    path = os.path.join(SCRIPT_DIR, "exclamation.bmp")
    img.save(path, "BMP")
    print(f"  Created: exclamation.bmp ({W}x{H})")


if __name__ == "__main__":
    print("Generating installer bitmaps...")
    generate_dialog_bmp()
    generate_banner_bmp()
    generate_exclamation_icon()
    print("Done!")
