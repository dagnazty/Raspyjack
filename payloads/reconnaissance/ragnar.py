#!/usr/bin/env python3
"""
RaspyJack Payload – Ragnar Port
===============================
Network scanning and vulnerability assessment tool for RaspyJack.
Port of Ragnar (https://github.com/PierreGode/Ragnar) capabilities.

Features:
  - Network discovery (live host detection)
  - Port scanning with service detection
  - Vulnerability assessment via Nmap scripts
  - Credential harvesting simulation display
  - Threat intelligence display

Controls:
  LEFT/RIGHT   – Cycle views (SCAN/HOSTS/VULNS/LOOT)
  UP/DOWN      – Scroll lists
  KEY1         – Start/Stop scan
  KEY2         – Toggle auto-scan (2hr period)
  KEY3         – Exit to RaspyJack

Views:
  SCAN   – Current scan status, targets, progress
  HOSTS  – Discovered live hosts
  VULNS  – Found vulnerabilities
  LOOT   – Captured credentials/services
"""

import os
import sys
import csv
import json
import time
import socket
import threading
import subprocess
import ipaddress
from datetime import datetime, timedelta
from pathlib import Path

# Try multiple possible RaspyJack installation paths
possible_roots = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),  # Standard: ~/Raspyjack
    "/root/Raspyjack",
    "/home/pi/Raspyjack",
    "/opt/Raspyjack",
]
for root in possible_roots:
    if root not in sys.path and os.path.isdir(root):
        sys.path.insert(0, root)

import RPi.GPIO as GPIO
import LCD_1in44, LCD_Config
from PIL import Image, ImageDraw, ImageFont
from payloads._input_helper import get_button

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
W, H = 128, 128

PINS = {
    "UP": 6, "DOWN": 19, "LEFT": 5, "RIGHT": 26,
    "OK": 13, "KEY1": 21, "KEY2": 20, "KEY3": 16,
}

VIEWS = ["SCAN", "HOSTS", "VULNS", "LOOT", "PROFILE"]

# Loot directory
LOOT_DIR = Path("/root/Raspyjack/loot/Ragnar/")
LOOT_DIR.mkdir(parents=True, exist_ok=True)

# Scan settings
SCAN_PERIOD = 2 * 60 * 60  # 2 hours for auto-scan
NMAP_QUICK = ["-T4", "-sn"]  # Ping scan for discovery
NMAP_PORT = ["-T4", "-sV", "--script=vuln"]  # Port + vuln scan
NMAP_VULN = ["-T4", "--script=vuln,nmap-vulners"]  # Full vuln scan

# Scan profiles
SCAN_PROFILES = {
    "QUICK": {
        "desc": "Ping scan only",
        "discovery": ["-T4", "-sn"],
        "port_scan": ["-T4", "-sT"],
        "timeout": 60,
    },
    "NORMAL": {
        "desc": "Ports + basic vuln",
        "discovery": ["-T4", "-sn"],
        "port_scan": ["-T4", "-sV", "--script=vuln"],
        "timeout": 120,
    },
    "DEEP": {
        "desc": "Full vuln scan",
        "discovery": ["-T4", "-sn"],
        "port_scan": ["-T4", "-sV", "-sC", "--script=vuln,nmap-vulners,vulscan"],
        "timeout": 300,
    },
    "STEALTH": {
        "desc": "Slow, stealthy scan",
        "discovery": ["-T1", "-sn"],
        "port_scan": ["-T1", "-sS", "-sV", "-p-"],
        "timeout": 600,
    },
}

# Default profile
DEFAULT_PROFILE = "NORMAL"

# Colors
GREEN = "#00FF00"
RED = "#FF0000"
YELLOW = "#FFFF00"
CYAN = "#00FFFF"
WHITE = "#FFFFFF"
BLACK = "#000000"
GRAY = "#808080"

# Animation frames
SPINNER_FRAMES = ["|", "/", "-", "\\"]
PULSE_FRAMES = ["*", "+", "•", "+"]

