#!/usr/bin/env python3
"""
Ragnar - Main Menu
===================
Unified launcher for Ragnar modules on RaspyJack.
Provides menu to select: Scan, Brute Force, or Exit
"""

import os
import sys
import time
import threading

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

# Custom exception for exiting back to menu
class ExitToMenu(Exception):
    """Raised when user wants to exit back to Ragnar main menu."""
    pass

# Handle imports for both package and script mode
try:
    from . import ragnar
    from . import ragnar_brute
except ImportError:
    # When run as script, use absolute imports
    import importlib.util
    ragnar_dir = os.path.dirname(__file__)
    spec = importlib.util.spec_from_file_location("ragnar", os.path.join(ragnar_dir, "ragnar.py"))
    ragnar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ragnar)
    spec = importlib.util.spec_from_file_location("ragnar_brute", os.path.join(ragnar_dir, "ragnar_brute.py"))
    ragnar_brute = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ragnar_brute)

try:
    import RPi.GPIO as GPIO
    import LCD_1in44, LCD_Config
    from PIL import Image, ImageDraw, ImageFont
    from payloads._input_helper import get_button
    HAS_LCD = True
except ImportError:
    HAS_LCD = False
    print("[WARN] Running without LCD/GPIO")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
W, H = 128, 128

PINS = {
    "UP": 6, "DOWN": 19, "LEFT": 5, "RIGHT": 26,
    "OK": 13, "KEY1": 21, "KEY2": 20, "KEY3": 16,
}

# Menu options
MENU_OPTIONS = [
    {"name": "SCAN", "desc": "Network Scanner", "module": "scan"},
    {"name": "BRUTE", "desc": "Brute Force", "module": "brute"},
    {"name": "WIFI", "desc": "WiFi AP", "module": "wifi"},
    {"name": "STEAL", "desc": "Data Stealer", "module": "steal"},
]

# Colors
GREEN = "#00FF00"
RED = "#FF0000"
YELLOW = "#FFFF00"
CYAN = "#00FFFF"
WHITE = "#FFFFFF"
BLACK = "#000000"
GRAY = "#808080"

# Animation frames
SPINNER = ["|", "/", "-", "\\"]

# State
state = {
    "menu_index": 0,
    "running": True,
    "frame": 0,
}

# ---------------------------------------------------------------------------
# LCD Setup
# ---------------------------------------------------------------------------
if HAS_LCD:
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    LCD = LCD_1in44.LCD()
    LCD.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
    
    font_small = ImageFont.load_default()
    font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    
    canvas = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(canvas)

# ---------------------------------------------------------------------------
# Display Functions
# ---------------------------------------------------------------------------
if HAS_LCD:
    def draw_menu():
        """Draw the main menu."""
        draw.rectangle((0, 0, W, H), fill=BLACK)
        
        # Header
        draw.rectangle((0, 0, W, 12), fill=CYAN)
        draw.text((2, 2), "RAGNAR v1.0", font=font_tiny, fill=BLACK)
        
        # Animated Viking in corner
        spinner = SPINNER[state["frame"] % 4]
        draw.text((W - 12, 2), spinner, font=font_tiny, fill=BLACK)
        
        # Menu options - show selected one big in middle
        y = 20
        
        # Show current option big in center
        opt = MENU_OPTIONS[state["menu_index"]]
        color = GREEN if opt["module"] in ["scan", "brute"] else YELLOW
        
        # Arrow indicators
        draw.text((2, 45), "<", font=font_large, fill=color)
        draw.text((W - 10, 45), ">", font=font_large, fill=color)
        
        # Selected option name large
        draw.text((30, 40), opt["name"], font=font_large, fill=color)
        
        # Description below
        y = 70
        draw.text((10, y), opt["desc"], font=font_tiny, fill=WHITE)
        
        # Controls hint
        draw.text((2, H - 10), "UP/DOWN:Select OK:Run", font=font_tiny, fill=GRAY)
        
        state["frame"] += 1
        LCD.LCD_ShowImage(canvas, 0, 0)

