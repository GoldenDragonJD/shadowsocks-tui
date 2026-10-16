"""TUN Controller for Shadowsocks VPN.
Handles privileged Linux routing commands, TUN network device lifecycle,
gateway detection, bypass host routes, and sudo access.
"""

import json
import os
import socket
import subprocess
from typing import Optional, Tuple


class TunController:
    """Manages TUN mode routing, interface lifecycle, and sudo operations."""

    @staticmethod
    def is_root() -> bool:
        """Check if currently running with effective UID 0."""
        return os.geteuid() == 0

    @staticmethod
    def has_passwordless_sudo() -> bool:
        """Check if passwordless sudo is configured and active."""
        if os.geteuid() == 0:
            return True
        res = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True)
        return res.returncode == 0

    @classmethod
    def verify_sudo_access(cls, sudo_password: str = "") -> Tuple[bool, str]:
        """Verify whether sudo commands can be executed with or without password."""
        if cls.is_root():
            return True, "Running as root"
        if cls.has_passwordless_sudo():
            return True, "Passwordless sudo active"
        if not sudo_password:
            return False, "Sudo password required for TUN mode"

        # Validate password with sudo -S -v
        p = subprocess.run(
            ["sudo", "-S", "-v"],
            input=f"{sudo_password}\n",
            capture_output=True,
            text=True,
        )
        if p.returncode == 0:
            return True, "Sudo authenticated successfully"
        return False, "Incorrect sudo password"

    @classmethod
    def run_sudo(cls, cmd: list[str], sudo_password: str = "") -> subprocess.CompletedProcess:
        """Run a command with elevated privileges."""
        if cls.is_root():
            return subprocess.run(cmd, capture_output=True, text=True)
        if sudo_password:
            return subprocess.run(
                ["sudo", "-S"] + cmd,
                input=f"{sudo_password}\n",
                capture_output=True,
                text=True,
            )
        return subprocess.run(["sudo", "-n"] + cmd, capture_output=True, text=True)

    @classmethod
    def spawn_sudo(
        cls, cmd: list[str], sudo_password: str = ""
    ) -> subprocess.Popen:
        """Spawn a background process with elevated privileges."""
        if cls.is_root():
            return subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        if sudo_password:
            cls.run_sudo(["-v"], sudo_password)
            proc = subprocess.Popen(
                ["sudo", "-S"] + cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                proc.stdin.write(f"{sudo_password}\n")
                proc.stdin.flush()
            except Exception:
                pass
            return proc
        return subprocess.Popen(
            ["sudo", "-n"] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    @staticmethod
    def get_default_gateway_and_interface() -> Tuple[Optional[str], Optional[str]]:
        """Retrieve default gateway IP and outbound physical interface name."""
        try:
            res = subprocess.run(
                ["ip", "-j", "route", "show", "default"],
                capture_output=True,
                text=True,
                check=True,
            )
            routes = json.loads(res.stdout)
            if routes and isinstance(routes, list):
                for route in routes:
                    gw = route.get("gateway")
                    dev = route.get("dev")
                    if gw and dev:
                        return gw, dev
        except Exception:
            pass

        # Fallback to parsing standard `ip route show default`
        try:
            res = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                check=True,
            )
            tokens = res.stdout.strip().split()
            gw, dev = None, None
            if "via" in tokens:
                gw = tokens[tokens.index("via") + 1]
            if "dev" in tokens:
                dev = tokens[tokens.index("dev") + 1]
            return gw, dev
        except Exception:
            pass

        return None, None

    @staticmethod
    def resolve_ip(host: str) -> Optional[str]:
        """Resolve a hostname or return the IP directly."""
        try:
            return socket.gethostbyname(host)
        except Exception:
            return None

    @classmethod
    def setup_tun_interface_and_routes(
        cls,
        server_host: str,
        tun_name: str = "sstun0",
        sudo_password: str = "",
    ) -> Tuple[bool, str]:
        """Configure bypass routes and global default routing via TUN interface."""
        gw, dev = cls.get_default_gateway_and_interface()
        if not gw or not dev:
            return False, "Failed to detect physical default gateway and interface"

        resolved_ip = cls.resolve_ip(server_host)
        if not resolved_ip:
            return False, f"Could not resolve server host '{server_host}'"

        # 1. Add bypass host route so Shadowsocks traffic doesn't loop into the tunnel
        res = cls.run_sudo(
            ["ip", "route", "replace", resolved_ip, "via", gw, "dev", dev],
            sudo_password,
        )
        if res.returncode != 0:
            return False, f"Failed to add bypass route to server: {res.stderr.strip()}"

        # 2. Bring tun link up
        cls.run_sudo(["ip", "link", "set", "dev", tun_name, "up"], sudo_password)

        # 3. Add 0.0.0.0/1 and 128.0.0.0/1 to direct all internet traffic through tun interface
        r1 = cls.run_sudo(
            ["ip", "route", "replace", "0.0.0.0/1", "dev", tun_name], sudo_password
        )
        r2 = cls.run_sudo(
            ["ip", "route", "replace", "128.0.0.0/1", "dev", tun_name], sudo_password
        )

        if r1.returncode != 0 or r2.returncode != 0:
            err = (r1.stderr + " " + r2.stderr).strip()
            return False, f"Failed to add TUN default routes: {err}"

        return True, f"TUN routes established via {tun_name} (Physical: {dev})"

    @classmethod
    def cleanup_tun_routes_and_interface(
        cls,
        server_host: str = "",
        tun_name: str = "sstun0",
        sudo_password: str = "",
    ) -> None:
        """Tear down TUN routes, delete bypass host route, and delete the interface."""
        cls.run_sudo(["ip", "route", "del", "0.0.0.0/1", "dev", tun_name], sudo_password)
        cls.run_sudo(["ip", "route", "del", "128.0.0.0/1", "dev", tun_name], sudo_password)

        if server_host:
            resolved_ip = cls.resolve_ip(server_host)
            if resolved_ip:
                cls.run_sudo(["ip", "route", "del", resolved_ip], sudo_password)

        cls.run_sudo(["ip", "link", "set", "dev", tun_name, "down"], sudo_password)
        cls.run_sudo(["ip", "link", "del", tun_name], sudo_password)

    @classmethod
    def kill_process(cls, pid: int, sudo_password: str = "") -> None:
        """Terminate a process by PID with elevated permissions if needed."""
        try:
            if cls.is_root():
                os.kill(pid, 15)  # SIGTERM
            else:
                cls.run_sudo(["kill", "-15", str(pid)], sudo_password)
        except Exception:
            pass
