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

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

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

VIEWS = ["SCAN", "HOSTS", "VULNS", "LOOT"]

# Loot directory
LOOT_DIR = Path("/root/Raspyjack/loot/Ragnar/")
LOOT_DIR.mkdir(parents=True, exist_ok=True)

# Scan settings
SCAN_PERIOD = 2 * 60 * 60  # 2 hours for auto-scan
NMAP_QUICK = ["-T4", "-sn"]  # Ping scan for discovery
NMAP_PORT = ["-T4", "-sV", "--script=vuln"]  # Port + vuln scan
NMAP_VULN = ["-T4", "--script=vuln,nmap-vulners"]  # Full vuln scan

# Colors
GREEN = "#00FF00"
RED = "#FF0000"
YELLOW = "#FFFF00"
CYAN = "#00FFFF"
WHITE = "#FFFFFF"
BLACK = "#000000"

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
    "current_target": "",
    "last_scan_time": None,
    "network": "192.168.1.0/24",
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
    for line in output.split("\n"):
        # Look for vuln script output
        if "vuln" in line.lower() or "CVE-" in line:
            vulns.append(line.strip())
    return vulns

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
def discover_hosts():
    """Discover live hosts on the network."""
    state["current_target"] = f"Discovering hosts on {state['network']}..."
    
    output, _ = run_nmap(NMAP_QUICK, state["network"], timeout=60)
    hosts = parse_nmap_hosts(output)
    
    state["hosts"] = hosts
    return hosts

def scan_host(host_ip):
    """Scan a single host for ports and vulnerabilities."""
    state["current_target"] = f"Scanning {host_ip}..."
    
    # Port scan
    output, _ = run_nmap(NMAP_PORT, host_ip, timeout=120)
    ports = parse_nmap_ports(output, host_ip)
    
    # Get vulns
    vulns = parse_nmap_vulns(output)
    
    # Update host in state
    for host in state["hosts"]:
        if host["ip"] == host_ip:
            host["ports"] = ports
            host["vulns"] = vulns
            state["vulns"].extend([f"{host_ip}: {v}" for v in vulns])
            break
    
    # Add to loot if interesting findings
    if ports or vulns:
        state["loot"].append({
            "ip": host_ip,
            "timestamp": datetime.now().isoformat(),
            "ports": ports,
            "vulns": vulns
        })

def full_scan():
    """Run complete network scan."""
    state["scanning"] = True
    state["scan_start"] = datetime.now()
    
    # Update network
    state["network"] = get_local_network()
    
    # Discover hosts
    discover_hosts()
    
    # Scan each host
    for host in state["hosts"]:
        if not state["scanning"]:
            break
        scan_host(host["ip"])
    
    # Save results
    save_loot()
    
    state["scanning"] = False
    state["last_scan_time"] = datetime.now()
    state["current_target"] = "Scan complete"

def scan_worker():
    """Worker thread for scanning."""
    thread = threading.Thread(target=full_scan, daemon=True)
    thread.start()

# ---------------------------------------------------------------------------
# Display Functions
# ---------------------------------------------------------------------------
def show(lines, invert=False, spacing=2):
    """Render lines to LCD."""
    if isinstance(lines, str):
        lines = lines.split("\n")
    
    draw.rectangle((0, 0, W, H), fill="white" if invert else BLACK)
    fg = BLACK if invert else GREEN
    
    y = 2
    for line in lines:
        draw.text((2, y), line, font=font_small, fill=fg)
        y += 8 + spacing
    
    canvas = Image.new("RGB", (W, H), "white" if invert else BLACK)
    draw = ImageDraw.Draw(canvas)
    y = 2
    for line in lines:
        draw.text((2, y), line, font=font_small, fill=fg)
        y += 8 + spacing
    
    LCD.LCD_ShowImage(canvas, 0, 0)

def draw_status_bar(title):
    """Draw the status bar at top."""
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), title[:18], font=font_tiny, fill=BLACK)

def draw_view_scan():
    """Draw the SCAN view."""
    draw.rectangle((0, 0, W, H), fill=BLACK)
    
    # Status bar
    draw.rectangle((0, 0, W, 12), fill=CYAN)
    draw.text((2, 2), "RAGNAR SCAN", font=font_tiny, fill=BLACK)
    
    # Status indicator
    status = "SCANNING" if state["scanning"] else "IDLE"
    color = RED if state["scanning"] else GREEN
    draw.text((W - 50, 2), status, font=font_tiny, fill=color)
    
    # Network
    draw.text((2, 16), f"Net: {state['network'][:18]}", font=font_tiny, fill=WHITE)
    
    # Stats
    y = 30
    draw.text((2, y), f"Hosts: {len(state['hosts'])}", font=font_small, fill=GREEN)
    y += 10
    draw.text((2, y), f"Vulns: {len(state['vulns'])}", font=font_small, fill=YELLOW)
    y += 10
    draw.text((2, y), f"Loot: {len(state['loot'])}", font=font_small, fill=CYAN)
    
    # Current target
    y = 60
    draw.text((2, y), "Target:", font=font_tiny, fill=GRAY)
    y += 8
    target = state["current_target"][:20] if state["current_target"] else "None"
    draw.text((2, y), target, font=font_tiny, fill=WHITE)
    
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

def render():
    """Render current view."""
    views = [draw_view_scan, draw_view_hosts, draw_view_vulns, draw_view_loot]
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
        button = get_button(timeout_ms=200)
        
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
            # Previous view
            state["current_view"] = (state["current_view"] - 1) % len(VIEWS)
            state["scroll_offset"] = 0
            render()
        
        elif button == "RIGHT":
            # Next view
            state["current_view"] = (state["current_view"] + 1) % len(VIEWS)
            state["scroll_offset"] = 0
            render()
        
        elif button == "UP":
            # Scroll up
            if state["scroll_offset"] > 0:
                state["scroll_offset"] -= 1
            render()
        
        elif button == "DOWN":
            # Scroll down
            max_items = 8
            if state["current_view"] == 1:  # HOSTS
                max_items = len(state["hosts"]) - 8
            elif state["current_view"] == 2:  # VULNS
                max_items = len(state["vulns"]) - 8
            elif state["current_view"] == 3:  # LOOT
                max_items = len(state["loot"]) - 8
            
            if state["scroll_offset"] < max_items:
                state["scroll_offset"] += 1
            render()
        
        # Re-render during scan to show progress
        if state["scanning"]:
            render()
            time.sleep(0.5)
    
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