# ---------------------------------------------------------------------------
# Module Launchers
# ---------------------------------------------------------------------------
def launch_scan():
    """Launch the network scanner module."""
    print("[INFO] Launching SCAN module...")
    if HAS_LCD:
        draw.rectangle((0, 0, W, H), fill=BLACK)
        draw.text((2, 50), "Loading Scan...", font=font_small, fill=GREEN)
        LCD.LCD_ShowImage(canvas, 0, 0)
    try:
        ragnar.main()
    except Exception as e:
        print(f"[ERROR] Scan module failed: {e}")
    if HAS_LCD:
        draw.rectangle((0, 0, W, H), fill=BLACK)
        draw.text((2, 50), "Scan Done", font=font_small, fill=GREEN)
        LCD.LCD_ShowImage(canvas, 0, 0)
        time.sleep(2)

def launch_brute():
    """Launch the brute-force module."""
    print("[INFO] Launching BRUTE module...")
    if HAS_LCD:
        draw.rectangle((0, 0, W, H), fill=BLACK)
        draw.text((2, 50), "Loading Brute...", font=font_small, fill=RED)
        LCD.LCD_ShowImage(canvas, 0, 0)
    try:
        ragnar_brute.main()
    except Exception as e:
        print(f"[ERROR] Brute module failed: {e}")
    if HAS_LCD:
        draw.rectangle((0, 0, W, H), fill=BLACK)
        draw.text((2, 50), "Brute Done", font=font_small, fill=RED)
        LCD.LCD_ShowImage(canvas, 0, 0)
        time.sleep(2)

def launch_wifi():
    """Launch WiFi AP module (placeholder)."""
    print("[INFO] WiFi module not yet implemented")
    if HAS_LCD:
        draw.rectangle((0, 0, W, H), fill=BLACK)
        draw.text((2, 50), "WiFi Coming", font=font_small, fill=YELLOW)
        draw.text((2, 65), "Soon!", font=font_small, fill=YELLOW)
        LCD.LCD_ShowImage(canvas, 0, 0)
        time.sleep(2)

def launch_steal():
    """Launch data stealer module (placeholder)."""
    print("[INFO] Steal module not yet implemented")
    if HAS_LCD:
        draw.rectangle((0, 0, W, H), fill=BLACK)
        draw.text((2, 50), "Steal Coming", font=font_small, fill=CYAN)
        draw.text((2, 65), "Soon!", font=font_small, fill=CYAN)
        LCD.LCD_ShowImage(canvas, 0, 0)
        time.sleep(2)

# Module launcher mapping
MODULE_LAUNCHERS = {
    "scan": launch_scan,
    "brute": launch_brute,
    "wifi": launch_wifi,
    "steal": launch_steal,
}

# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------
def main():
    """Main menu loop."""
    if not HAS_LCD:
        print("Ragnar Menu (headless mode)")
        print("Run individual modules directly:")
        print("  - from ragnar import ragnar; ragnar.main()")
        print("  - from ragnar import ragnar_brute; ragnar_brute.main()")
        return
    
    # Initialize GPIO
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Initial draw
    draw_menu()
    
    while state["running"]:
        # Poll buttons - don't block on get_button
        button = get_button(PINS, GPIO)
        
        if button is not None:
            # Wait for button release
            while get_button(PINS, GPIO) is not None:
                time.sleep(0.05)
            time.sleep(0.1)  # Debounce
            
            if button == "KEY3":
                # Exit
                state["running"] = False
            
            elif button == "UP" or button == "LEFT":
                # Previous option
                state["menu_index"] = (state["menu_index"] - 1) % len(MENU_OPTIONS)
                draw_menu()
            
            elif button == "DOWN" or button == "RIGHT":
                # Next option
                state["menu_index"] = (state["menu_index"] + 1) % len(MENU_OPTIONS)
                draw_menu()
            
            elif button == "OK" or button == "KEY1":
                # Launch selected module
                module = MENU_OPTIONS[state["menu_index"]]["module"]
                launcher = MODULE_LAUNCHERS.get(module)
                if launcher:
                    try:
                        launcher()
                    except ExitToMenu:
                        pass
                draw_menu()
        
        # Slow down the loop a bit for animation
        time.sleep(0.1)
    
    # Cleanup
    if HAS_LCD:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
