#!/usr/bin/env python3
"""
OTP Evidence Demo Video Generator

Creates a ~2 minute demo video of the OTP pipeline and evidence viewer.
Uses PIL for frame rendering and FFmpeg for encoding.

Usage:
    py tools/make_otp_video.py
    py tools/make_otp_video.py -o otp_demo.mp4
"""

import argparse
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(1)


# ============================================================
# CONFIG
# ============================================================

WIDTH, HEIGHT = 1280, 720
FPS = 15
BG_COLOR = (236, 233, 216)  # XP gray #ECE9D8
TITLE_BG = (10, 36, 106)    # XP blue #0A246A
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (212, 208, 200)
GREEN = (0, 128, 0)
RED = (204, 0, 0)
BLUE = (0, 102, 204)
ORANGE = (255, 165, 0)
YELLOW_BG = (255, 250, 205)


def get_font(size, bold=False):
    """Get a font, falling back gracefully."""
    candidates = [
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(draw, text, font):
    """Get text size (works across PIL versions)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_xp_window(draw, title, x, y, w, h):
    """Draw a Windows XP style window."""
    # Shadow
    draw.rectangle([x + 3, y + 3, x + w + 3, y + h + 3], fill=(128, 128, 128))
    # Window body
    draw.rectangle([x, y, x + w, y + h], fill=BG_COLOR, outline=LIGHT_GRAY)
    # Title bar gradient (simplified)
    draw.rectangle([x, y, x + w, y + 24], fill=TITLE_BG)
    # Title text
    font = get_font(11, bold=True)
    draw.text((x + 8, y + 5), title, fill=WHITE, font=font)
    # Close button
    draw.rectangle([x + w - 20, y + 2, x + w - 4, y + 18], fill=(192, 57, 43))
    draw.text((x + w - 17, y + 3), "X", fill=WHITE, font=get_font(9, bold=True))
    # Border
    draw.rectangle([x, y, x + w, y + h], outline=LIGHT_GRAY, width=2)


def draw_field(draw, x, y, label, value, font_label, font_value, max_width=500):
    """Draw a label: value field pair."""
    draw.text((x, y), label, fill=BLUE, font=font_label)
    lw, _ = text_size(draw, label, font_label)
    # Truncate value if too long
    val_str = str(value)
    vw, _ = text_size(draw, val_str, font_value)
    while vw > max_width - lw and len(val_str) > 10:
        val_str = val_str[:-4] + "..."
        vw, _ = text_size(draw, val_str, font_value)
    draw.text((x + lw + 8, y), val_str, fill=BLACK, font=font_value)


def draw_badge(draw, x, y, text, bg_color, font):
    """Draw a colored badge."""
    tw, th = text_size(draw, text, font)
    padding = 6
    draw.rectangle([x, y, x + tw + padding * 2, y + th + padding], fill=bg_color)
    draw.rectangle([x, y, x + tw + padding * 2, y + th + padding], outline=DARK_GRAY)
    draw.text((x + padding, y + padding // 2), text, fill=WHITE if bg_color != ORANGE else BLACK, font=font)


# ============================================================
# SCENES
# ============================================================

def scene_title(duration=8.0):
    """Title card."""
    frames = []
    n_frames = int(duration * FPS)
    font_big = get_font(36, bold=True)
    font_sub = get_font(18)
    font_small = get_font(12)

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), (10, 36, 106))
        draw = ImageDraw.Draw(img)

        # Animated fade-in
        alpha = min(1.0, i / (FPS * 0.5))

        # Title
        title = "OTP Evidence Viewer"
        tw, th = text_size(draw, title, font_big)
        draw.text(((WIDTH - tw) // 2, HEIGHT // 2 - 60), title, fill=WHITE, font=font_big)

        # Subtitle
        sub = "Windows XP Edition"
        sw, sh = text_size(draw, sub, font_sub)
        draw.text(((WIDTH - sw) // 2, HEIGHT // 2 - 10), sub, fill=(180, 200, 255), font=font_sub)

        # Version
        ver = "v0.1.0 — C89 Portable + Python"
        vw, vh = text_size(draw, ver, font_small)
        draw.text(((WIDTH - vw) // 2, HEIGHT // 2 + 30), ver, fill=(120, 140, 180), font=font_small)

        # Decorative line
        draw.line([(WIDTH // 2 - 200, HEIGHT // 2 + 60), (WIDTH // 2 + 200, HEIGHT // 2 + 60)],
                  fill=(60, 100, 180), width=2)

        frames.append(img)

    return frames


def scene_pipeline(duration=24.0):
    """Pipeline flow visualization."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(20, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(10)

    steps = [
        ("EVENT", "roadstar.normalize()", GREEN),
        ("LEASE", "make_ack_lease()", BLUE),
        ("FINDING", "AckLeasePolicy.evaluate()", ORANGE),
        ("SENTINEL", "sentinel.deny_by_default()", RED),
        ("ACTION", "request_for()", BLUE),
        ("RECEIPT", "make_receipt() SHA-256", GREEN),
    ]

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([0, 0, WIDTH, 32], fill=TITLE_BG)
        draw.text((8, 8), "OTP Pipeline — Core Flow", fill=WHITE, font=font_title)

        # Pipeline boxes
        box_w = 180
        box_h = 60
        start_x = (WIDTH - (len(steps) * (box_w + 20) - 20)) // 2
        y = 120

        for j, (name, desc, color) in enumerate(steps):
            x = start_x + j * (box_w + 20)

            # Calculate if this step is "active" based on time
            step_time = (i / FPS) * (len(steps) / duration)
            is_active = j <= step_time
            is_current = abs(j - step_time) < 0.5

            if is_active:
                # Active box
                draw.rectangle([x, y, x + box_w, y + box_h], fill=color, outline=DARK_GRAY)
                draw.rectangle([x + 2, y + 2, x + box_w - 2, y + box_h - 2], outline=WHITE, width=1)
                text_color = WHITE
            else:
                # Inactive box
                draw.rectangle([x, y, x + box_w, y + box_h], fill=LIGHT_GRAY, outline=DARK_GRAY)
                text_color = DARK_GRAY

            # Step name
            nw, nh = text_size(draw, name, font_label)
            draw.text((x + (box_w - nw) // 2, y + 10), name, fill=text_color, font=font_label)

            # Description
            dw, dh = text_size(draw, desc, font_small)
            draw.text((x + (box_w - dw) // 2, y + 32), desc, fill=text_color, font=font_small)

            # Arrow between boxes
            if j < len(steps) - 1:
                arrow_x = x + box_w + 5
                arrow_y = y + box_h // 2
                draw.text((arrow_x, arrow_y - 6), "→", fill=DARK_GRAY, font=font_label)

        # Evidence box at bottom
        ev_y = 240
        draw_xp_window(draw, "Evidence Receipt", 100, ev_y, WIDTH - 200, 300)

        # Receipt fields (appear as pipeline progresses)
        field_y = ev_y + 32
        field_x = 120
        line_h = 22

        receipt_fields = [
            ("execution_id:", "exec_demo_001"),
            ("source_adapter:", "roadstar-workbook-v0"),
            ("policy_version:", "ack-lease-v0"),
            ("verdict:", "ACTION_REQUESTED"),
            ("finding.status:", "FAIL"),
            ("finding.reason_code:", "ACK_LEASE_EXPIRED"),
            ("finding.severity:", "HIGH"),
            ("receipt_sha256:", "f906a49be99b853da3e7..."),
        ]

        visible_fields = min(len(receipt_fields), int((i / FPS) * (len(receipt_fields) / duration) + 1))

        for k in range(visible_fields):
            label, value = receipt_fields[k]
            fy = field_y + k * line_h
            draw_field(draw, field_x, fy, label, value, font_label, font_value, max_width=800)

        # Status bar
        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], fill=LIGHT_GRAY)
        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], outline=DARK_GRAY, width=1)
        draw.text((8, HEIGHT - 20), f"Scene: Pipeline Flow  |  Frame: {i}/{n_frames}  |  Time: {i/FPS:.1f}s",
                  fill=DARK_GRAY, font=font_small)

        frames.append(img)

    return frames


def scene_viewer(duration=36.0):
    """Show the HTML viewer."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(20, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(10)
    font_code = get_font(10)

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([0, 0, WIDTH, 32], fill=TITLE_BG)
        draw.text((8, 8), "OTP Evidence Viewer — Windows XP Edition", fill=WHITE, font=font_title)

        # Main window
        draw_xp_window(draw, "OTP Evidence Viewer — exec_demo_001", 20, 44, WIDTH - 40, HEIGHT - 68)

        # Tabs
        tab_y = 68
        tabs = ["Overview", "Event", "Finding", "Action", "Components", "Raw JSON"]
        tab_x = 30
        for j, tab in enumerate(tabs):
            tw, th = text_size(draw, tab, font_value)
            is_active = j == 0
            bg = BG_COLOR if is_active else LIGHT_GRAY
            draw.rectangle([tab_x, tab_y, tab_x + tw + 16, tab_y + 20], fill=bg, outline=DARK_GRAY)
            if is_active:
                draw.rectangle([tab_x, tab_y + 18, tab_x + tw + 16, tab_y + 20], fill=BG_COLOR)
            draw.text((tab_x + 8, tab_y + 3), tab, fill=BLACK, font=font_value)
            tab_x += tw + 20

        # Content area
        content_y = 92
        content_x = 40

        # Group box: Execution
        draw.rectangle([content_x, content_y, WIDTH - 60, content_y + 140], outline=DARK_GRAY)
        draw.text((content_x + 8, content_y - 6), "Execution", fill=BLACK, font=font_label)

        fields = [
            ("Execution ID:", "exec_demo_001"),
            ("Source Adapter:", "roadstar-workbook-v0"),
            ("Policy Version:", "ack-lease-v0"),
            ("Channel Adapter:", "mock"),
        ]
        for k, (label, value) in enumerate(fields):
            draw_field(draw, content_x + 12, content_y + 12 + k * 22, label, value, font_label, font_value)

        # Verdict badge
        vy = content_y + 100
        draw.text((content_x + 12, vy), "Verdict:", fill=BLACK, font=font_label)
        draw_badge(draw, content_x + 100, vy - 2, "ACTION_REQUESTED", RED, font_label)

        # Finding box
        fy = content_y + 152
        draw.rectangle([content_x, fy, WIDTH - 60, fy + 120], outline=DARK_GRAY)
        draw.text((content_x + 8, fy - 6), "Finding", fill=BLACK, font=font_label)

        finding_fields = [
            ("Status:", "FAIL"),
            ("Reason Code:", "ACK_LEASE_EXPIRED"),
            ("Severity:", "HIGH"),
            ("Action Recommended:", "Yes"),
        ]
        for k, (label, value) in enumerate(finding_fields):
            color = RED if value in ("FAIL", "HIGH") else BLACK
            draw.text((content_x + 12, fy + 12 + k * 22), label, fill=BLUE, font=font_label)
            lw, _ = text_size(draw, label, font_label)
            draw.text((content_x + 12 + lw + 8, fy + 12 + k * 22), value, fill=color, font=font_value)

        # Verification section
        vy2 = fy + 132
        draw.rectangle([content_x, vy2, WIDTH - 60, vy2 + 80], outline=DARK_GRAY)
        draw.text((content_x + 8, vy2 - 6), "Receipt Integrity", fill=BLACK, font=font_label)
        draw.text((content_x + 12, vy2 + 12), "Receipt SHA-256:", fill=BLUE, font=font_label)
        draw.text((content_x + 12, vy2 + 32), "f906a49be99b853da3e72e62fa4d3514e3b568b2d878cbcf88628a1a421130c1",
                  fill=DARK_GRAY, font=font_code)

        # Verify button
        btn_y = vy2 + 52
        draw.rectangle([content_x + 12, btn_y, content_x + 160, btn_y + 22], fill=LIGHT_GRAY, outline=DARK_GRAY)
        draw.text((content_x + 20, btn_y + 4), "Verify Integrity", fill=BLACK, font=font_value)

        # Show verification result after midpoint
        if i > n_frames * 0.6:
            vr_y = btn_y + 30
            draw.rectangle([content_x + 12, vr_y, content_x + 500, vr_y + 30], fill=(144, 238, 144), outline=GREEN)
            draw.text((content_x + 20, vr_y + 6), "RECEIPT VALID — All 5 component hashes verified", fill=GREEN, font=font_label)

        # Status bar
        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], fill=LIGHT_GRAY)
        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], outline=DARK_GRAY, width=1)
        status = "VALID — All hashes match" if i > n_frames * 0.6 else "Ready"
        draw.text((8, HEIGHT - 20), f"Schema: evidence-receipt/1  |  Components: 5  |  {status}",
                  fill=DARK_GRAY, font=font_small)

        frames.append(img)

    return frames


def scene_domain_parity(duration=30.0):
    """Domain parity: Python == C."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(20, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(10)
    font_code = get_font(11)

    claims = [
        ("payload_sha256", "63c24184584fbad5ce03de8bac3468e9..."),
        ("finding.status", "PASS"),
        ("finding.reason_code", "ACK_LEASE_OPEN"),
        ("finding.action_recommended", "false"),
        ("sentinel.verdict", "NO_ACTION"),
    ]

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([0, 0, WIDTH, 32], fill=TITLE_BG)
        draw.text((8, 8), "Domain Parity — Python == C", fill=WHITE, font=font_title)

        # Two columns
        col_w = (WIDTH - 60) // 2

        # Python column
        draw_xp_window(draw, "Python (Reference)", 20, 50, col_w, 400)
        draw.text((36, 82), "otp.pipeline.evaluate_ack()", fill=DARK_GRAY, font=font_small)
        draw.text((36, 100), "otp.evidence.make_receipt()", fill=DARK_GRAY, font=font_small)

        # C column
        draw_xp_window(draw, "C89 (Portable)", 20 + col_w + 20, 50, col_w, 400)
        draw.text((36 + col_w + 20, 82), "./otp verify fixture.json", fill=DARK_GRAY, font=font_small)
        draw.text((36 + col_w + 20, 100), "otp_portable.c", fill=DARK_GRAY, font=font_small)

        # Claims table
        table_y = 130
        row_h = 36

        for k, (field, value) in enumerate(claims):
            ry = table_y + k * row_h

            # Animate checkmarks
            check_time = (i / FPS) * (len(claims) / duration)
            is_checked = k < check_time

            # Python value
            px = 36
            draw.text((px, ry), field, fill=BLUE, font=font_label)
            draw.text((px, ry + 16), value, fill=DARK_GRAY, font=font_code)

            # C value (same)
            cx = 36 + col_w + 20
            draw.text((cx, ry), field, fill=BLUE, font=font_label)
            draw.text((cx, ry + 16), value, fill=DARK_GRAY, font=font_code)

            # Match indicator
            if is_checked:
                match_x = 36 + col_w - 30
                draw.text((match_x, ry + 2), "✓", fill=GREEN, font=font_label)

        # Final verdict
        if i > n_frames * 0.7:
            vy = table_y + len(claims) * row_h + 20
            draw.rectangle([WIDTH // 2 - 120, vy, WIDTH // 2 + 120, vy + 40], fill=GREEN, outline=DARK_GRAY)
            draw.text((WIDTH // 2 - 80, vy + 10), "DOMAIN PARITY = PASS", fill=WHITE, font=font_title)

        # Status bar
        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], fill=LIGHT_GRAY)
        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], outline=DARK_GRAY, width=1)
        draw.text((8, HEIGHT - 20), f"Scene: Domain Parity  |  Claims verified: {min(len(claims), int((i/FPS)*(len(claims)/duration)+1))}/{len(claims)}",
                  fill=DARK_GRAY, font=font_small)

        frames.append(img)

    return frames


def scene_summary(duration=22.0):
    """Summary card."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(24, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(11)

    features = [
        ("C89 Portable", "cc otp_portable.c -o otp"),
        ("Domain Parity", "Python == C semantics"),
        ("Evidence Viewer", "Windows XP aesthetic, offline HTML"),
        ("SHA-256 Verification", "Web Crypto API, browser-side"),
        ("156 Tests", "persistence + parity + RoadStar surface"),
    ]

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), (10, 36, 106))
        draw = ImageDraw.Draw(img)

        # Title
        title = "OTP — Operational Trust Pipeline"
        tw, th = text_size(draw, title, font_title)
        draw.text(((WIDTH - tw) // 2, 60), title, fill=WHITE, font=font_title)

        # Subtitle
        sub = "FEATURES MAY DEGRADE. SEMANTICS MUST NOT."
        sw, sh = text_size(draw, sub, font_label)
        draw.text(((WIDTH - sw) // 2, 100), sub, fill=(180, 200, 255), font=font_label)

        # Feature list
        fy = 160
        for k, (name, desc) in enumerate(features):
            # Animate appearance
            appear_time = (i / FPS) * (len(features) / duration)
            if k > appear_time:
                continue

            draw.rectangle([WIDTH // 2 - 250, fy, WIDTH // 2 + 250, fy + 44], fill=(20, 50, 120), outline=(60, 100, 180))
            draw.text((WIDTH // 2 - 230, fy + 4), "✓ " + name, fill=GREEN, font=font_label)
            draw.text((WIDTH // 2 - 230, fy + 24), desc, fill=(180, 200, 255), font=font_small)
            fy += 54

        # URLs
        uy = fy + 30
        draw.text((WIDTH // 2 - 200, uy), "github.com/DannyBaanks/Operational-Trust-Pipeline",
                  fill=(120, 140, 180), font=font_small)

        frames.append(img)

    return frames


def scene_dock_collision(duration=36.0):
    """RoadStar Dock/HOS Collision timeline."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(20, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(10)

    samples = [
        ("08:00", "Milton terminal", 82, 0, 8.0, None),
        ("08:20", "En route 401", 78, 0, 7.7, None),
        ("08:40", "401 SLOWDOWN", 22, 0, 7.4, "401_SLOWDOWN"),
        ("09:00", "401 SLOWDOWN", 18, 0, 7.1, "401_SLOWDOWN"),
        ("09:20", "Near London", 62, 0, 6.8, None),
        ("09:30", "Approaching dock", 12, 0, 6.6, None),
        ("09:40", "GEOFENCE ENTER", 0, 0, 2.4, "DOCK_ARRIVAL"),
        ("10:40", "Dock wait 60m", 0, 60, 1.4, "DOCK_WAIT"),
        ("11:40", "DETENTION >2h", 0, 120, 0.4, "DETENTION_THRESHOLD"),
        ("12:00", "HOS COLLISION", 0, 140, 0.0, "HOS_COLLISION"),
        ("12:10", "DEPARTED", 15, 140, 0.0, "DOCK_DEPARTURE"),
    ]

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, WIDTH, 32], fill=TITLE_BG)
        draw.text((8, 8), "RoadStar — Dock/HOS Collision", fill=WHITE, font=font_title)

        progress = min(len(samples) - 1, int((i / n_frames) * len(samples)))
        # Timeline
        y = 120
        x0, x1 = 80, WIDTH - 80
        draw.line([(x0, y), (x1, y)], fill=DARK_GRAY, width=3)
        for k, (t, label, speed, dock, hos, ev) in enumerate(samples):
            x = x0 + (x1 - x0) * k / (len(samples) - 1)
            color = LIGHT_GRAY
            if k <= progress:
                color = RED if ev in ("HOS_COLLISION", "DETENTION_THRESHOLD") else (
                    ORANGE if ev in ("401_SLOWDOWN", "DOCK_WAIT") else GREEN)
            draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=color, outline=DARK_GRAY)
            if k == progress:
                draw.text((x - 20, y + 14), t, fill=BLACK, font=font_small)

        # Current sample detail
        t, label, speed, dock, hos, ev = samples[progress]
        draw_xp_window(draw, "Telemetry — " + t, 100, 200, WIDTH - 200, 300)
        rows = [
            ("Position:", label),
            ("Speed:", f"{speed} km/h"),
            ("Dock wait:", f"{dock} min"),
            ("On-duty remaining:", f"{hos:.1f} h"),
            ("Scenario:", ev or "EN ROUTE"),
        ]
        for k, (name, val) in enumerate(rows):
            fy = 240 + k * 30
            draw.text((130, fy), name, fill=BLUE, font=font_label)
            c = RED if (name == "Scenario:" and ev in ("HOS_COLLISION", "DETENTION_THRESHOLD")) else BLACK
            draw.text((330, fy), val, fill=c, font=font_value)

        if progress >= 9:
            draw.rectangle([WIDTH // 2 - 220, 420, WIDTH // 2 + 220, 460], fill=RED)
            draw.text((WIDTH // 2 - 200, 430), "HOS EXHAUSTED IN DOCK QUEUE", fill=WHITE, font=font_label)

        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], fill=LIGHT_GRAY)
        draw.text((8, HEIGHT - 20), f"Scene: Dock/HOS Collision | Sample {progress + 1}/{len(samples)}",
                  fill=DARK_GRAY, font=font_small)
        frames.append(img)
    return frames


def scene_geofence_detention(duration=32.0):
    """Geofence timestamps and detention billing."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(20, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(10)
    font_code = get_font(11)

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, WIDTH, 32], fill=TITLE_BG)
        draw.text((8, 8), "Geofence + Detention Billing (>2h free)", fill=WHITE, font=font_title)

        draw_xp_window(draw, "London DC — Visit", 100, 60, WIDTH - 200, 220)
        fields = [
            ("ENTERED:", "2026-09-12T09:40:00Z"),
            ("DEPARTED:", "2026-09-12T12:10:00Z"),
            ("Dock wait:", "150 min"),
            ("Free allowance:", "120 min"),
        ]
        for k, (name, val) in enumerate(fields):
            fy = 95 + k * 30
            draw.text((130, fy), name, fill=BLUE, font=font_label)
            draw.text((330, fy), val, fill=BLACK, font=font_value)

        # Animated wait bar
        wait = min(150, int((i / n_frames) * 160))
        billable = max(0, wait - 120)
        bx, by, bw, bh = 130, 320, WIDTH - 260, 28
        draw.rectangle([bx, by, bx + bw, by + bh], fill=WHITE, outline=DARK_GRAY)
        free_w = bw * min(wait, 120) / 150
        bill_w = bw * billable / 150
        draw.rectangle([bx, by, bx + free_w, by + bh], fill=GREEN)
        draw.rectangle([bx + free_w, by, bx + free_w + bill_w, by + bh], fill=RED)
        draw.text((bx, by + 34), f"wait {wait} min — free 120 min — billable {billable} min",
                  fill=BLACK, font=font_value)

        if billable > 0:
            charge = round(billable / 60 * 75.0, 2)
            draw.rectangle([WIDTH // 2 - 160, 400, WIDTH // 2 + 160, 444], fill=(255, 250, 205), outline=DARK_GRAY)
            draw.text((WIDTH // 2 - 140, 412), f"DETENTION: {billable} min = ${charge:.2f} CAD",
                      fill=BLACK, font=font_label)

        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], fill=LIGHT_GRAY)
        draw.text((8, HEIGHT - 20), "Scene: Geofence/Detention | 2h free, excess billed",
                  fill=DARK_GRAY, font=font_small)
        frames.append(img)
    return frames


def scene_load_match(duration=28.0):
    """Return-load ranking for the London truck."""
    frames = []
    n_frames = int(duration * FPS)
    font_title = get_font(20, bold=True)
    font_label = get_font(14, bold=True)
    font_value = get_font(12)
    font_small = get_font(10)

    candidates = [
        ("409385-AA", "MILTON → KITCHENER", "31,400 lbs", "deadhead 99 km", True),
        ("409339-AA", "WHITBY → KITCHENER", "35,983 lbs", "deadhead 208 km", True),
        ("409090", "LONDON → LONDON", "24,894 lbs", "deadhead 0 km", True),
    ]

    for i in range(n_frames):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, WIDTH, 32], fill=TITLE_BG)
        draw.text((8, 8), "Load Matching — Deadhead Reduction", fill=WHITE, font=font_title)
        draw.text((8, 40), "Truck in LONDON after delivery · dry van · 45,000 lbs · 8.0 h HOS",
                  fill=DARK_GRAY, font=font_value)

        y = 90
        visible = min(len(candidates), int((i / n_frames) * (len(candidates) + 1)))
        for k in range(visible):
            bid, route, weight, reason, ok = candidates[k]
            draw.rectangle([60, y, WIDTH - 60, y + 90], fill=WHITE, outline=DARK_GRAY)
            draw.text((80, y + 8), f"#{k + 1}  {bid}", fill=BLUE, font=font_label)
            draw.text((80, y + 32), route, fill=BLACK, font=font_value)
            draw.text((80, y + 54), f"{weight} · {reason}", fill=DARK_GRAY, font=font_small)
            draw_badge(draw, WIDTH - 180, y + 8, "MATCH", GREEN, font_small)
            y += 104

        draw.rectangle([0, HEIGHT - 24, WIDTH, HEIGHT], fill=LIGHT_GRAY)
        draw.text((8, HEIGHT - 20), "Scene: Load Match | dispatcher decides, OTP never auto-assigns",
                  fill=DARK_GRAY, font=font_small)
        frames.append(img)
    return frames


# ============================================================
# RENDER
# ============================================================

def render_video(frames, output_path, fps=FPS):
    """Render frames to MP4 using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "medium",
        "-movflags", "+faststart",
        str(output_path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for i, frame in enumerate(frames):
        proc.stdin.write(frame.tobytes())
        if i % fps == 0:
            print(f"\r  Rendering: {i}/{len(frames)} frames ({i/len(frames)*100:.0f}%)", end="", flush=True)
    proc.stdin.close()
    _, stderr = proc.communicate()
    print(f"\r  Rendering: {len(frames)}/{len(frames)} frames (100%)")
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="Generate OTP demo video")
    parser.add_argument("-o", "--output", default="otp_demo.mp4", help="Output MP4 path")
    parser.add_argument("--no-audio", action="store_true", help="Skip audio generation")
    args = parser.parse_args()

    output_path = Path(args.output)
    temp_dir = Path("build") / "otp_video"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("OTP Demo Video Generator")
    print("=" * 40)

    # Generate scenes
    print("\n[1/8] Generating title scene...")
    title_frames = scene_title(8.0)

    print("[2/8] Generating pipeline scene...")
    pipeline_frames = scene_pipeline(24.0)

    print("[3/8] Generating viewer scene...")
    viewer_frames = scene_viewer(28.0)

    print("[4/8] Generating Dock/HOS Collision scene...")
    collision_frames = scene_dock_collision(36.0)

    print("[5/8] Generating geofence/detention scene...")
    detention_frames = scene_geofence_detention(32.0)

    print("[6/8] Generating load-match scene...")
    match_frames = scene_load_match(28.0)

    print("[7/8] Generating domain parity scene...")
    parity_frames = scene_domain_parity(24.0)

    print("[8/8] Generating summary scene...")
    summary_frames = scene_summary(22.0)

    # Concatenate all frames
    all_frames = (title_frames + pipeline_frames + viewer_frames +
                  collision_frames + detention_frames + match_frames +
                  parity_frames + summary_frames)
    total_duration = len(all_frames) / FPS
    print(f"\nTotal: {len(all_frames)} frames, {total_duration:.1f}s")

    # Render
    print(f"\nRendering to {output_path}...")
    ret = render_video(all_frames, output_path)

    if ret == 0:
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"\nDone! {output_path} ({size_mb:.1f} MB)")
        print(f"Duration: {total_duration:.1f}s at {FPS}fps")
    else:
        print(f"\nERROR: FFmpeg exited with code {ret}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