# Image paths for Ragnar sprites
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
IDLE_FRAMES = []  # Will be loaded from images
SCAN_FRAMES = []  # Will be loaded from images

def load_images():
    """Load Ragnar sprite images if available."""
    global IDLE_FRAMES, SCAN_FRAMES
    
    try:
        from PIL import Image
        import os
        
        # Look in loot folder first, then fall back to images folder
        possible_dirs = [
            "/root/Raspyjack/loot/Ragnar/images",
            IMAGES_DIR,
        ]
        
        def process_image(fpath):
            """Load image and make white background transparent."""
            img = Image.open(fpath)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            # Make white (#FFFFFF) transparent
            data = img.getdata()
            new_data = []
            for item in data:
                # If pixel is close to white, make it transparent
                if item[0] > 200 and item[1] > 200 and item[2] > 200:
                    new_data.append((0, 0, 0, 0))  # Transparent
                else:
                    new_data.append(item)
            img.putdata(new_data)
            return img
        
        # Load IDLE frames
        for img_dir in possible_dirs:
            idle_dir = os.path.join(img_dir, "IDLE")
            if os.path.isdir(idle_dir):
                for i in range(10):
                    for ext in ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                        fname = f"IDLE{ext}.bmp" if ext else "IDLE.bmp"
                        fpath = os.path.join(idle_dir, fname)
                        if os.path.exists(fpath):
                            IDLE_FRAMES.append(process_image(fpath))
                if IDLE_FRAMES:
                    break
        
        # Load NetworkScanner frames (for scanning)
        for img_dir in possible_dirs:
            scan_dir = os.path.join(img_dir, "NetworkScanner")
            if os.path.isdir(scan_dir):
                for i in range(10):
                    for ext in ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                        fname = f"NetworkScanner{ext}.bmp" if ext else "NetworkScanner.bmp"
                        fpath = os.path.join(scan_dir, fname)
                        if os.path.exists(fpath):
                            SCAN_FRAMES.append(process_image(fpath))
                if SCAN_FRAMES:
                    break
        
        print(f"[INFO] Loaded {len(IDLE_FRAMES)} IDLE frames, {len(SCAN_FRAMES)} SCAN frames")
    except Exception as e:
        print(f"[WARN] Could not load images: {e}")

# Try to load images on import
load_images()

# Fallback Viking sprite if images not available
VIKING_SPRITE = [
    "  ████  ",
    " ██──██ ",
    "████████",
    "████████",
    " ██▓▓██ ",
    "  ████  ",
    "   ██   ",
    "  █  █  ",
]

def draw_viking_fallback(x, y, size=4, color=GREEN, frame=0):
    """Draw a simple Viking warrior sprite as fallback."""
    anim_offset = [0, 1, 0, -1][frame % 4]
    for row_idx, row in enumerate(VIKING_SPRITE):
        for col_idx, pixel in enumerate(row):
            if pixel in "█▓":
                px = x + (col_idx * size) + (anim_offset if row_idx == 7 else 0)
                py = y + (row_idx * size)
                fill = color if pixel == "█" else YELLOW
                draw.rectangle((px, py, px + size - 1, py + size - 1), fill=fill)

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
state = {
    "scanning": False,
    "auto_scan": False,
    "current_view": 0,
    "scroll_offset": 0,
    "targets": [],
    "hosts": [],
    "vulns": [],
    "loot": [],
    "scan_start": None,
    "scan_progress": 0,  # 0-100 percentage
    "current_target": "",
    "last_scan_time": None,
    "network": "192.168.1.0/24",
    "frame_index": 0,  # For animations
    "scan_profile": DEFAULT_PROFILE,  # Current scan profile
}

# ---------------------------------------------------------------------------
# GPIO Setup
# ---------------------------------------------------------------------------
GPIO.setmode(GPIO.BCM)
for pin in PINS.values():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ---------------------------------------------------------------------------
# LCD Setup
# ---------------------------------------------------------------------------
LCD = LCD_1in44.LCD()
LCD.LCD_Init(LCD_1in44.SCAN_DIR_DFT)

