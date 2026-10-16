# Shadowsocks TUI Client

A fast, modern, and lightweight terminal user interface (TUI) Shadowsocks VPN client built with the **`uibuilder`** framework. It features single-toggle connection, seamless switching between **System Mode** and **TUN Mode**, built-in **IPv6 Leak Protection**, secure credential persistence, and flexible privilege escalation on Linux.

---

## Features

- **Simple Toggle Connection**: Connect and disconnect with a single button press or `Enter` keystroke.
- **Dual Routing Modes**:
  - **System Proxy Mode**: Starts `sslocal` in SOCKS5/HTTP mode on `127.0.0.1:1080` and automatically configures your desktop environment proxy settings (supporting KDE Plasma via `kwriteconfig6`/`5` and GNOME via `gsettings`). Automatically restores direct internet access upon disconnection. *Does not require root.*
  - **TUN Mode (Full-System VPN)**: Allocates a virtual Layer 3 TUN adapter (`sstun0`) and configures system routing tables (`ip route`) using `/1` split routing (`0.0.0.0/1` and `128.0.0.0/1`) with automatic server bypass. Captures and routes all network traffic (terminals, games, background services, Docker). *Requires sudo privileges.*
- **Built-in IPv6 Leak Protection**:
  - Prevents your ISP-assigned IPv6 address from leaking when communicating with dual-stack servers.
  - Deploys high-priority unreachable blackhole routes (`unreachable default metric 1`, `::/1`, `8000::/1`) and firewall reject filters (`ip6tables ! -o lo`) while preserving local loopback (`::1`).
  - Can be toggled on/off at any time with the dedicated **`[IPv6: BLOCKED]`** / **`[IPv6: ALLOWED]`** button.
- **Single-Entry Credential Persistence**:
  - Enter your server IP, port, password, and cipher method once.
  - Once connection is verified, settings are securely saved to `~/.config/shadowsocks-tui/config.json` (with `0600` permissions).
  - Next time you open the client, your configuration is prefilled so you can connect immediately.
- **Flexible Sudo Access for TUN Mode**:
  1. **In-TUI Password Input**: Enter your user password in the masked field; the client validates and refreshes privileges via `sudo -S -v`.
  2. **Direct Root Launch**: Launch directly with root privileges (`sudo shadowsocks-tui` or `sudo ./run.sh`) for completely promptless operation.
  3. **One-Time Passwordless Sudo Rule**: Run `sudo bash scripts/setup_sudoers.sh` to allow passwordless execution of `/usr/bin/sslocal`, `/usr/bin/ip`, `/usr/bin/ip6tables`, and `/usr/bin/sysctl`.
- **Live Diagnostics**:
  - Real-time status indicators (`● CONNECTED`, `○ DISCONNECTED`, `⌛ CONNECTING`, `✗ ERROR`).
  - Active IPv6 shield badge (`IPv6: BLOCKED` / `IPv6: ALLOWED`).
  - Latency probe button (`[ PING ]`).
  - Active session uptime counter.
- **Clean Network Teardown**:
  - Registers `atexit` and signal handlers (`SIGINT`, `SIGTERM`) to guarantee that routing tables, tun interfaces, and system proxy settings are cleanly restored if the application exits.

---

## Visual Preview

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│                        ★  SHADOWSOCKS TUI CLIENT  ★                          │
├──────────────────────────────────────────────────────────────────────────────┤
│  Status: ○ DISCONNECTED  │ Mode: [TUN VPN]  │ IPv6: BLOCKED  │ Ping: -- ms   │
├──────────────────────────────────────────────────────────────────────────────┤
│   [ SERVER CONFIGURATION ]                                                   │
│     Server IP / Host:                      Port:       Cipher Method:        │
│   ┌──────────────────────────────────────┐ ┌─────────┐ ┌──────────────────┐  │
│   │198.51.100.4                          │ │8388     │ │aes-256-gcm       │  │
│   └──────────────────────────────────────┘ └─────────┘ └──────────────────┘  │
│     Server Password:                       Sudo Password (for TUN Mode):     │
│   ┌──────────────────────────────────────┐ ┌──────────────────────────────┐  │
│   │••••••••••••••••••••••••••••••••••••••│ │••••••••••••••••••••••••••••••│  │
│   └──────────────────────────────────────┘ └──────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────┤
│  ╭───────────╮ ╭───────────────╮ ╭───────────────╮ ╭─────────╮ ╭─────────╮   │
│  │[ CONNECT ]│ │[MODE: TUN VPN]│ │[IPv6: BLOCKED]│ │ [ PING ]│ │ [ QUIT ]│   │
│  ╰───────────╯ ╰───────────────╯ ╰───────────────╯ ╰─────────╯ ╰─────────╯   │
├──────────────────────────────────────────────────────────────────────────────┤
│   Mode: TUN (VPN)     │  Full system routing via sstun0  │  IPv6 Blocked     │
│   Status: Ready. Configure server and click Connect.                         │
├──────────────────────────────────────────────────────────────────────────────┤
│   [TAB] Navigate  │  [ENTER] Activate/Select  │  [ESC] Exit Client           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## Installation

### Prerequisites

- **Linux** (tested on Arch Linux, KDE Plasma, GNOME, Ubuntu/Debian, Fedora)
- **Python 3.10+**
- **shadowsocks-rust** (`sslocal`):
  - Arch Linux: `sudo pacman -S shadowsocks-rust`
  - Debian/Ubuntu: `sudo apt install shadowsocks-rust` or install via Cargo: `cargo install shadowsocks-rust`
  - Binary must be accessible in your `$PATH` (typically `/usr/bin/sslocal`).

