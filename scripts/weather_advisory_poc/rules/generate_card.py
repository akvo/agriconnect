"""
Generate a visual advisory card (PNG) for WhatsApp broadcast.
Uses Pillow to render a clean, scannable image from triggered rules + forecast.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime, timedelta
import json
import sys
import subprocess


# ── Colors ─────────────────────────────────────────────────────────────
BG           = "#FFFFFF"
HEADER_BG    = "#1B4332"
HEADER_TEXT  = "#FFFFFF"
BODY_TEXT     = "#1B1B1B"
MUTED_TEXT   = "#6B7280"
DO_BG        = "#ECFDF5"
DO_BORDER    = "#A7F3D0"
DO_ICON      = "#059669"
DONT_BG      = "#FEF2F2"
DONT_BORDER  = "#FECACA"
DONT_ICON    = "#DC2626"
WARN_BG      = "#FFFBEB"
WARN_BORDER  = "#FDE68A"
WARN_TEXT    = "#92400E"
DIVIDER      = "#E5E7EB"
RAIN_BAR     = "#93C5FD"
RAIN_BAR_HEAVY = "#3B82F6"
FORECAST_BG  = "#F8FAFC"
BEST_DAY_BG  = "#F0FDF4"
BEST_DAY_BORDER = "#86EFAC"


# ── Font helpers ───────────────────────────────────────────────────────
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a system font. Prefer SF Pro or Helvetica on macOS."""
    if bold:
        candidates = [
            ("/System/Library/Fonts/SFPro.ttf", 0),
            ("/System/Library/Fonts/Helvetica.ttc", 1),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/SFPro.ttf", 0),
            ("/System/Library/Fonts/Helvetica.ttc", 0),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ]
    for path, index in candidates:
        try:
            return ImageFont.truetype(path, size, index=index)
        except (OSError, IndexError):
            continue
    return ImageFont.load_default(size)


# ── Drawing helpers ────────────────────────────────────────────────────
def draw_rounded_rect(draw, xy, fill, radius=12, outline=None, outline_width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=outline_width)


