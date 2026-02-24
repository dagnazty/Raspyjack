# Ragnar Port to RaspyJack - Implementation Plan

## Overview
Port full Ragnar capabilities to RaspyJack with a lite version for Pi Zero (512MB-1GB RAM).

---

## Current State (What's Done)
- ✅ `ragnar.py` - Basic network scanning + vuln assessment
- ✅ Viking sprite animations (downloaded from Ragnar repo)
- ✅ Auto-scan (2hr period)
- ✅ 4 views: SCAN/HOSTS/VULNS/LOOT

---

## Proposed Architecture

```
payloads/reconnaissance/ragnar/
├── __init__.py           # Package init
├── menu.py               # Main menu / mode selector
├── scan.py               # Network + vuln scanning (current ragnar.py)
├── brute.py              # Brute-force attacks (NEW)
├── steal.py              # File exfiltration (NEW) 
├── wifi.py               # AP mode / captive portal (NEW)
└── intel.py              # CVE/threat intel (NEW)

# Lite variants for Pi Zero:
├── lite/                 # Lite versions
│   ├── scan.py           # Basic nmap only
│   ├── brute.py          # Reduced wordlists
│   └── wifi.py          # No AP mode
```

---

## Feature Breakdown

### 1. SCAN (Network + Vuln Scanning) - Refine
**Current:** Basic nmap ping scan → port scan → vuln scan
**Enhance:**
- [ ] Multiple scan profiles (quick/deep/custom)
- [ ] Add Nmap scripts: vulners, vulscan, discovery
- [ ] Auto-detect best nmap arguments per target
- [ ] Display service version info
- [ ] Save XML + grepable output for parsing

### 2. BRUTE (Brute-Force Attacks) - New
**Ragnar supports:** FTP, SSH, SMB, RDP, Telnet, SQL
**RaspyJack approach:**
- [ ] Service selector menu
- [ ] Built-in small wordlists (top 100 passwords)
- [ ] Hydra integration (if available)
- [ ] Show progress on LCD
- [ ] Auto-stop on found credential

### 3. STEAL (File Exfiltration) - New  
**Ragnar supports:** Grab files from FTP/SMB
**RaspyJack approach:**
- [ ] Target file paths from discovered services
- [ ] Simple HTTP server to receive files
- [ ] Save to loot/Ragnar/files/
- [ ] Display on LCD

### 4. WIFI (AP + Captive Portal) - New
**Ragnar:** Full WiFi AP with web portal
**RaspyJack approach:**
- [ ] Use existing RaspyJack wifi tools
- [ ] Hostapd control
- [ ] Simple captive portal page
- [ ] Credential logging

### 5. INTEL (Threat Intel Display) - New
**Ragnar:** CISA KEV, NVD, AlienVault OTX
**RaspyJack Lite approach:**
- [ ] Parse CVE data from Nmap scan results
- [ ] Display severity badges (CRIT/HIGH/MED/LOW)
- [ ] Cache last 50 CVEs locally
- [ ] No external API (lite version)

---

## Hardware Tiers

### Tier 1: Pi Zero W/W2 (512MB-1GB RAM) - "LITE"
- Basic nmap scans only
- No brute-force (memory)
- No file steal
- No WiFi AP (use existing)
- Simplified CVE display

### Tier 2: Pi 3/4 (2-4GB RAM) - "STANDARD"
- Full scanning + vuln assessment  
- Brute-force with small wordlists
- File steal from FTP/SMB
- WiFi AP mode
- Basic CVE display

### Tier 3: Pi 5 / Server (8GB+ RAM) - "FULL"
- Everything in STANDARD
- Large wordlists
- Real-time traffic analysis (if enabled)
- Full threat intel from APIs
- Advanced vuln scanning (Nuclei, Nikto)

---

## Menu Structure

```
[RAGNAR - MAIN MENU]
> NETWORK SCAN      (KEY1)
  BRUTE FORCE       (KEY2)
  FILE STEAL        (KEY3)
  WIFI AP          (LEFT)
  THREAT INTEL     (RIGHT)
  EXIT             (KEY3 hold)
```

---

## Implementation Priority

1. **Phase 1:** Refine current ragnar.py (scan.py)
2. **Phase 2:** Add brute.py module
3. **Phase 3:** Add steal.py module
4. **Phase 4:** Add wifi.py module
5. **Phase 5:** Add intel.py module
6. **Phase 6:** Create lite/ variants

---

## Next Step

Start with **Phase 1** - refine current scan.py