# Fonts
font_small = ImageFont.load_default()
font_large = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10
)
font_tiny = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8
)

canvas = Image.new("RGB", (W, H), BLACK)
draw = ImageDraw.Draw(canvas)

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def get_local_network():
    """Get the local network based on default route."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            line = result.stdout.strip()
            # Parse "default via X.X.X.X dev eth0 proto dhcp"
            parts = line.split()
            if "via" in parts:
                gateway = parts[parts.index("via") + 1]
                # Assume /24 network
                return str(ipaddress.IPv4Network(f"{gateway}/24", strict=False))
    except Exception:
        pass
    return state["network"]

def run_nmap(args, target, timeout=120):
    """Run nmap and return output."""
    try:
        cmd = ["nmap"] + args + [target]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "", "Timeout"
    except Exception as e:
        return "", str(e)

def parse_nmap_hosts(output):
    """Parse nmap output for live hosts."""
    hosts = []
    for line in output.split("\n"):
        if "Nmap scan report for" in line:
            parts = line.split("for ")[-1].split()
            ip = parts[0]
            hosts.append({"ip": ip, "status": "up", "ports": [], "services": []})
        elif "Ports:" in line:
            # Parse port info
            port_section = line.split("Ports:")[-1].strip()
            # This is simplified - real parsing would be more complex
            if hosts:
                hosts[-1]["ports_found"] = True
    return hosts

def parse_nmap_ports(output, host_ip):
    """Parse nmap output for open ports and services."""
    ports = []
    in_ports = False
    for line in output.split("\n"):
        if "Ports:" in line:
            in_ports = True
            continue
        if in_ports:
            if line.strip() == "" or "Service info" in line:
                break
            # Parse: 22/tcp   open  ssh     OpenSSH
            parts = line.strip().split()
            if len(parts) >= 3 and "/" in parts[0]:
                port_proto = parts[0].split("/")
                port = port_proto[0]
                proto = port_proto[1] if len(port_proto) > 1 else "tcp"
                state = parts[1]
                service = parts[2] if len(parts) > 2 else "unknown"
                ports.append({
                    "port": port, "proto": proto, "state": state,
                    "service": service
                })
    return ports

def parse_nmap_vulns(output):
    """Parse nmap output for vulnerabilities."""
    vulns = []
    severity_colors = {
        "CRITICAL": RED,
        "HIGH": YELLOW,
        "MEDIUM": YELLOW,
        "LOW": CYAN,
    }
    
    for line in output.split("\n"):
        line_lower = line.lower()
        # Look for vuln script output, CVEs, or severity
        if any(x in line_lower for x in ["vuln", "cve-", "cve:", "exploit", "attack"]):
            # Extract severity if present
            severity = "MEDIUM"
            for sev in severity_colors:
                if sev in line.upper():
                    severity = sev
            vulns.append({
                "text": line.strip(),
                "severity": severity
            })
    return vulns

def parse_nmap_services(output):
    """Parse nmap output for detailed service information."""
    services = []
    for line in output.split("\n"):
        # Look for service info lines
        # Format: 22/tcp   open  ssh     OpenSSH 7.4
        if "/tcp" in line or "/udp" in line:
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    port_proto = parts[0].split("/")
                    service = {
                        "port": port_proto[0],
                        "proto": port_proto[1] if len(port_proto) > 1 else "tcp",
                        "state": parts[1],
                        "service": parts[2],
                        "version": " ".join(parts[3:]) if len(parts) > 3 else ""
                    }
                    services.append(service)
                except:
                    pass
    return services

def save_loot():
    """Save discovered data to loot directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save hosts
    hosts_file = LOOT_DIR / f"hosts_{timestamp}.json"
    with open(hosts_file, "w") as f:
        json.dump(state["hosts"], f, indent=2)
    
    # Save vulns
    vulns_file = LOOT_DIR / f"vulns_{timestamp}.json"
    with open(vulns_file, "w") as f:
        json.dump(state["vulns"], f, indent=2)
    
    # Save loot summary
    loot_file = LOOT_DIR / f"loot_{timestamp}.txt"
    with open(loot_file, "w") as f:
        f.write(f"Ragnar Scan - {timestamp}\n")
        f.write(f"Network: {state['network']}\n")
        f.write(f"Hosts found: {len(state['hosts'])}\n")
        f.write(f"Vulnerabilities: {len(state['vulns'])}\n")
        f.write("\n=== HOSTS ===\n")
        for host in state["hosts"]:
            f.write(f"{host['ip']} - {host.get('status', 'unknown')}\n")
            for port in host.get("ports", []):
                f.write(f"  {port['port']}/{port['proto']} {port['service']}\n")
        f.write("\n=== VULNERABILITIES ===\n")
        for vuln in state["vulns"]:
            f.write(f"{vuln}\n")