def draw_rain_drop(draw, cx, cy, size, color="#3B82F6"):
    """Draw a simple raindrop shape."""
    s = size
    # Teardrop using ellipse + triangle
    draw.ellipse([cx - s, cy, cx + s, cy + s * 2], fill=color)
    draw.polygon([(cx, cy - s), (cx - s, cy + s // 2), (cx + s, cy + s // 2)], fill=color)


def draw_sun(draw, cx, cy, radius, color="#F59E0B"):
    """Draw a simple sun circle."""
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
    # Rays
    for i in range(8):
        import math
        angle = i * math.pi / 4
        x1 = cx + int((radius + 3) * math.cos(angle))
        y1 = cy + int((radius + 3) * math.sin(angle))
        x2 = cx + int((radius + 7) * math.cos(angle))
        y2 = cy + int((radius + 7) * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill=color, width=2)


def draw_cloud_rain(draw, cx, cy, intensity="light"):
    """Draw cloud + rain drops. intensity: light, moderate, heavy."""
    # Cloud body
    cloud_color = "#94A3B8" if intensity == "heavy" else "#CBD5E1"
    draw.rounded_rectangle([cx - 16, cy - 6, cx + 16, cy + 6], radius=6, fill=cloud_color)
    draw.rounded_rectangle([cx - 10, cy - 12, cx + 10, cy], radius=6, fill=cloud_color)

    # Rain drops
    drop_color = RAIN_BAR_HEAVY if intensity == "heavy" else "#60A5FA"
    if intensity in ("moderate", "heavy"):
        for dx in [-8, 0, 8]:
            draw.line([cx + dx, cy + 10, cx + dx - 2, cy + 17], fill=drop_color, width=2)
    if intensity == "heavy":
        for dx in [-4, 4]:
            draw.line([cx + dx, cy + 14, cx + dx - 2, cy + 20], fill=drop_color, width=2)
    if intensity == "light":
        draw.line([cx, cy + 10, cx - 2, cy + 16], fill=drop_color, width=2)


def draw_weather_icon(draw, cx, cy, rain_mm):
    """Draw appropriate weather icon based on rainfall amount."""
    if rain_mm >= 8:
        draw_cloud_rain(draw, cx, cy, "heavy")
    elif rain_mm >= 3:
        draw_cloud_rain(draw, cx, cy, "moderate")
    elif rain_mm >= 0.5:
        draw_cloud_rain(draw, cx, cy, "light")
    else:
        draw_sun(draw, cx, cy, 8)


def draw_checkbox(draw, x, y, checked=True, color="#059669"):
    """Draw a filled checkbox with checkmark, or empty red X."""
    if checked:
        draw.rounded_rectangle([x, y, x + 18, y + 18], radius=4, fill=color)
        # Checkmark
        draw.line([x + 4, y + 9, x + 7, y + 13], fill="#FFFFFF", width=2)
        draw.line([x + 7, y + 13, x + 14, y + 5], fill="#FFFFFF", width=2)
    else:
        draw.rounded_rectangle([x, y, x + 18, y + 18], radius=4, fill="#DC2626")
        # X mark
        draw.line([x + 4, y + 4, x + 14, y + 14], fill="#FFFFFF", width=2)
        draw.line([x + 14, y + 4, x + 4, y + 14], fill="#FFFFFF", width=2)


# ── Main card generator ───────────────────────────────────────────────
def generate_advisory_card(
    location: str,
    date_range: str,
    variety_stage: str,
    forecast_days: list[dict],
    do_actions: list[str],
    dont_actions: list[str],
    best_spray_day: str | None,
    best_harvest_day: str | None,
    risk_alerts: list[str],
    output_path: str = "advisory_card.png",
):
    W = 720
    MARGIN = 32
    CONTENT_W = W - 2 * MARGIN

    # Fonts
    font_title = get_font(24, bold=True)
    font_subtitle = get_font(16)
    font_body = get_font(16)
    font_body_bold = get_font(16, bold=True)
    font_small = get_font(13)
    font_day = get_font(14, bold=True)
    font_section = get_font(15, bold=True)

    # ── Pre-calculate height ───────────────────────────────────────
    y = 0
    y += 90   # header
    y += 12   # gap
    y += 100  # forecast strip
    y += 20   # gap + divider
    y += 28   # "This week" header
    y += len(do_actions) * 34 + 8
    y += 16   # gap
    y += 28   # "Avoid" header
    y += len(dont_actions) * 34 + 8
    y += 16   # gap + divider
    y += 32   # spray day
    y += 32   # harvest day
    y += len(risk_alerts) * 34
    y += 32   # bottom padding

    H = max(y, 480)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    y = 0

    # ── Header ─────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, 84], fill=HEADER_BG)

    # Location pin (drawn, not emoji)
    px, py = MARGIN, 18
    draw.ellipse([px, py, px + 10, py + 10], fill="#F87171")
    draw.polygon([(px + 5, py + 14), (px, py + 7), (px + 10, py + 7)], fill="#F87171")

    draw.text((MARGIN + 18, 14), location, fill=HEADER_TEXT, font=font_title)
    draw.text((MARGIN + 18, 44), f"{date_range}   {variety_stage}", fill="#86EFAC", font=font_subtitle)

    y = 96

    # ── Forecast strip ─────────────────────────────────────────────
    draw_rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 95], fill=FORECAST_BG, radius=10)

    day_w = CONTENT_W // len(forecast_days)
    max_rain = max(d["rain_mm"] for d in forecast_days) or 1

    for i, day in enumerate(forecast_days):
        x = MARGIN + i * day_w
        cx = x + day_w // 2

        # Day name centered
        bbox = draw.textbbox((0, 0), day["day_short"], font=font_day)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y + 8), day["day_short"], fill=MUTED_TEXT, font=font_day)

        # Weather icon (drawn)
        draw_weather_icon(draw, cx, y + 36, day["rain_mm"])

        # Rain amount
        rain_text = f"{day['rain_mm']:.0f}mm" if day["rain_mm"] >= 1 else "<1"
        bbox = draw.textbbox((0, 0), rain_text, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y + 54), rain_text, fill=BODY_TEXT, font=font_small)

        # Rain bar
        bar_h = max(3, int(22 * day["rain_mm"] / max_rain))
        bar_color = RAIN_BAR_HEAVY if day["rain_mm"] >= 5 else RAIN_BAR
        bar_top = y + 86 - bar_h
        draw.rounded_rectangle([cx - 8, bar_top, cx + 8, y + 86], radius=3, fill=bar_color)

    y += 106

    # ── Divider ────────────────────────────────────────────────────
    draw.line([MARGIN + 8, y, W - MARGIN - 8, y], fill=DIVIDER, width=1)
    y += 12

    # ── DO section ─────────────────────────────────────────────────
    draw.text((MARGIN + 4, y), "THIS WEEK", fill=DO_ICON, font=font_section)
    y += 26

    for action in do_actions:
        draw_rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 28], fill=DO_BG, radius=6, outline=DO_BORDER)
        draw_checkbox(draw, MARGIN + 8, y + 5, checked=True, color=DO_ICON)
        display = action if len(action) <= 50 else action[:47] + "..."
        draw.text((MARGIN + 34, y + 5), display, fill=BODY_TEXT, font=font_body)
        y += 34

    y += 12

    # ── DON'T section ──────────────────────────────────────────────
    draw.text((MARGIN + 4, y), "AVOID THIS WEEK", fill=DONT_ICON, font=font_section)
    y += 26

    for action in dont_actions:
        draw_rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 28], fill=DONT_BG, radius=6, outline=DONT_BORDER)
        draw_checkbox(draw, MARGIN + 8, y + 5, checked=False, color=DONT_ICON)
        display = action if len(action) <= 50 else action[:47] + "..."
        draw.text((MARGIN + 34, y + 5), display, fill=BODY_TEXT, font=font_body)
        y += 34

    y += 12

    # ── Divider ────────────────────────────────────────────────────
    draw.line([MARGIN + 8, y, W - MARGIN - 8, y], fill=DIVIDER, width=1)
    y += 12

    # ── Best days ──────────────────────────────────────────────────
    if best_spray_day:
        draw_rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 26], fill=BEST_DAY_BG, radius=6, outline=BEST_DAY_BORDER)
        draw.text((MARGIN + 10, y + 4), f"Spray day:  {best_spray_day}", fill="#166534", font=font_body_bold)
    else:
        draw.text((MARGIN + 10, y + 4), "Spray:  No window this week", fill=MUTED_TEXT, font=font_body)
    y += 32

    if best_harvest_day:
        draw_rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 26], fill=BEST_DAY_BG, radius=6, outline=BEST_DAY_BORDER)
        draw.text((MARGIN + 10, y + 4), f"Harvest day:  {best_harvest_day}", fill="#166534", font=font_body_bold)
    else:
        draw.text((MARGIN + 10, y + 4), "Harvest:  No window — wait for dry", fill=MUTED_TEXT, font=font_body)
    y += 32

    # ── Risk alerts ────────────────────────────────────────────────
    for alert in risk_alerts:
        draw_rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 28], fill=WARN_BG, radius=6, outline=WARN_BORDER)
        # Warning triangle (drawn)
        tx, ty = MARGIN + 12, y + 6
        draw.polygon([(tx + 7, ty), (tx, ty + 14), (tx + 14, ty + 14)], fill="#F59E0B")
        draw.text((tx + 4, ty + 2), "!", fill="#FFFFFF", font=get_font(10, bold=True))
        draw.text((MARGIN + 34, y + 5), alert, fill=WARN_TEXT, font=font_body)
        y += 34

    # ── Save ───────────────────────────────────────────────────────
    img.save(output_path, "PNG", quality=95)
    print(f"Card saved: {output_path} ({W}x{H})")
    return output_path


