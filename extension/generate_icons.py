"""
SuperTroopers Chrome Extension Icon Generator
Concept: Terminal monitor with ASCII art state trooper in terminal green
"""

from PIL import Image, ImageDraw
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BG = (26, 26, 46, 255)          # #1a1a2e — dark navy
MONITOR_OUTLINE = (58, 58, 94, 255)   # #3a3a5e — lighter gray-blue
SCREEN_BG = (22, 33, 62, 255)   # #16213e — screen fill
GREEN = (0, 255, 65, 255)        # #00FF41 — terminal green
GREEN_DIM = (0, 180, 45, 200)    # dimmed green for details
TRANSPARENT = (0, 0, 0, 0)


def draw_monitor_128(draw, size=128):
    """Full detail 128x128 monitor with stand"""
    w, h = size, size
    # Monitor outer frame
    mx, my = 8, 6
    mw, mh = w - 16, h - 22
    r = 8
    draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=r, fill=MONITOR_OUTLINE)
    # Screen bezel (inner)
    bx, by = mx + 5, my + 5
    bw, bh = mw - 10, mh - 10
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=4, fill=SCREEN_BG)
    # Stand neck
    neck_x = w // 2 - 4
    neck_y = my + mh
    draw.rectangle([neck_x, neck_y, neck_x + 8, neck_y + 6], fill=MONITOR_OUTLINE)
    # Stand base
    base_x = w // 2 - 14
    base_y = neck_y + 6
    draw.rectangle([base_x, base_y, base_x + 28, base_y + 4], fill=MONITOR_OUTLINE)
    return (bx + 2, by + 2, bx + bw - 2, by + bh - 2)  # usable screen area


def draw_trooper_128(draw, screen):
    """Full detail trooper figure for 128px"""
    sx, sy, ex, ey = screen
    sw = ex - sx
    sh = ey - sy
    cx = sx + sw // 2

    # --- Campaign hat (flat brim trooper hat) ---
    # Brim (wide flat rectangle)
    brim_y = sy + int(sh * 0.06)
    brim_h = int(sh * 0.05)
    brim_w = int(sw * 0.72)
    brim_x = cx - brim_w // 2
    draw.rectangle([brim_x, brim_y, brim_x + brim_w, brim_y + brim_h], fill=GREEN)
    # Crown of hat
    crown_w = int(sw * 0.44)
    crown_h = int(sh * 0.12)
    crown_x = cx - crown_w // 2
    crown_y = brim_y - crown_h
    draw.rounded_rectangle([crown_x, crown_y, crown_x + crown_w, crown_y + crown_h],
                            radius=3, fill=GREEN)
    # Hat band (darker line)
    band_y = brim_y - int(sh * 0.025)
    draw.rectangle([crown_x, band_y, crown_x + crown_w, band_y + int(sh * 0.025)],
                   fill=GREEN_DIM)

    # --- Head ---
    head_w = int(sw * 0.34)
    head_h = int(sh * 0.16)
    head_x = cx - head_w // 2
    head_y = brim_y + brim_h
    draw.rounded_rectangle([head_x, head_y, head_x + head_w, head_y + head_h],
                            radius=4, fill=GREEN)

    # --- Sunglasses (two rectangles with bridge) ---
    glass_y = head_y + int(head_h * 0.28)
    glass_h = int(head_h * 0.28)
    glass_w = int(head_w * 0.38)
    gap = int(head_w * 0.08)
    left_x = cx - gap // 2 - glass_w
    right_x = cx + gap // 2
    # Lens fill (dark)
    draw.rectangle([left_x, glass_y, left_x + glass_w, glass_y + glass_h],
                   fill=(0, 40, 10, 255))
    draw.rectangle([right_x, glass_y, right_x + glass_w, glass_y + glass_h],
                   fill=(0, 40, 10, 255))
    # Lens outline (green)
    draw.rectangle([left_x, glass_y, left_x + glass_w, glass_y + glass_h],
                   outline=GREEN, width=2)
    draw.rectangle([right_x, glass_y, right_x + glass_w, glass_y + glass_h],
                   outline=GREEN, width=2)
    # Bridge
    bridge_y = glass_y + glass_h // 2
    draw.line([left_x + glass_w, bridge_y, right_x, bridge_y], fill=GREEN, width=2)

    # --- Shoulders / uniform ---
    body_top = head_y + head_h
    body_w = int(sw * 0.56)
    body_h = int(sh * 0.28)
    body_x = cx - body_w // 2
    # Shoulders (trapezoid via polygon)
    shoulder_pts = [
        (cx - int(sw * 0.16), body_top),
        (cx + int(sw * 0.16), body_top),
        (cx + int(sw * 0.28), body_top + int(body_h * 0.35)),
        (body_x + body_w, body_top + body_h),
        (body_x, body_top + body_h),
        (cx - int(sw * 0.28), body_top + int(body_h * 0.35)),
    ]
    draw.polygon(shoulder_pts, fill=GREEN)

    # --- Badge (star outline on chest) ---
    badge_cx = cx
    badge_cy = body_top + int(body_h * 0.5)
    badge_r = int(sw * 0.07)
    # Simple star: 5 points
    import math
    star_pts = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = badge_r if i % 2 == 0 else badge_r * 0.45
        star_pts.append((badge_cx + r * math.cos(angle),
                          badge_cy - r * math.sin(angle)))
    draw.polygon(star_pts, fill=SCREEN_BG, outline=GREEN)

    # --- Collar line ---
    collar_y = body_top + int(body_h * 0.12)
    draw.line([cx - int(sw * 0.06), collar_y, cx, body_top + int(body_h * 0.25)],
              fill=SCREEN_BG, width=2)
    draw.line([cx + int(sw * 0.06), collar_y, cx, body_top + int(body_h * 0.25)],
              fill=SCREEN_BG, width=2)

    # --- Terminal cursor at bottom of screen ---
    cur_w = int(sw * 0.12)
    cur_h = int(sh * 0.025)
    cur_x = sx + int(sw * 0.08)
    cur_y = ey - int(sh * 0.06)
    draw.rectangle([cur_x, cur_y, cur_x + cur_w, cur_y + cur_h], fill=GREEN)


