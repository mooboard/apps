#!/usr/bin/env python3
"""Generates the 5 AI apps into apps-store-repo/AI/ with manifests, icons, READMEs, and datasets."""
import io
import json
import os
import struct
import zlib
from PIL import Image, ImageDraw

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AI_DIR = os.path.join(REPO, "AI")

def clean_png_bytes(img):
    if img.mode != "P":
        # Ensure RGBA, convert semi-transparent to solid or clean palette
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img = img.quantize(colors=16, method=Image.Quantize.FASTOCTREE)
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

# --- 1. AI Dreamscape Icon ---
def draw_dreamscape_icon():
    img = Image.new("RGBA", (32, 32), (10, 10, 26, 255))
    d = ImageDraw.Draw(img)
    # Stars
    stars = [(4, 4), (12, 6), (22, 3), (28, 8), (8, 12), (18, 9), (26, 14)]
    for x, y in stars:
        d.point((x, y), fill=(255, 240, 150, 255))
    d.point((12, 6), fill=(255, 255, 255, 255))
    # Aurora wave ribbon
    d.line([(2, 11), (9, 7), (16, 12), (24, 8), (30, 13)], fill=(78, 236, 213, 200), width=2)
    d.line([(1, 14), (8, 10), (17, 14), (25, 11), (30, 16)], fill=(255, 46, 136, 180), width=2)
    # Mountains silhouettes
    # Back mountain (purple)
    d.polygon([(4, 30), (14, 17), (24, 30)], fill=(45, 25, 65, 255))
    # Front mountain (dark indigo)
    d.polygon([(14, 30), (22, 19), (31, 30)], fill=(25, 20, 45, 255))
    d.polygon([(0, 30), (7, 21), (15, 30)], fill=(30, 22, 50, 255))
    # Base ground
    d.rectangle([0, 29, 31, 31], fill=(18, 14, 32, 255))
    # Frame border
    d.rounded_rectangle([0, 0, 31, 31], radius=2, outline=(60, 50, 90, 255))
    return img

# --- 2. AI Briefing Icon ---
def draw_briefing_icon():
    img = Image.new("RGBA", (32, 32), (12, 16, 28, 255))
    d = ImageDraw.Draw(img)
    # Frame
    d.rounded_rectangle([1, 1, 30, 30], radius=2, outline=(40, 55, 80, 255))
    # Synapse connections
    edges = [((8, 8), (16, 12)), ((8, 24), (16, 19)), ((24, 8), (16, 12)), ((24, 24), (16, 19)), ((16, 12), (16, 19))]
    for p1, p2 in edges:
        d.line([p1, p2], fill=(50, 90, 130, 255), width=1)
    # Neural nodes (outer)
    outer = [(8, 8), (8, 24), (24, 8), (24, 24)]
    for x, y in outer:
        d.rectangle([x-2, y-2, x+2, y+2], fill=(78, 236, 213, 255))
        d.point((x, y), fill=(255, 255, 255, 255))
    # Central AI intelligence core (amber gold)
    d.rectangle([13, 13, 19, 18], fill=(255, 214, 10, 255))
    d.rectangle([14, 14, 18, 17], fill=(255, 245, 180, 255))
    # Pulse ticks
    d.point((16, 10), fill=(255, 150, 0, 255))
    d.point((16, 21), fill=(255, 150, 0, 255))
    d.point((11, 15), fill=(255, 150, 0, 255))
    d.point((21, 15), fill=(255, 150, 0, 255))
    return img