# ── Demo with the real forecast data ──────────────────────────────────
def main():
    forecast_days = [
        {"day_short": "Wed", "rain_mm": 1.6, "temp_range": "12–20"},
        {"day_short": "Thu", "rain_mm": 9.4, "temp_range": "12–20"},
        {"day_short": "Fri", "rain_mm": 8.4, "temp_range": "12–19"},
        {"day_short": "Sat", "rain_mm": 2.0, "temp_range": "11–20"},
        {"day_short": "Sun", "rain_mm": 3.5, "temp_range": "12–20"},
        {"day_short": "Mon", "rain_mm": 6.8, "temp_range": "13–20"},
    ]

    do_actions = [
        "Clear drainage channels (TODAY)",
        "Apply Ridomil around tree bases",
        "Check fruit fly traps — replace old lures",
        "Collect and destroy fallen fruit daily",
    ]

    dont_actions = [
        "No copper spray — rain all week",
        "No harvesting — wait for dry morning",
        "No overhead irrigation — soil saturated",
    ]

    risk_alerts = [
        "Root rot risk: HIGH (soil wet 6+ days)",
        "Anthracnose risk: HIGH (long rains)",
    ]

    out = generate_advisory_card(
        location="Kariara, Gatanga, Murang'a",
        date_range="25–30 Mar 2026",
        variety_stage="🥑 Fuerte: Harvest  •  Hass: Fruit growing",
        forecast_days=forecast_days,
        do_actions=do_actions,
        dont_actions=dont_actions,
        best_spray_day=None,
        best_harvest_day=None,
        risk_alerts=risk_alerts,
        output_path=str(Path(__file__).parent / "advisory_card.png"),
    )


if __name__ == "__main__":
    main()
