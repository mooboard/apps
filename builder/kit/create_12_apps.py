#!/usr/bin/env python3
import os
import sys
import json
import io
import struct
import zlib
from PIL import Image, ImageDraw

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def clean_png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    keep = (b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND")
    out = raw[:8]
    pos = 8
    while pos < len(raw):
        l, k = struct.unpack(">I4s", raw[pos:pos+8])
        chunk = raw[pos:pos+12+l]
        if k in keep:
            out += chunk
        pos += 12 + l
    return out

# Icon generation functions (all return 32x32 Image)

def draw_split_flap():
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Background panel
    d.rounded_rectangle([2, 3, 29, 28], radius=3, fill=(28, 30, 36, 255), outline=(45, 48, 56, 255))
    # Top flap
    d.rectangle([4, 5, 27, 15], fill=(36, 39, 47, 255))
    # Bottom flap
    d.rectangle([4, 17, 27, 26], fill=(22, 24, 30, 255))
    # Split seam
    d.line([3, 16, 28, 16], fill=(10, 11, 14, 255), width=1)
    # Left & right mechanical hinges
    d.rectangle([2, 15, 4, 17], fill=(80, 85, 95, 255))
    d.rectangle([27, 15, 29, 17], fill=(80, 85, 95, 255))
    # Digits "0" and "7"
    # Left digit '0'
    d.rectangle([7, 8, 14, 23], outline=(255, 248, 230, 255), width=2)
    # Right digit '7'
    d.line([17, 8, 24, 8], fill=(255, 248, 230, 255), width=2)
    d.line([24, 8, 19, 23], fill=(255, 248, 230, 255), width=2)
    # Split line over digits
    d.line([3, 16, 28, 16], fill=(10, 11, 14, 255), width=1)
    return img

def draw_word_clock():
    img = Image.new("RGBA", (32, 32), (12, 16, 28, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=3, outline=(30, 41, 59, 255))
    # Lit words: IT IS (top row)
    # 'I' 'T'
    d.rectangle([4, 5, 5, 8], fill=(78, 236, 213, 255))
    d.rectangle([8, 5, 11, 6], fill=(78, 236, 213, 255))
    d.line([9, 7, 9, 8], fill=(78, 236, 213, 255))
    # 'I' 'S'
    d.rectangle([15, 5, 16, 8], fill=(78, 236, 213, 255))
    d.rectangle([19, 5, 22, 8], outline=(78, 236, 213, 255))
    # Unlit row (middle)
    d.rectangle([4, 12, 7, 15], fill=(30, 41, 59, 255))
    d.rectangle([10, 12, 13, 15], fill=(30, 41, 59, 255))
    d.rectangle([16, 12, 19, 15], fill=(30, 41, 59, 255))
    d.rectangle([22, 12, 25, 15], fill=(30, 41, 59, 255))
    # Lit word: TEN (row 3)
    # T
    d.line([5, 19, 9, 19], fill=(78, 236, 213, 255), width=1)
    d.line([7, 19, 7, 23], fill=(78, 236, 213, 255), width=1)
    # E
    d.line([12, 19, 16, 19], fill=(78, 236, 213, 255), width=1)
    d.line([12, 19, 12, 23], fill=(78, 236, 213, 255), width=1)
    d.line([12, 21, 15, 21], fill=(78, 236, 213, 255), width=1)
    d.line([12, 23, 16, 23], fill=(78, 236, 213, 255), width=1)
    # N
    d.line([19, 19, 19, 23], fill=(78, 236, 213, 255), width=1)
    d.line([19, 19, 23, 23], fill=(78, 236, 213, 255), width=1)
    d.line([23, 19, 23, 23], fill=(78, 236, 213, 255), width=1)
    # Minute dots along bottom
    d.point([5, 27], fill=(56, 189, 248, 255))
    d.point([11, 27], fill=(56, 189, 248, 255))
    d.point([17, 27], fill=(56, 189, 248, 255))
    d.point([23, 27], fill=(30, 41, 59, 255))
    return img

def draw_solar_arc():
    img = Image.new("RGBA", (32, 32), (18, 14, 38, 255))
    d = ImageDraw.Draw(img)
    # Sky gradient lines near horizon
    d.rectangle([0, 18, 31, 22], fill=(85, 30, 50, 255))
    d.rectangle([0, 23, 31, 26], fill=(210, 85, 30, 255))
    d.rectangle([0, 27, 31, 31], fill=(12, 15, 20, 255))
    # Golden arc
    d.arc([2, 5, 29, 32], start=190, end=350, fill=(251, 191, 36, 255), width=1)
    # Sun
    d.ellipse([7, 9, 15, 17], fill=(254, 240, 138, 255), outline=(245, 158, 11, 255))
    # Sun rays
    d.point([11, 6], fill=(254, 240, 138, 255))
    d.point([11, 20], fill=(254, 240, 138, 255))
    d.point([4, 13], fill=(254, 240, 138, 255))
    d.point([18, 13], fill=(254, 240, 138, 255))
    # Moon crescent on right
    d.ellipse([21, 8, 27, 14], fill=(224, 231, 255, 255))
    d.ellipse([20, 7, 25, 13], fill=(18, 14, 38, 255))
    return img

def draw_vfd_clock():
    img = Image.new("RGBA", (32, 32), (4, 18, 16, 255))
    d = ImageDraw.Draw(img)
    # Outer glass tube frame
    d.rounded_rectangle([2, 4, 29, 27], radius=4, outline=(15, 55, 45, 255), width=1)
    # Horizontal scanlines
    for y in range(6, 26, 2):
        d.line([3, y, 28, y], fill=(6, 26, 22, 255))
    # Glowing teal 7-segment digits: "8 : 4"
    c_teal = (38, 230, 164, 255)
    # Digit '8' on left
    d.rectangle([6, 9, 12, 22], outline=c_teal, width=1)
    d.line([6, 15, 12, 15], fill=c_teal, width=1)
    # Colon
    d.rectangle([15, 12, 16, 13], fill=c_teal)
    d.rectangle([15, 18, 16, 19], fill=c_teal)
    # Digit '4' on right
    d.line([20, 9, 20, 16], fill=c_teal, width=1)
    d.line([20, 16, 25, 16], fill=c_teal, width=1)
    d.line([24, 9, 24, 22], fill=c_teal, width=1)
    return img

def draw_git_pulse():
    img = Image.new("RGBA", (32, 32), (13, 17, 23, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=3, outline=(33, 38, 45, 255))
    # Git commit branch line at top
    d.line([4, 6, 27, 6], fill=(56, 139, 253, 255), width=1)
    d.ellipse([7, 4, 11, 8], fill=(56, 139, 253, 255), outline=(13, 17, 23, 255))
    d.ellipse([20, 4, 24, 8], fill=(56, 139, 253, 255), outline=(13, 17, 23, 255))
    # Heatmap grid 4 columns x 3 rows
    greens = [
        (22, 27, 34, 255),   # 0
        (14, 68, 41, 255),   # 1
        (0, 109, 50, 255),   # 2
        (38, 166, 65, 255),  # 3
        (57, 211, 83, 255),  # 4
    ]
    grid = [
        [greens[1], greens[3], greens[2], greens[4], greens[3]],
        [greens[0], greens[2], greens[4], greens[3], greens[4]],
        [greens[2], greens[4], greens[3], greens[1], greens[2]],
    ]
    for r, row in enumerate(grid):
        for c, color in enumerate(row):
            x = 4 + c * 5
            y = 12 + r * 5
            d.rectangle([x, y, x + 3, y + 3], fill=color)
    return img

def draw_next_up():
    img = Image.new("RGBA", (32, 32), (15, 23, 42, 255))
    d = ImageDraw.Draw(img)
    # Calendar card body
    d.rounded_rectangle([3, 4, 28, 27], radius=3, fill=(30, 41, 59, 255), outline=(51, 65, 85, 255))
    # Red header
    d.rounded_rectangle([3, 4, 28, 11], radius=2, fill=(239, 68, 68, 255))
    # Ring binder tabs
    d.rectangle([8, 2, 10, 5], fill=(148, 163, 184, 255))
    d.rectangle([21, 2, 23, 5], fill=(148, 163, 184, 255))
    # Clock circle in middle
    d.ellipse([7, 14, 18, 25], outline=(241, 245, 249, 255), width=1)
    d.line([12, 19, 12, 16], fill=(241, 245, 249, 255), width=1)
    d.line([12, 19, 15, 19], fill=(241, 245, 249, 255), width=1)
    # Amber countdown badge
    d.rounded_rectangle([19, 16, 27, 24], radius=2, fill=(245, 158, 11, 255))
    d.point([22, 19], fill=(255, 255, 255, 255))
    d.point([24, 21], fill=(255, 255, 255, 255))
    return img

def draw_flow_tide():
    img = Image.new("RGBA", (32, 32), (15, 23, 42, 255))
    d = ImageDraw.Draw(img)
    # Deep ocean left background
    d.rectangle([0, 0, 16, 31], fill=(2, 132, 199, 255))
    # Warm amber right background
    d.rectangle([16, 0, 31, 31], fill=(217, 119, 6, 255))
    # Flow tide wave dividing them
    wave_pts = [(0, 18), (8, 14), (16, 20), (24, 12), (31, 16), (31, 31), (0, 31)]
    d.polygon(wave_pts, fill=(14, 165, 233, 255))
    # Wave crest highlight
    d.line([(0, 18), (8, 14), (16, 20), (24, 12), (31, 16)], fill=(224, 242, 254, 255), width=1)
    # 4 focus session dots at top
    for i in range(4):
        x = 6 + i * 6
        color = (252, 211, 77, 255) if i < 3 else (71, 85, 105, 255)
        d.ellipse([x, 5, x + 3, 8], fill=color)
    return img

def draw_water_cow():
    img = Image.new("RGBA", (32, 32), (240, 249, 255, 255))
    d = ImageDraw.Draw(img)
    # Soft blue background border
    d.rounded_rectangle([1, 1, 30, 30], radius=4, fill=(224, 242, 254, 255), outline=(186, 230, 253, 255))
    # Cow ears & horns
    d.ellipse([4, 6, 9, 11], fill=(252, 211, 77, 255))   # Horn left
    d.ellipse([17, 6, 22, 11], fill=(252, 211, 77, 255)) # Horn right
    # Cow face
    d.rounded_rectangle([5, 8, 21, 24], radius=3, fill=(255, 255, 255, 255))
    # Black patch over right eye
    d.ellipse([12, 9, 20, 17], fill=(15, 23, 42, 255))
    # Eyes
    d.point([9, 13], fill=(15, 23, 42, 255))
    d.point([16, 13], fill=(255, 255, 255, 255))
    # Pink snout
    d.rounded_rectangle([7, 17, 19, 23], radius=2, fill=(244, 114, 182, 255))
    d.point([10, 20], fill=(190, 24, 93, 255))
    d.point([16, 20], fill=(190, 24, 93, 255))
    # Water droplet on right
    d.polygon([(26, 13), (23, 19), (29, 19)], fill=(56, 189, 248, 255))
    d.ellipse([23, 16, 29, 23], fill=(56, 189, 248, 255))
    d.point([25, 17], fill=(255, 255, 255, 255))
    # Hydration level bar at bottom
    d.rounded_rectangle([4, 26, 27, 29], radius=1, fill=(186, 230, 253, 255))
    d.rectangle([4, 26, 20, 29], fill=(2, 132, 199, 255))
    return img

def draw_air_glance():
    img = Image.new("RGBA", (32, 32), (12, 74, 110, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=3, outline=(3, 105, 161, 255))
    # Cloud silhouette
    d.ellipse([6, 9, 16, 19], fill=(240, 249, 255, 255))
    d.ellipse([14, 7, 24, 17], fill=(240, 249, 255, 255))
    d.ellipse([18, 11, 26, 19], fill=(240, 249, 255, 255))
    d.rectangle([10, 14, 22, 19], fill=(240, 249, 255, 255))
    # Breeze lines
    d.line([4, 22, 16, 22], fill=(56, 189, 248, 255), width=1)
    d.line([8, 25, 20, 25], fill=(56, 189, 248, 255), width=1)
    # Green AQI badge pill (Good air)
    d.rounded_rectangle([16, 19, 29, 28], radius=3, fill=(34, 197, 94, 255), outline=(240, 253, 244, 255))
    # AQI leaf/dot
    d.ellipse([19, 22, 23, 25], fill=(255, 255, 255, 255))
    d.point([25, 24], fill=(255, 255, 255, 255))
    return img

def draw_power_grid():
    img = Image.new("RGBA", (32, 32), (15, 23, 42, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=3, outline=(30, 41, 59, 255))
    # Yellow sun (solar) top-left
    d.ellipse([5, 5, 13, 13], fill=(250, 204, 21, 255))
    d.point([9, 3], fill=(250, 204, 21, 255))
    d.point([9, 15], fill=(250, 204, 21, 255))
    d.point([3, 9], fill=(250, 204, 21, 255))
    d.point([15, 9], fill=(250, 204, 21, 255))
    # Blue house roof bottom-right
    d.polygon([(24, 16), (17, 22), (31, 22)], fill=(56, 189, 248, 255))
    d.rectangle([19, 22, 29, 28], fill=(14, 165, 233, 255))
    # Window
    d.rectangle([22, 24, 26, 26], fill=(255, 255, 255, 255))
    # Central lightning bolt (energy flow)
    bolt = [(18, 6), (12, 15), (16, 15), (13, 23), (21, 13), (17, 13)]
    d.polygon(bolt, fill=(245, 158, 11, 255))
    return img

def draw_mailbox():
    img = Image.new("RGBA", (32, 32), (241, 245, 249, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=3, fill=(226, 232, 240, 255), outline=(203, 213, 225, 255))
    # Post post
    d.rectangle([14, 22, 17, 30], fill=(71, 85, 105, 255))
    # Mailbox body (slate gray)
    d.rounded_rectangle([6, 10, 23, 22], radius=4, fill=(51, 65, 85, 255))
    # Mailbox door seam
    d.ellipse([5, 10, 11, 22], fill=(30, 41, 59, 255))
    # Red postal flag UP
    d.line([18, 16, 18, 5], fill=(239, 68, 68, 255), width=2)
    d.rectangle([18, 5, 25, 9], fill=(239, 68, 68, 255))
    # Envelope popping out
    d.rectangle([10, 13, 17, 19], fill=(255, 255, 255, 255), outline=(148, 163, 184, 255))
    d.line([(10, 13), (13, 16), (17, 13)], fill=(203, 213, 225, 255), width=1)
    return img

def draw_flight_glance():
    img = Image.new("RGBA", (32, 32), (2, 21, 38, 255))
    d = ImageDraw.Draw(img)
    # Radar sweep rings
    d.ellipse([2, 2, 29, 29], outline=(10, 60, 40, 255), width=1)
    d.ellipse([8, 8, 23, 23], outline=(15, 80, 50, 255), width=1)
    d.ellipse([13, 13, 18, 18], outline=(20, 100, 60, 255), width=1)
    # Sweep line
    d.line([16, 16, 28, 6], fill=(34, 197, 94, 180), width=1)
    # Twin-engine passenger jet climbing at 45 degrees
    # Fuselage
    d.polygon([(10, 22), (22, 10), (24, 11), (12, 23)], fill=(255, 255, 255, 255))
    # Wings
    d.polygon([(13, 15), (10, 9), (13, 10), (17, 17)], fill=(241, 245, 249, 255))
    d.polygon([(16, 18), (19, 25), (20, 24), (18, 16)], fill=(241, 245, 249, 255))
    # Tail
    d.polygon([(9, 21), (7, 24), (10, 23)], fill=(255, 255, 255, 255))
    # Flight vector green dot
    d.point([25, 8], fill=(34, 197, 94, 255))
    return img

# Apps definition table
APPS = [
    {
        "category": "Clock",
        "folder": "Split-Flap Clock",
        "id": "split-flap",
        "name": "Split-Flap Clock",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Mechanical transit departure board clock with animated flipping digits.",
        "uses": "pong",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "speed",
                "type": "choice",
                "label": "Flip speed",
                "default": "Normal",
                "options": ["Slow", "Normal", "Fast"]
            },
            {
                "key": "colors",
                "type": "choice",
                "label": "Colorway",
                "default": "Classic",
                "options": ["Classic", "Amber"]
            }
        ],
        "readme": """# Split-Flap Clock

A mechanical transit departure board clock on your mooboard.

Digits flip smoothly on each minute change with classic railway split-flap styling.

## Settings

- Flip speed: Slow, Normal, or Fast.
- Colorway: Classic (white on black) or Amber (warm transit yellow).

Choose your settings in your board's web app.
""",
        "draw_icon": draw_split_flap
    },
    {
        "category": "Clock",
        "folder": "Word Clock",
        "id": "word-clock",
        "name": "Word Clock",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Conversational typographic time rendered in crisp glowing letterforms.",
        "uses": "pong",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "speed",
                "type": "choice",
                "label": "Fade rate",
                "default": "Normal",
                "options": ["Slow", "Normal", "Fast"]
            },
            {
                "key": "colors",
                "type": "choice",
                "label": "Palette",
                "default": "Classic",
                "options": ["Classic", "Warm"]
            }
        ],
        "readme": """# Word Clock

Conversational typographic time on your mooboard.

Displays current hours and five-minute increments in crisp glowing letterforms with discrete minute indicator dots.

## Settings

- Fade rate: Slow, Normal, or Fast.
- Palette: Classic (cyan mint) or Warm (candle amber).

Choose your settings in your board's web app.
""",
        "draw_icon": draw_word_clock
    },
    {
        "category": "Clock",
        "folder": "Solar Arc",
        "id": "solar-arc",
        "name": "Solar Arc",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Sun and moon arc across an illuminated horizon with real-time twilight.",
        "uses": "sunmoon",
        "minFirmware": "0.3.1",
        "readme": """# Solar Arc

An illuminated horizon arc showing the sun and moon positions.

Real-time solar arc from sunrise through golden hour, dusk twilight, and moon phases.

Takes a turn in your clock rotation when time and location are set.
""",
        "draw_icon": draw_solar_arc
    },
    {
        "category": "Clock",
        "folder": "Matrix VFD Clock",
        "id": "vfd-clock",
        "name": "Matrix VFD Clock",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Vintage vacuum fluorescent display glow with phosphor scanlines.",
        "uses": "raincode",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "color",
                "type": "color",
                "label": "Phosphor color",
                "default": "#26E6A4"
            },
            {
                "key": "speed",
                "type": "choice",
                "label": "Scan rate",
                "default": "Normal",
                "options": ["Slow", "Normal", "Fast"]
            }
        ],
        "readme": """# Matrix VFD Clock

A retro vacuum fluorescent display clock with glowing cyan-teal phosphor.

Features subtle matrix scanlines and high-contrast digital segment glow.

## Settings

- Phosphor color: Teal, Amber, or custom color.
- Scan rate: Slow, Normal, or Fast.

Choose your settings in your board's web app.
""",
        "draw_icon": draw_vfd_clock
    },
    {
        "category": "Tools",
        "folder": "Git Pulse",
        "id": "git-pulse",
        "name": "Git Pulse",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "GitHub commit streak and daily activity tiles on your desk.",
        "uses": "habits",
        "minFirmware": "0.3.1",
        "controls": [
            {
                "key": "habits",
                "type": "list",
                "label": "Repos and streaks",
                "max": 6,
                "chars": 16,
                "add": "Add repo"
            }
        ],
        "readme": """# Git Pulse

Track your daily code streaks and GitHub contributions on your mooboard.

Shows 64-day commit activity tiles, streaks, and repository push milestones.

## Controls

- Add repositories and branches to track.
- Tap completed milestones from your phone.

Manage your streak in your board's web app.
""",
        "draw_icon": draw_git_pulse
    },
    {
        "category": "Tools",
        "folder": "Next Up",
        "id": "next-up",
        "name": "Next Up",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Calendar event and meeting countdown pill on your desk.",
        "uses": "countdown",
        "minFirmware": "0.3.1",
        "readme": """# Next Up

Upcoming calendar meetings and event countdowns on your mooboard.

Displays meeting names and minutes remaining. Glows amber two minutes before start.

Configure events in your board's web app.
""",
        "draw_icon": draw_next_up
    },
    {
        "category": "Tools",
        "folder": "Flow Tide",
        "id": "flow-tide",
        "name": "Flow Tide",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Pomodoro focus tide across 128 pixels from deep blue to tea amber.",
        "uses": "pomodoro",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "focus",
                "type": "choice",
                "label": "Focus block",
                "default": "25 min",
                "options": ["15 min", "20 min", "25 min", "30 min", "45 min", "50 min"]
            },
            {
                "key": "break",
                "type": "choice",
                "label": "Rest interval",
                "default": "5 min",
                "options": ["3 min", "5 min", "10 min"]
            },
            {
                "key": "long_break",
                "type": "choice",
                "label": "Deep rest cycle",
                "default": "15 min",
                "options": ["Off", "15 min", "20 min", "30 min"]
            }
        ],
        "controls": [
            {
                "key": "left",
                "type": "readout",
                "label": "Time remaining"
            },
            {
                "key": "start",
                "type": "button",
                "label": "Start wave"
            },
            {
                "key": "pause",
                "type": "button",
                "label": "Pause wave"
            },
            {
                "key": "resume",
                "type": "button",
                "label": "Resume wave"
            },
            {
                "key": "skip",
                "type": "button",
                "label": "Skip interval"
            },
            {
                "key": "stop",
                "type": "button",
                "label": "End session"
            }
        ],
        "readme": """# Flow Tide

A deep focus Pomodoro timer that fills all 128 pixels with an animated tide.

Transitions from calm ocean blue during focus to warm tea amber on break intervals.

## Settings

- Focus block: 15, 20, 25, 30, 45, or 50 minutes.
- Rest interval: 3, 5, or 10 minutes.
- Deep rest cycle: Off, 15, 20, or 30 minutes.

Control the tide from your phone in the web app.
""",
        "draw_icon": draw_flow_tide
    },
    {
        "category": "Lifestyle",
        "folder": "Water Cow",
        "id": "water-cow",
        "name": "Water Cow",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Daily hydration habit companion with cup target and one-tap logging.",
        "uses": "tally",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "label",
                "type": "text",
                "label": "Goal title",
                "default": "Water cups",
                "max": 12
            }
        ],
        "controls": [
            {
                "key": "count",
                "type": "stepper",
                "label": "Glasses logged",
                "min": 0,
                "max": 20
            },
            {
                "key": "add",
                "type": "button",
                "label": "Drink glass"
            },
            {
                "key": "reset",
                "type": "button",
                "label": "Reset today"
            },
            {
                "key": "done",
                "type": "button",
                "label": "Save count"
            }
        ],
        "readme": """# Water Cow

Your cheerful desk hydration companion.

Log each glass of water with a single tap. The animated cow drinks alongside you as you reach your daily target.

## Settings

- Goal title: Custom label for your daily goal (up to 12 characters).

Log glasses and reset daily in your board's web app.
""",
        "draw_icon": draw_water_cow
    },
    {
        "category": "Tools",
        "folder": "Air Glance",
        "id": "air-glance",
        "name": "Air Glance",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Ambient indoor climate and outdoor air quality glance.",
        "uses": "rain",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "rain",
                "type": "choice",
                "label": "AQI range",
                "default": "Steady",
                "options": ["Gentle", "Steady", "Downpour"]
            },
            {
                "key": "city",
                "type": "choice",
                "label": "Skyline",
                "default": "Show",
                "options": ["Show", "Hide"]
            }
        ],
        "readme": """# Air Glance

Live ambient air quality badge, indoor temperature, and humidity glance.

Color-coded badges (Green, Yellow, Orange, Red) keep you informed when windows should open or close.

## Settings

- AQI range: Gentle, Steady, or Downpour display style.
- Skyline: Show or Hide the city skyline backdrop.

Choose your settings in your board's web app.
""",
        "draw_icon": draw_air_glance
    },
    {
        "category": "Tools",
        "folder": "Power Grid",
        "id": "power-grid",
        "name": "Power Grid",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Live solar production, home draw, and grid energy balance.",
        "uses": "scoreboard",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "left",
                "type": "text",
                "label": "Source name",
                "default": "Solar",
                "max": 8
            },
            {
                "key": "right",
                "type": "text",
                "label": "Load name",
                "default": "Home",
                "max": 8
            },
            {
                "key": "left_color",
                "type": "color",
                "label": "Source color",
                "default": "#FFD000"
            },
            {
                "key": "right_color",
                "type": "color",
                "label": "Load color",
                "default": "#00BFFF"
            }
        ],
        "controls": [
            {
                "key": "left",
                "type": "stepper",
                "label": "Source kW",
                "min": 0,
                "max": 99
            },
            {
                "key": "right",
                "type": "stepper",
                "label": "Load kW",
                "min": 0,
                "max": 99
            },
            {
                "key": "reset",
                "type": "button",
                "label": "Reset meters"
            },
            {
                "key": "done",
                "type": "button",
                "label": "Save levels"
            }
        ],
        "readme": """# Power Grid

Live energy flow vector monitoring solar generation, home consumption, and net grid flow.

Shows active kW metrics side by side with live power vector arrows across the panel.

## Settings

- Source name: Generation label (e.g. Solar, Solar 1).
- Load name: Consumption label (e.g. Home, EV).
- Colors: Independent colors for generation and consumption metrics.

Update meters and thresholds in your board's web app.
""",
        "draw_icon": draw_power_grid
    },
    {
        "category": "Tools",
        "folder": "Mailbox",
        "id": "mailbox",
        "name": "Mailbox",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Package deliveries and incoming mail glance with carrier tags.",
        "uses": "chores",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "people",
                "type": "text",
                "label": "Carriers",
                "default": "USPS, Amazon, UPS, FedEx",
                "max": 32
            },
            {
                "key": "rotate",
                "type": "choice",
                "label": "Check cycle",
                "default": "Daily",
                "options": ["Daily", "Weekly"]
            }
        ],
        "controls": [
            {
                "key": "chores",
                "type": "list",
                "label": "Active packages",
                "max": 6,
                "chars": 16,
                "add": "Add package"
            }
        ],
        "readme": """# Mailbox

Keep track of incoming packages and mail deliveries right on your desk.

Shows active carrier delivery badges, arrival ETAs, and package counts.

## Settings

- Carriers: Active delivery services (USPS, Amazon, UPS, FedEx).
- Check cycle: Daily or Weekly rotation.

## Controls

- Active packages: Add package tracking notes and check them off when delivered.

Manage deliveries in your board's web app.
""",
        "draw_icon": draw_mailbox
    },
    {
        "category": "Tools",
        "folder": "Flight Glance",
        "id": "flight-glance",
        "name": "Flight Glance",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Overhead flight radar glance when aircraft pass nearby.",
        "uses": "flappy",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "speed",
                "type": "choice",
                "label": "Radar sweep",
                "default": "Normal",
                "options": ["Slow", "Normal", "Fast"]
            }
        ],
        "readme": """# Flight Glance

Sky radar glance on your mooboard when an airplane flies overhead.

Renders altitude, flight path, and flight speed vectors across the display.

## Settings

- Radar sweep: Slow, Normal, or Fast sweep rate.

Configure radar settings in your board's web app.
""",
        "draw_icon": draw_flight_glance
    }
]