# ---------------------------------------------------------------------------
# Scanning Functions
# ---------------------------------------------------------------------------
def get_profile():
    """Get current scan profile settings."""
    return SCAN_PROFILES.get(state["scan_profile"], SCAN_PROFILES["NORMAL"])

def discover_hosts():
    """Discover live hosts on the network."""
    profile = get_profile()
    state["current_target"] = f"Discovering hosts..."
    
    # Run discovery scan
    output, err = run_nmap(profile["discovery"], state["network"], timeout=profile["timeout"])
    hosts = parse_nmap_hosts(output)
    
    # Also save raw output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_file = LOOT_DIR / f"scan_discovery_{timestamp}.txt"
    with open(scan_file, "w") as f:
        f.write(output)
    
    state["hosts"] = hosts
    return hosts

def scan_host(host_ip):
    """Scan a single host for ports and vulnerabilities."""
    profile = get_profile()
    state["current_target"] = f"Scanning {host_ip}..."
    
    # Port + vuln scan with XML output
    xml_output = f"-oX {LOOT_DIR}/scan_{host_ip.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    cmd_args = profile["port_scan"] + xml_output.split()
    
    output, err = run_nmap(cmd_args, host_ip, timeout=profile["timeout"])
    ports = parse_nmap_ports(output, host_ip)
    
    # Get vulns with more detailed parsing
    vulns = parse_nmap_vulns(output)
    
    # Get service versions
    services = parse_nmap_services(output)
    
    # Update host in state
    for host in state["hosts"]:
        if host["ip"] == host_ip:
            host["ports"] = ports
            host["vulns"] = vulns
            host["services"] = services
            state["vulns"].extend([f"{host_ip}:{p['port']}: {v}" for v in vulns for p in ports])
            break
    
    # Add to loot if interesting findings
    if ports or vulns:
        state["loot"].append({
            "ip": host_ip,
            "timestamp": datetime.now().isoformat(),
            "ports": ports,
            "vulns": vulns,
            "services": services
        })

def full_scan():
    """Run complete network scan."""
    state["scanning"] = True
    state["scan_start"] = datetime.now()
    state["scan_progress"] = 0
    
    # Update network
    state["network"] = get_local_network()
    state["current_target"] = "Discovering hosts..."
    
    # Discover hosts
    discover_hosts()
    state["scan_progress"] = 20
    
    # Scan each host
    total_hosts = len(state["hosts"])
    for i, host in enumerate(state["hosts"]):
        if not state["scanning"]:
            break
        state["current_target"] = f"Scanning {host['ip']}..."
        state["scan_progress"] = 20 + int((i / max(total_hosts, 1)) * 80)
        scan_host(host["ip"])
    
    state["scan_progress"] = 100
    
    # Save results
    save_loot()
    
    state["scanning"] = False
    state["scan_progress"] = 0
    state["last_scan_time"] = datetime.now()
    state["current_target"] = "Scan complete"