# --- 3. AI Companion Icon ---
def draw_companion_icon():
    img = Image.new("RGBA", (32, 32), (20, 18, 30, 255))
    d = ImageDraw.Draw(img)
    # Tamagotchi egg outline
    d.rounded_rectangle([2, 2, 29, 29], radius=5, fill=(35, 28, 50, 255), outline=(90, 70, 120, 255))
    # Screen display window
    d.rounded_rectangle([5, 6, 26, 25], radius=3, fill=(15, 12, 22, 255))
    # Cat robot ears
    d.polygon([(9, 11), (12, 7), (14, 11)], fill=(255, 46, 136, 255))
    d.polygon([(18, 11), (20, 7), (23, 11)], fill=(255, 46, 136, 255))
    # Mascot face head
    d.rounded_rectangle([9, 11, 23, 21], radius=2, fill=(245, 240, 255, 255))
    # Big bright eyes
    d.rectangle([11, 14, 13, 17], fill=(78, 236, 213, 255))
    d.point((11, 14), fill=(255, 255, 255, 255))
    d.rectangle([19, 14, 21, 17], fill=(78, 236, 213, 255))
    d.point((19, 14), fill=(255, 255, 255, 255))
    # Blush
    d.point((10, 18), fill=(255, 100, 150, 255))
    d.point((22, 18), fill=(255, 100, 150, 255))
    # Smile
    d.line([(15, 18), (17, 18)], fill=(30, 20, 40, 255), width=1)
    # Sparkle heart antenna
    d.point((16, 4), fill=(255, 60, 100, 255))
    return img