def main():
    sys.path.insert(0, os.path.join(REPO, "builder"))
    import build

    for app in APPS:
        app_dir = os.path.join(REPO, app["category"], app["folder"])
        os.makedirs(app_dir, exist_ok=True)

        manifest = {
            "format": 2,
            "id": app["id"],
            "name": app["name"],
            "version": app["version"],
            "by": app["by"],
            "description": app["description"],
            "category": app["category"],
            "uses": app["uses"],
            "minFirmware": app["minFirmware"],
        }
        if "settings" in app:
            manifest["settings"] = app["settings"]
        if "controls" in app:
            manifest["controls"] = app["controls"]

        # Validate manifest with build.py
        man_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        build.check_manifest(man_bytes, app["category"], app["folder"])

        with open(os.path.join(app_dir, "mooboard.json"), "wb") as f:
            f.write(man_bytes)

        # Generate & validate icon
        img = app["draw_icon"]()
        icon_bytes = clean_png_bytes(img)
        build.check_icon(icon_bytes, f"{app['category']}/{app['folder']}/icon.png")

        with open(os.path.join(app_dir, "icon.png"), "wb") as f:
            f.write(icon_bytes)

        # Write README
        with open(os.path.join(app_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(app["readme"].strip() + "\n")

        print(f"Created {app['category']}/{app['folder']} ({app['id']}) - icon: {len(icon_bytes)}B, manifest: {len(man_bytes)}B")

if __name__ == "__main__":
    main()
