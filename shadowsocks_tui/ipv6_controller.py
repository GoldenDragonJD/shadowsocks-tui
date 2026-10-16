"""IPv6 Leak Protection Controller for Linux.
Prevents IPv6 address leaks by installing blackhole/unreachable default routes
and firewall reject rules while preserving loopback (::1).
"""

import shutil
import subprocess
from typing import Tuple

from .tun_controller import TunController


class IPv6Controller:
    """Manages IPv6 leak protection rules and routing."""

    _is_active: bool = False

    @classmethod
    def is_active(cls) -> bool:
        return cls._is_active

    @classmethod
    def enable_leak_protection(cls, sudo_password: str = "") -> Tuple[bool, str]:
        """Enable IPv6 leak protection by blocking external IPv6 routes and traffic."""
        ok, msg = TunController.verify_sudo_access(sudo_password)
        if not ok:
            return False, f"Sudo required for IPv6 leak protection: {msg}"

        messages = []

        routes = [
            ["ip", "-6", "route", "replace", "unreachable", "default", "metric", "1"],
            ["ip", "-6", "route", "replace", "unreachable", "::/1", "metric", "1"],
            ["ip", "-6", "route", "replace", "unreachable", "8000::/1", "metric", "1"],
        ]

        route_success = True
        for r in routes:
            res = TunController.run_sudo(r, sudo_password)
            if res.returncode != 0 and "File exists" not in res.stderr:
                route_success = False

        if route_success:
            messages.append("unreachable routes installed")

        if shutil.which("ip6tables"):
            try:
                check_cmd = [
                    "ip6tables", "-C", "OUTPUT", "!", "-o", "lo", "-j", "REJECT",
                    "--reject-with", "icmp6-adm-prohibited"
                ]
                res_check = TunController.run_sudo(check_cmd, sudo_password)
                if res_check.returncode != 0:
                    add_cmd = [
                        "ip6tables", "-I", "OUTPUT", "!", "-o", "lo", "-j", "REJECT",
                        "--reject-with", "icmp6-adm-prohibited"
                    ]
                    res_add = TunController.run_sudo(add_cmd, sudo_password)
                    if res_add.returncode == 0:
                        messages.append("ip6tables filter active")
            except Exception:
                pass

        cls._is_active = True
        detail = ", ".join(messages) if messages else "active"
        return True, f"IPv6 leak protection enabled ({detail})"

    @classmethod
    def disable_leak_protection(cls, sudo_password: str = "") -> Tuple[bool, str]:
        """Remove IPv6 leak protection rules and restore direct IPv6 connectivity."""
        routes = [
            ["ip", "-6", "route", "del", "unreachable", "default", "metric", "1"],
            ["ip", "-6", "route", "del", "unreachable", "::/1", "metric", "1"],
            ["ip", "-6", "route", "del", "unreachable", "8000::/1", "metric", "1"],
        ]

        for r in routes:
            TunController.run_sudo(r, sudo_password)

        if shutil.which("ip6tables"):
            try:
                del_cmd = [
                    "ip6tables", "-D", "OUTPUT", "!", "-o", "lo", "-j", "REJECT",
                    "--reject-with", "icmp6-adm-prohibited"
                ]
                TunController.run_sudo(del_cmd, sudo_password)
            except Exception:
                pass

        cls._is_active = False
        return True, "IPv6 leak protection disabled (IPv6 restored)"