def scan_worker():
    """Worker thread for scanning."""
    thread = threading.Thread(target=full_scan, daemon=True)
    thread.start()

# ---------------------------------------------------------------------------
# Display Functions
# ---------------------------------------------------------------------------
def clear_screen():
    """Clear the LCD screen."""
    draw.rectangle((0, 0, W, H), fill=BLACK)
    LCD.LCD_ShowImage(canvas, 0, 0)

def draw_view_scan():
    """Draw the SCAN view."""
    # Clear screen
    draw.rectangle((0, 0, W, H), fill=BLACK)
    
    # Status bar
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), "RAGNAR SCAN", font=font_tiny, fill=BLACK)
    
    # Status indicator with spinner animation
    if state["scanning"]:
        spinner = SPINNER_FRAMES[state["frame_index"] % len(SPINNER_FRAMES)]
        draw.text((W - 55, 2), f"{spinner}", font=font_tiny, fill=RED)
        draw.text((W - 30, 2), "SCAN", font=font_tiny, fill=RED)
    else:
        draw.text((W - 30, 2), "IDLE", font=font_tiny, fill=GREEN)
    
    # Draw Ragnar sprite (use loaded images if available, otherwise fallback)
    frames = SCAN_FRAMES if state["scanning"] else IDLE_FRAMES
    if frames:
        # Use loaded image frames
        frame_idx = state["frame_index"] % len(frames)
        frame_img = frames[frame_idx]
        # Resize to fit (target is ~32x32 area)
        frame_img = frame_img.resize((32, 32), Image.LANCZOS)
        # Paste at position
        canvas.paste(frame_img, (W - 36, 12), frame_img if frame_img.mode == 'RGBA' else None)
    else:
        # Fallback: draw simple sprite
        viking_color = RED if state["scanning"] else GREEN
        draw_viking_fallback(W - 45, 14, size=3, color=viking_color, frame=state["frame_index"])
    
    # Mode under sprite
    draw.text((W - 48, 48), f"Mode:", font=font_tiny, fill=GRAY)
    draw.text((W - 48, 56), state["scan_profile"][:8], font=font_tiny, fill=CYAN)
    
    # Network
    draw.text((2, 16), f"Net: {state['network'][:14]}", font=font_tiny, fill=WHITE)
    
    # Stats
    y = 30
    draw.text((2, y), f"Hosts: {len(state['hosts'])}", font=font_small, fill=GREEN)
    y += 10
    draw.text((2, y), f"Vulns: {len(state['vulns'])}", font=font_small, fill=YELLOW)
    y += 10
    draw.text((2, y), f"Loot: {len(state['loot'])}", font=font_small, fill=CYAN)
    
    # Current target with pulse animation when scanning
    y = 60
    draw.text((2, y), "Target:", font=font_tiny, fill=GRAY)
    y += 8
    target = state["current_target"][:20] if state["current_target"] else "None"
    if state["scanning"]:
        # Pulse effect on target
        pulse = PULSE_FRAMES[state["frame_index"] % len(PULSE_FRAMES)]
        draw.text((2, y), f"{pulse} {target}", font=font_tiny, fill=WHITE)
    else:
        draw.text((2, y), target, font=font_tiny, fill=WHITE)
    
    # Progress bar when scanning
    if state["scanning"] and state["scan_progress"] > 0:
        progress = state["scan_progress"] / 100.0
        bar_width = int((W - 4) * progress)
        draw.rectangle((2, H - 20, W - 2, H - 15), outline=GRAY)
        draw.rectangle((3, H - 19, 3 + bar_width, H - 16), fill=GREEN)
        draw.text((2, H - 14), f"{state['scan_progress']}%", font=font_tiny, fill=GRAY)
    
    # Auto-scan status
    if state["auto_scan"]:
        draw.text((2, H - 10), "AUTO-SCAN: ON", font=font_tiny, fill=YELLOW)
    
    # Controls hint
    draw.text((W - 40, H - 10), "K1:Scan", font=font_tiny, fill=GRAY)
    
    LCD.LCD_ShowImage(canvas, 0, 0)