# --- 4. AI Clock Builder Icon ---
def draw_builder_icon():
    img = Image.new("RGBA", (32, 32), (6, 14, 8, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=2, outline=(15, 45, 20, 255))
    # Matrix rain streams
    streams = [(4, 3, 12), (10, 2, 10), (16, 5, 14), (22, 1, 9), (27, 4, 13)]
    for x, y0, length in streams:
        for i in range(length):
            y = y0 + i * 2
            if y < 29:
                color = (34, 197, 89, 180) if i < length - 1 else (220, 255, 220, 255)
                d.point((x, y), fill=color)
    # Digital clock plate in center
    d.rectangle([5, 12, 26, 20], fill=(10, 24, 14, 240), outline=(34, 197, 89, 255))
    # 7-segment styled digits "12:00"
    # '1'
    d.line([(8, 14), (8, 18)], fill=(78, 236, 213, 255), width=1)
    # '2'
    d.line([(11, 14), (14, 14)], fill=(78, 236, 213, 255), width=1)
    d.line([(14, 14), (14, 16)], fill=(78, 236, 213, 255), width=1)
    d.line([(11, 16), (14, 16)], fill=(78, 236, 213, 255), width=1)
    d.line([(11, 16), (11, 18)], fill=(78, 236, 213, 255), width=1)
    d.line([(11, 18), (14, 18)], fill=(78, 236, 213, 255), width=1)
    # ':'
    d.point((16, 15), fill=(78, 236, 213, 255))
    d.point((16, 17), fill=(78, 236, 213, 255))
    # '0' '0'
    d.rectangle([18, 14, 20, 18], outline=(78, 236, 213, 255))
    d.rectangle([22, 14, 24, 18], outline=(78, 236, 213, 255))
    return img

# --- 5. AI Arcade Bot Icon ---
def draw_arcade_icon():
    img = Image.new("RGBA", (32, 32), (10, 12, 24, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, 30, 30], radius=2, outline=(30, 45, 80, 255))
    # Maze grid walls (cyan blue)
    walls = [
        # Outer border segments
        ([4, 4, 27, 4]),
        ([4, 4, 4, 27]),
        ([27, 4, 27, 27]),
        ([4, 27, 27, 27]),
        # Inner maze walls
        ([4, 12, 16, 12]),
        ([12, 12, 12, 20]),
        ([16, 8, 16, 16]),
        ([20, 12, 27, 12]),
        ([16, 20, 23, 20]),
        ([20, 20, 20, 27])
    ]
    for w in walls:
        d.line(w, fill=(60, 157, 255, 255), width=2)
    # AI Bot Solver agent (yellow glowing circle)
    d.rectangle([7, 15, 10, 18], fill=(255, 214, 10, 255))
    d.point((8, 16), fill=(255, 255, 255, 255))
    # Solved path trail (dots)
    d.point((8, 8), fill=(255, 150, 0, 255))
    d.point((8, 11), fill=(255, 150, 0, 255))
    d.point((13, 8), fill=(255, 150, 0, 255))
    # Goal orb (neon green)
    d.rectangle([22, 22, 25, 25], fill=(52, 199, 89, 255))
    d.point((23, 23), fill=(200, 255, 220, 255))
    return img

def main():
    os.makedirs(AI_DIR, exist_ok=True)

    # 1. AI Dreamscape
    app1 = os.path.join(AI_DIR, "AI Dreamscape")
    os.makedirs(app1, exist_ok=True)
    m1 = {
        "format": 2,
        "id": "ai-dreamscape",
        "name": "AI Dreamscape",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Generative ambient pixel landscapes from neural prompts.",
        "category": "AI",
        "uses": "aurora",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "colors",
                "type": "choice",
                "label": "Colors",
                "default": "Violet",
                "options": [
                    "Green",
                    "Green and pink",
                    "Violet"
                ]
            },
            {
                "key": "speed",
                "type": "choice",
                "label": "Speed",
                "default": "Normal",
                "options": [
                    "Slow",
                    "Normal",
                    "Fast"
                ]
            }
        ]
    }
    with open(os.path.join(app1, "mooboard.json"), "w", encoding="utf-8") as f:
        json.dump(m1, f, indent=2)
    with open(os.path.join(app1, "icon.png"), "wb") as f:
        f.write(clean_png_bytes(draw_dreamscape_icon()))
    with open(os.path.join(app1, "README.md"), "w", encoding="utf-8") as f:
        f.write("# AI Dreamscape\n\nGenerative ambient pixel landscapes created from neural prompts.\n")

    # 2. AI Briefing
    app2 = os.path.join(AI_DIR, "AI Briefing")
    os.makedirs(os.path.join(app2, "data"), exist_ok=True)
    m2 = {
        "format": 2,
        "id": "ai-briefing",
        "name": "AI Briefing",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Glanceable AI daily summaries and machine intelligence.",
        "category": "AI",
        "uses": "facts",
        "minFirmware": "0.3.1"
    }
    with open(os.path.join(app2, "mooboard.json"), "w", encoding="utf-8") as f:
        json.dump(m2, f, indent=2)
    with open(os.path.join(app2, "icon.png"), "wb") as f:
        f.write(clean_png_bytes(draw_briefing_icon()))
    with open(os.path.join(app2, "README.md"), "w", encoding="utf-8") as f:
        f.write("# AI Briefing\n\nGlanceable AI executive summaries and daily machine intelligence.\n")
    # 24 Curated AI Daily Briefings / Insights
    briefing_items = [
        ["Deep learning models process tokens in parallel using self-attention mechanisms.", "https://mooboard.co/ai"],
        ["Autonomous agents reason step-by-step using chain-of-thought prompting.", "https://mooboard.co/ai"],
        ["Diffusion models generate high fidelity visuals by reversing Gaussian noise.", "https://mooboard.co/ai"],
        ["Quantization compresses 16-bit weights to 4-bit integers with minimal loss.", "https://mooboard.co/ai"],
        ["Speculative decoding drafts tokens with a small model to speed up generation.", "https://mooboard.co/ai"],
        ["Mixture of Experts activates only sparse sub-networks for each generated token.", "https://mooboard.co/ai"],
        ["Reinforcement Learning from Human Feedback aligns model outputs with intent.", "https://mooboard.co/ai"],
        ["Retrieval Augmented Generation grounds neural model responses in live facts.", "https://mooboard.co/ai"],
        ["Direct Preference Optimization steers language models without a reward model.", "https://mooboard.co/ai"],
        ["Vector embeddings map semantic relationships into high-dimensional vector spaces.", "https://mooboard.co/ai"],
        ["FlashAttention optimizes GPU memory bandwidth using online softmax tiling.", "https://mooboard.co/ai"],
        ["In-context learning allows language models to adapt from prompt demonstrations.", "https://mooboard.co/ai"],
        ["Rotary position embeddings encode token distance with complex rotation matrices.", "https://mooboard.co/ai"],
        ["Multimodal neural networks fuse vision, audio, and language into one joint space.", "https://mooboard.co/ai"],
        ["Self-correcting code agents iteratively test, lint, and repair software builds.", "https://mooboard.co/ai"],
        ["Constitutional AI trains harmless models using written self-critique principles.", "https://mooboard.co/ai"],
        ["Knowledge distillation transfers reasoning capabilities to edge microcontrollers.", "https://mooboard.co/ai"],
        ["Synthetic data generation curates diverse reasoning trajectories for fine-tuning.", "https://mooboard.co/ai"],
        ["Neural network scaling laws accurately predict loss from compute and dataset size.", "https://mooboard.co/ai"],
        ["Sparse autoencoders decompose black-box activations into interpretable features.", "https://mooboard.co/ai"]
    ]
    with open(os.path.join(app2, "data", "list.json"), "w", encoding="utf-8") as f:
        json.dump({"format": 1, "items": briefing_items}, f, indent=2)

    # 3. AI Companion
    app3 = os.path.join(AI_DIR, "AI Companion")
    os.makedirs(app3, exist_ok=True)
    m3 = {
        "format": 2,
        "id": "ai-companion",
        "name": "AI Companion",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "An emotive desktop AI pet with interactive mood bonding.",
        "category": "AI",
        "uses": "tally",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "label",
                "type": "text",
                "label": "Happiness",
                "default": "Happiness",
                "max": 12
            }
        ],
        "controls": [
            {
                "key": "count",
                "type": "stepper",
                "label": "Energy",
                "min": 0,
                "max": 20
            },
            {
                "key": "add",
                "type": "button",
                "label": "Feed"
            },
            {
                "key": "reset",
                "type": "button",
                "label": "Nap"
            },
            {
                "key": "done",
                "type": "button",
                "label": "Pet"
            }
        ]
    }
    with open(os.path.join(app3, "mooboard.json"), "w", encoding="utf-8") as f:
        json.dump(m3, f, indent=2)
    with open(os.path.join(app3, "icon.png"), "wb") as f:
        f.write(clean_png_bytes(draw_companion_icon()))
    with open(os.path.join(app3, "README.md"), "w", encoding="utf-8") as f:
        f.write("# AI Companion\n\nAn emotive desktop AI pet with mood states and interactive bonding.\n")

    # 4. AI Clock Builder
    app4 = os.path.join(AI_DIR, "AI Clock Builder")
    os.makedirs(app4, exist_ok=True)
    m4 = {
        "format": 2,
        "id": "ai-builder",
        "name": "AI Clock Builder",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Procedural matrix HUD clock from digital rain prompts.",
        "category": "AI",
        "uses": "raincode",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "color",
                "type": "color",
                "label": "Color",
                "default": "#34C759"
            },
            {
                "key": "speed",
                "type": "choice",
                "label": "Speed",
                "default": "Normal",
                "options": [
                    "Slow",
                    "Normal",
                    "Fast"
                ]
            }
        ]
    }
    with open(os.path.join(app4, "mooboard.json"), "w", encoding="utf-8") as f:
        json.dump(m4, f, indent=2)
    with open(os.path.join(app4, "icon.png"), "wb") as f:
        f.write(clean_png_bytes(draw_builder_icon()))
    with open(os.path.join(app4, "README.md"), "w", encoding="utf-8") as f:
        f.write("# AI Clock Builder\n\nProcedural matrix HUD clock generated from digital rain prompts.\n")

    # 5. AI Arcade Bot
    app5 = os.path.join(AI_DIR, "AI Arcade Bot")
    os.makedirs(app5, exist_ok=True)
    m5 = {
        "format": 2,
        "id": "ai-arcade",
        "name": "AI Arcade Bot",
        "version": "1.0.0",
        "by": "mooboard",
        "description": "Self-learning maze-solving AI and adaptive arcade bot.",
        "category": "AI",
        "uses": "maze",
        "minFirmware": "0.3.1",
        "settings": [
            {
                "key": "speed",
                "type": "choice",
                "label": "Speed",
                "default": "Normal",
                "options": [
                    "Slow",
                    "Normal",
                    "Fast"
                ]
            }
        ]
    }
    with open(os.path.join(app5, "mooboard.json"), "w", encoding="utf-8") as f:
        json.dump(m5, f, indent=2)
    with open(os.path.join(app5, "icon.png"), "wb") as f:
        f.write(clean_png_bytes(draw_arcade_icon()))
    with open(os.path.join(app5, "README.md"), "w", encoding="utf-8") as f:
        f.write("# AI Arcade Bot\n\nSelf-learning maze-solving AI and adaptive pathfinding arcade.\n")

    print("Created 5 AI apps successfully in", AI_DIR)

if __name__ == "__main__":
    main()