---

### Option 1: Install with `pipx` (Recommended)

Install directly from GitHub into an isolated environment:

```bash
pipx install git+https://github.com/GoldenDragonJD/shadowsocks-tui.git
```

Or install from a local clone:

```bash
git clone https://github.com/GoldenDragonJD/shadowsocks-tui.git
cd shadowsocks-tui
pipx install .
```

Once installed, you can launch the client from any terminal:

```bash
shadowsocks-tui
# or using the shortcut:
sstui
```

To upgrade in the future:
```bash
pipx upgrade shadowsocks-tui
```

---

### Option 2: Run from Source / Virtual Environment

```bash
git clone https://github.com/GoldenDragonJD/shadowsocks-tui.git
cd shadowsocks-tui

python3 -m venv venv
./venv/bin/pip install -e .

# Launch using the runner script:
./run.sh
```

---

## Quickstart Guide

1. **Launch the Client**:
   ```bash
   shadowsocks-tui
   # or
   ./run.sh
   ```
2. **Enter Server Credentials**:
   - Use **`[TAB]`** to navigate between fields.
   - Enter your **Server IP or Domain** (e.g., `198.51.100.4` or `vpn.example.com`).
   - Enter your **Port** (default: `8388`).
   - Enter your **Cipher Method** (default: `aes-256-gcm`).
   - Enter your **Server Password**.
3. **Choose Your Mode**:
   - Use **`[TAB]`** to select the Mode button.
   - Press **`[ENTER]`** to toggle between:
     - **`[MODE: SYSTEM]`**: Standard SOCKS5 desktop proxy (no root required).
     - **`[MODE: TUN VPN]`**: Full system network tunnel (routes all apps, requires sudo).
4. **Connect**:
   - Select **`[ CONNECT ]`** and press **`[ENTER]`**.
   - Upon successful connection, your configuration is saved to `~/.config/shadowsocks-tui/config.json`.
   - The button label updates to **`[● DISCONNECT]`** and the status bar displays **`● CONNECTED`**.

---

## Sudo Access for TUN Mode

Creating a Layer 3 TUN interface (`sstun0`) and modifying kernel routing tables requires elevated permissions. You can use any of the following approaches:

### 1. In-TUI Password Input (Default)
Enter your Linux sudo password into the **Sudo Password** input field in the TUI. When connecting in TUN mode, it securely authenticates via `sudo -S -v` without leaving the terminal UI.

### 2. Run as Root
Launch the application directly with sudo:
```bash
sudo shadowsocks-tui
# or
sudo ./run.sh
```
The client detects root access (`os.geteuid() == 0`) and automatically skips password prompts.

### 3. Passwordless Sudo Setup (Recommended for seamless use)
Run the included helper script once:
```bash
sudo bash scripts/setup_sudoers.sh
```
This generates `/etc/sudoers.d/shadowsocks-tun`, allowing your user to run `/usr/bin/sslocal`, `/usr/bin/ip`, `/usr/bin/ip6tables`, and `/usr/bin/sysctl` without entering a password.

---

## Keyboard Controls

| Key | Action |
| :--- | :--- |
| **`TAB`** | Advance focus to next input field or button |
| **`ENTER`** | Activate focused button, or advance to next input field |
| **`BACKSPACE`** / **`DELETE`** | Delete character before / after cursor |
| **`LEFT`** / **`RIGHT`** | Move cursor horizontally within input field |
| **`HOME`** / **`END`** | Move cursor to beginning / end of input field |
| **`ESC`** | Cleanly disconnect VPN and exit client |

---

## Configuration File

The configuration file is stored at:
- **`~/.config/shadowsocks-tui/config.json`** (standard XDG path)
- Or `./config.json` if run locally from a repository folder.

Example format:
```json
{
    "server": "198.51.100.4",
    "server_port": 8388,
    "password": "your_secret_password",
    "method": "aes-256-gcm",
    "mode": "tun",
    "local_port": 1080,
    "tun_interface": "sstun0",
    "tun_address": "10.255.0.2/24",
    "ipv6_leak_protection": true
}
```

---

## Repository Structure

```text
shadowsocks-tui/
├── pyproject.toml              # Build specification for pipx and pip
├── README.md                   # Project documentation
├── LICENSE                     # MIT License
├── run.sh                      # Shell launch script
├── main.py                     # Entry point for direct execution
├── scripts/
│   └── setup_sudoers.sh        # Setup script for passwordless TUN & IPv6 rules
└── shadowsocks_tui/            # Core package
    ├── __init__.py
    ├── app.py                  # Main TUI interface & event loop
    ├── config_manager.py       # Configuration persistence (XDG standard)
    ├── ipv6_controller.py      # IPv6 leak guard (blackhole routes & firewall)
    ├── main.py                 # Package CLI entrypoint
    ├── proxy_controller.py     # System proxy manager (KDE Plasma & GNOME)
    ├── tun_controller.py       # TUN adapter lifecycle & Linux routing
    ├── ui_components.py        # Custom uibuilder widgets (FormInput, ActionButton)
    └── vpn_manager.py          # Process manager & connection orchestration
```

---

## License

This project is licensed under the [MIT License](LICENSE) © 2026 GoldenDragonJD.