def draw_view_hosts():
    """Draw the HOSTS view."""
    draw.rectangle((0, 0, W, H), fill=BLACK)
    
    # Status bar
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), "DISCOVERED HOSTS", font=font_tiny, fill=BLACK)
    draw.text((W - 20, 2), f"{len(state['hosts'])}", font=font_tiny, fill=BLACK)
    
    if not state["hosts"]:
        draw.text((2, 30), "No hosts found", font=font_small, fill=GRAY)
        draw.text((2, 45), "Press KEY1 to", font=font_tiny, fill=GRAY)
        draw.text((2, 55), "start scan", font=font_tiny, fill=GRAY)
    else:
        y = 16 + state["scroll_offset"] * 12
        for i, host in enumerate(state["hosts"][state["scroll_offset"]:state["scroll_offset"] + 8]):
            if y > H - 10:
                break
            draw.text((2, y), host["ip"][:18], font=font_small, fill=GREEN)
            y += 10
    
    LCD.LCD_ShowImage(canvas, 0, 0)

def draw_view_vulns():
    """Draw the VULNS view."""
    draw.rectangle((0, 0, W, H), fill=BLACK)
    
    # Status bar
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), "VULNERABILITIES", font=font_tiny, fill=BLACK)
    draw.text((W - 20, 2), f"{len(state['vulns'])}", font=font_tiny, fill=BLACK)
    
    if not state["vulns"]:
        draw.text((2, 30), "No vulns found", font=font_small, fill=GRAY)
        draw.text((2, 45), "Run a scan to", font=font_tiny, fill=GRAY)
        draw.text((2, 55), "detect vulns", font=font_tiny, fill=GRAY)
    else:
        y = 16 + state["scroll_offset"] * 12
        for vuln in state["vulns"][state["scroll_offset"]:state["scroll_offset"] + 8]:
            if y > H - 10:
                break
            # Truncate long lines
            text = vuln[:20] if len(vuln) > 20 else vuln
            draw.text((2, y), text, font=font_tiny, fill=YELLOW)
            y += 10
    
    LCD.LCD_ShowImage(canvas, 0, 0)

def draw_view_loot():
    """Draw the LOOT view."""
    draw.rectangle((0, 0, W, H), fill=BLACK)
    
    # Status bar
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), "CAPTURED DATA", font=font_tiny, fill=BLACK)
    draw.text((W - 20, 2), f"{len(state['loot'])}", font=font_tiny, fill=BLACK)
    
    if not state["loot"]:
        draw.text((2, 30), "No loot yet", font=font_small, fill=GRAY)
        draw.text((2, 45), "Scan to discover", font=font_tiny, fill=GRAY)
        draw.text((2, 55), "services & creds", font=font_tiny, fill=GRAY)
    else:
        y = 16 + state["scroll_offset"] * 12
        for item in state["loot"][state["scroll_offset"]:state["scroll_offset"] + 8]:
            if y > H - 10:
                break
            ports = len(item.get("ports", []))
            vulns = len(item.get("vulns", []))
            text = f"{item['ip']} P:{ports} V:{vulns}"
            draw.text((2, y), text[:20], font=font_tiny, fill=CYAN)
            y += 10
    
    LCD.LCD_ShowImage(canvas, 0, 0)

