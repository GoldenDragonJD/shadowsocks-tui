"""System Proxy Controller for Linux Desktop Environments.
Supports KDE Plasma (kwriteconfig6/5) and GNOME (gsettings).
Allows turning system proxy on and off with a single toggle without requiring root.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


def get_env_script_path() -> Path:
    xdg_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "shadowsocks-tui"
    try:
        xdg_dir.mkdir(parents=True, exist_ok=True)
        return xdg_dir / "proxy_env.sh"
    except Exception:
        return Path("proxy_env.sh").resolve()


class ProxyController:
    """Manages system proxy settings for Linux desktop and shell environments."""

    @staticmethod
    def is_kde() -> bool:
        return bool(shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5"))

    @staticmethod
    def is_gnome() -> bool:
        return bool(shutil.which("gsettings"))

    @classmethod
    def enable_proxy(cls, host: str = "127.0.0.1", port: int = 1080) -> Tuple[bool, str]:
        """Configure and enable system proxy."""
        messages = []
        success = False

        # 1. KDE Plasma (kwriteconfig6 / kwriteconfig5)
        kwrite = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
        if kwrite:
            try:
                # ProxyType 1 = Manual Proxy Configuration
                subprocess.run([kwrite, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType", "1", "--notify"], check=True, capture_output=True)
                subprocess.run([kwrite, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "socksProxy", f"socks://{host}:{port}", "--notify"], check=True, capture_output=True)
                messages.append("KDE proxy configured")
                success = True
            except Exception as e:
                messages.append(f"KDE proxy error: {e}")

        # 2. GNOME / GTK (gsettings)
        if shutil.which("gsettings"):
            try:
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"], check=True, capture_output=True)
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy.socks", "host", host], check=True, capture_output=True)
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy.socks", "port", str(port)], check=True, capture_output=True)
                messages.append("GNOME proxy configured")
                success = True
            except Exception as e:
                if not success:
                    messages.append(f"GNOME proxy error: {e}")

        # 3. Create helper shell script for terminal proxy
        try:
            env_path = get_env_script_path()
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"""# Run: source {env_path}
export http_proxy="socks5://{host}:{port}"
export https_proxy="socks5://{host}:{port}"
export all_proxy="socks5://{host}:{port}"
export no_proxy="localhost,127.0.0.1,localaddress,.localdomain.com"
echo "Terminal proxy enabled: socks5://{host}:{port}"
""")
            os.chmod(env_path, 0o755)
            messages.append("Shell proxy script generated")
            success = True
        except Exception:
            pass

        if success:
            return True, f"System proxy enabled ({', '.join(messages)})"
        return False, "No desktop proxy manager detected (KDE/GNOME)"

    @classmethod
    def disable_proxy(cls) -> Tuple[bool, str]:
        """Disable system proxy and restore direct internet connection."""
        messages = []

        # 1. KDE Plasma
        kwrite = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
        if kwrite:
            try:
                # ProxyType 0 = No Proxy (Direct Connection)
                subprocess.run([kwrite, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType", "0", "--notify"], check=True, capture_output=True)
                messages.append("KDE proxy cleared")
            except Exception as e:
                messages.append(f"KDE clear error: {e}")

        # 2. GNOME
        if shutil.which("gsettings"):
            try:
                subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"], check=True, capture_output=True)
                messages.append("GNOME proxy cleared")
            except Exception as e:
                pass

        # 3. Update helper shell script
        try:
            env_path = get_env_script_path()
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("""# Terminal proxy unset
unset http_proxy https_proxy all_proxy no_proxy
echo "Terminal proxy disabled"
""")
            os.chmod(env_path, 0o755)
        except Exception:
            pass

        return True, "System proxy disabled (Direct connection restored)"