def draw_monitor_48(draw, size=48):
    """Simplified 48px monitor"""
    w, h = size, size
    mx, my = 3, 2
    mw, mh = w - 6, h - 9
    draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=4, fill=MONITOR_OUTLINE)
    bx, by = mx + 3, my + 3
    bw, bh = mw - 6, mh - 6
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=2, fill=SCREEN_BG)
    # Stand
    draw.rectangle([w // 2 - 2, my + mh, w // 2 + 2, my + mh + 3], fill=MONITOR_OUTLINE)
    draw.rectangle([w // 2 - 6, my + mh + 3, w // 2 + 6, my + mh + 5], fill=MONITOR_OUTLINE)
    return (bx + 1, by + 1, bx + bw - 1, by + bh - 1)


def draw_trooper_48(draw, screen):
    """48px trooper - hat, glasses, shoulders"""
    sx, sy, ex, ey = screen
    sw = ex - sx
    sh = ey - sy
    cx = sx + sw // 2

    # Hat brim
    brim_y = sy + int(sh * 0.05)
    draw.rectangle([sx + int(sw * 0.1), brim_y, ex - int(sw * 0.1), brim_y + 3], fill=GREEN)
    # Hat crown
    crown_x = cx - int(sw * 0.22)
    draw.rectangle([crown_x, brim_y - int(sh * 0.14), crown_x + int(sw * 0.44), brim_y],
                   fill=GREEN)

    # Head
    head_y = brim_y + 3
    head_h = int(sh * 0.20)
    draw.rounded_rectangle([cx - int(sw * 0.18), head_y,
                             cx + int(sw * 0.18), head_y + head_h], radius=2, fill=GREEN)

    # Sunglasses
    g_y = head_y + int(head_h * 0.25)
    g_h = max(3, int(head_h * 0.3))
    g_w = int(sw * 0.14)
    draw.rectangle([cx - g_w * 2 - 1, g_y, cx - 2, g_y + g_h], fill=(0, 40, 10, 255))
    draw.rectangle([cx - g_w * 2 - 1, g_y, cx - 2, g_y + g_h], outline=GREEN, width=1)
    draw.rectangle([cx + 2, g_y, cx + g_w * 2 + 1, g_y + g_h], fill=(0, 40, 10, 255))
    draw.rectangle([cx + 2, g_y, cx + g_w * 2 + 1, g_y + g_h], outline=GREEN, width=1)

    # Shoulders
    body_top = head_y + head_h
    draw.polygon([
        (cx - int(sw * 0.1), body_top),
        (cx + int(sw * 0.1), body_top),
        (cx + int(sw * 0.28), ey - int(sh * 0.12)),
        (cx - int(sw * 0.28), ey - int(sh * 0.12)),
    ], fill=GREEN)

    # Cursor
    draw.rectangle([sx + 2, ey - 4, sx + 6, ey - 2], fill=GREEN)


def draw_monitor_32(draw, size=32):
    """32px abstract monitor"""
    w, h = size, size
    mx, my = 2, 2
    mw, mh = w - 4, h - 7
    draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=3, fill=MONITOR_OUTLINE)
    bx, by = mx + 2, my + 2
    bw, bh = mw - 4, mh - 4
    draw.rectangle([bx, by, bx + bw, by + bh], fill=SCREEN_BG)
    draw.rectangle([w // 2 - 2, my + mh, w // 2 + 2, my + mh + 3], fill=MONITOR_OUTLINE)
    draw.rectangle([w // 2 - 5, my + mh + 3, w // 2 + 5, my + mh + 5], fill=MONITOR_OUTLINE)
    return (bx + 1, by + 1, bx + bw - 1, by + bh - 1)


def draw_trooper_32(draw, screen):
    """32px - hat silhouette + glasses + shoulders blob"""
    sx, sy, ex, ey = screen
    sw = ex - sx
    sh = ey - sy
    cx = sx + sw // 2

    # Hat brim (1px line)
    brim_y = sy + int(sh * 0.08)
    draw.rectangle([sx + 1, brim_y, ex - 1, brim_y + 2], fill=GREEN)
    # Crown
    draw.rectangle([cx - int(sw * 0.25), brim_y - int(sh * 0.16),
                    cx + int(sw * 0.25), brim_y], fill=GREEN)

    # Head blob
    head_y = brim_y + 2
    head_h = int(sh * 0.20)
    draw.rectangle([cx - int(sw * 0.2), head_y, cx + int(sw * 0.2), head_y + head_h],
                   fill=GREEN)

    # Glasses — just two dark dots
    g_y = head_y + int(head_h * 0.25)
    g_s = max(2, int(sw * 0.13))
    draw.rectangle([cx - g_s * 2, g_y, cx - 1, g_y + g_s], fill=(0, 80, 20, 255))
    draw.rectangle([cx + 1, g_y, cx + g_s * 2, g_y + g_s], fill=(0, 80, 20, 255))

    # Body/shoulders blob
    body_top = head_y + head_h
    draw.polygon([
        (cx - int(sw * 0.12), body_top),
        (cx + int(sw * 0.12), body_top),
        (cx + int(sw * 0.3), ey - 2),
        (cx - int(sw * 0.3), ey - 2),
    ], fill=GREEN)


def draw_icon_16(draw, size=16):
    """16px iconic — monitor with hat+glasses symbol"""
    w, h = size, size
    # Monitor frame
    draw.rounded_rectangle([1, 1, w - 2, h - 4], radius=2, fill=MONITOR_OUTLINE)
    # Screen
    draw.rectangle([3, 3, w - 4, h - 6], fill=SCREEN_BG)
    # Stand
    draw.rectangle([w // 2 - 1, h - 4, w // 2 + 1, h - 2], fill=MONITOR_OUTLINE)
    draw.rectangle([w // 2 - 3, h - 2, w // 2 + 3, h - 1], fill=MONITOR_OUTLINE)

    cx = w // 2
    # Mini hat (just a green bar at top of screen)
    draw.rectangle([4, 3, w - 5, 4], fill=GREEN)      # brim
    draw.rectangle([5, 2, w - 6, 3], fill=GREEN)       # crown hint
    # Mini glasses (two green pixels each side)
    draw.rectangle([4, 6, 6, 7], fill=GREEN)
    draw.rectangle([9, 6, 11, 7], fill=GREEN)
    # Body dot
    draw.rectangle([cx - 1, 9, cx + 1, 11], fill=GREEN)


def generate_icon(size):
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # Fill background
    draw.rectangle([0, 0, size - 1, size - 1], fill=BG)

    if size == 128:
        screen = draw_monitor_128(draw, size)
        draw_trooper_128(draw, screen)
    elif size == 48:
        screen = draw_monitor_48(draw, size)
        draw_trooper_48(draw, screen)
    elif size == 32:
        screen = draw_monitor_32(draw, size)
        draw_trooper_32(draw, screen)
    elif size == 16:
        draw_icon_16(draw, size)

    out_path = os.path.join(OUTPUT_DIR, f"icon-{size}.png")
    img.save(out_path, "PNG")
    print(f"Saved {out_path} ({size}x{size})")
    return out_path


if __name__ == "__main__":
    for s in [16, 32, 48, 128]:
        generate_icon(s)
    print("All icons generated.")