def draw_view_profile():
    """Draw the PROFILE view - select scan profile."""
    draw.rectangle((0, 0, W, H), fill=BLACK)
    
    # Status bar
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), "SCAN PROFILE", font=font_tiny, fill=BLACK)
    
    # Current profile
    current = state["scan_profile"]
    draw.text((2, 16), f"Current: {current}", font=font_small, fill=GREEN)
    
    # Show profile descriptions
    y = 30
    profile_names = list(SCAN_PROFILES.keys())
    for i, name in enumerate(profile_names):
        prefix = ">" if name == current else " "
        desc = SCAN_PROFILES[name]["desc"]
        text = f"{prefix} {name}: {desc}"
        color = GREEN if name == current else GRAY
        draw.text((2, y), text[:22], font=font_tiny, fill=color)
        y += 12
    
    # Instructions
    draw.text((2, H - 20), "KEY1: Select", font=font_tiny, fill=GRAY)
    draw.text((2, H - 10), "LEFT/RIGHT: Cycle", font=font_tiny, fill=GRAY)
    
    LCD.LCD_ShowImage(canvas, 0, 0)

def render():
    """Render current view."""
    # Update animation frame on each render
    state["frame_index"] += 1
    views = [draw_view_scan, draw_view_hosts, draw_view_vulns, draw_view_loot, draw_view_profile]
    views[state["current_view"]]()

# ---------------------------------------------------------------------------
# Auto-scan Timer
# ---------------------------------------------------------------------------
auto_scan_thread = None
auto_scan_running = True

def auto_scan_worker():
    """Background worker for auto-scan."""
    while auto_scan_running:
        if state["auto_scan"] and not state["scanning"]:
            # Check if enough time has passed
            if state["last_scan_time"] is None or \
               (datetime.now() - state["last_scan_time"]).total_seconds() >= SCAN_PERIOD:
                scan_worker()
        time.sleep(10)

auto_scan_thread = threading.Thread(target=auto_scan_worker, daemon=True)
auto_scan_thread.start()

# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------
def main():
    """Main application loop."""
    global auto_scan_running
    
    render()
    
    while True:
        button = get_button(PINS, GPIO)
        
        # Re-render during scan to show progress
        if state["scanning"]:
            render()
            time.sleep(0.3)
        
        if button is None:
            continue
        
        # Debounce: wait for button release
        while get_button(PINS, GPIO) is not None:
            time.sleep(0.05)
        time.sleep(0.1)  # Extra debounce delay
        
        if button == "KEY3":
            # Exit
            break
        
        elif button == "KEY1":
            # Toggle scan
            if state["scanning"]:
                state["scanning"] = False
            else:
                scan_worker()
            render()
        
        elif button == "KEY2":
            # Toggle auto-scan
            state["auto_scan"] = not state["auto_scan"]
            render()
        
        elif button == "LEFT":
            # Cycle to previous view
            state["current_view"] = (state["current_view"] - 1) % len(VIEWS)
            state["scroll_offset"] = 0
            render()
        
        elif button == "RIGHT":
            # Cycle to next view
            state["current_view"] = (state["current_view"] + 1) % len(VIEWS)
            state["scroll_offset"] = 0
            render()
        
        elif button == "UP":
            if state["current_view"] == 4:  # PROFILE view - select previous
                profiles = list(SCAN_PROFILES.keys())
                current_idx = profiles.index(state["scan_profile"])
                state["scan_profile"] = profiles[(current_idx - 1) % len(profiles)]
            else:
                # Scroll up lists
                if state["scroll_offset"] > 0:
                    state["scroll_offset"] -= 1
            render()
        
        elif button == "DOWN":
            if state["current_view"] == 4:  # PROFILE view - select next
                profiles = list(SCAN_PROFILES.keys())
                current_idx = profiles.index(state["scan_profile"])
                state["scan_profile"] = profiles[(current_idx + 1) % len(profiles)]
            else:
                # Scroll down lists
                max_items = 8
                if state["current_view"] == 1:  # HOSTS
                    max_items = max(0, len(state["hosts"]) - 8)
                elif state["current_view"] == 2:  # VULNS
                    max_items = max(0, len(state["vulns"]) - 8)
                elif state["current_view"] == 3:  # LOOT
                    max_items = max(0, len(state["loot"]) - 8)
                
                if state["scroll_offset"] < max_items:
                    state["scroll_offset"] += 1
            render()
    
    # Cleanup
    auto_scan_running = False
    GPIO.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        GPIO.cleanup()
