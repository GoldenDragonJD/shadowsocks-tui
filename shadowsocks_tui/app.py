"""Main Application for Shadowsocks TUI Client.
Built with uibuilder framework.
Provides connection toggle, TUN/System mode toggle, IPv6 leak protection,
sudo handling, and persistent configuration saving on successful connection.
"""

import threading
from typing import Optional

from uibuilder import Label, UIBuilder

from .config_manager import has_saved_config, load_config
from .tun_controller import TunController
from .ui_components import ActionButton, BackgroundFrame, FormInput
from .vpn_manager import VPNManager


class ShadowsocksApp:
    """TUI Application controller for Shadowsocks Client."""

    def __init__(self):
        # 1. Initialize UIBuilder (80 columns x 24 rows)
        self.ui = UIBuilder(grid_size_x=80, grid_size_y=24)
        self.vpn = VPNManager()

        # 2. Load persistent configuration
        self.saved_cfg = load_config()
        self.vpn.mode = self.saved_cfg.get("mode", "system")
        self.vpn.ipv6_leak_protection = bool(self.saved_cfg.get("ipv6_leak_protection", True))

        # 3. Build UI Elements
        self._build_ui()

        # 4. Remove UIBuilder self from interactive elements for seamless Tab navigation
        if self.ui in self.ui.interactice_elements:
            self.ui.interactice_elements.remove(self.ui)

        # 5. Populate initial values from config
        self._load_saved_values()

        # Track previous states to avoid unnecessary redraws
        self._last_status = None
        self._last_mode = None
        self._last_msg = ""
        self._last_uptime = ""
        self._last_ping = None

    def _build_ui(self) -> None:
        """Construct the visual layout of the TUI."""
        # Layer 0: Frame & Static Dividers
        self.frame = BackgroundFrame(self.ui)
        self.ui.add_ui_element(self.frame)

        # Row 1: Title Header Banner
        title_text = "★  SHADOWSOCKS TUI CLIENT  ★"
        self.title_lbl = Label(self.ui, 2, 1, title_text.center(76))
        self.ui.add_ui_element(self.title_lbl)

        # Row 3: Live Status Summary
        self.summary_lbl = Label(self.ui, 2, 3, " Status: ○ DISCONNECTED  │ Mode: [SYSTEM]  │ IPv6: BLOCKED  │ Ping: -- ms ")
        self.ui.add_ui_element(self.summary_lbl)

        # Row 6: Input Field Labels (Row 1)
        lbl_r1 = "  Server IP / Host:".ljust(41) + "Port:".ljust(12) + "Cipher Method:"
        self.lbl_row1 = Label(self.ui, 4, 6, lbl_r1)
        self.ui.add_ui_element(self.lbl_row1)

        # Row 7-9: Inputs (Row 1)
        self.ip_input = FormInput(
            self.ui, 4, 7, size=38, placeholder="e.g. 198.51.100.4 or vpn.example.com",
            on_enter_next=self._advance_focus
        )
        self.port_input = FormInput(
            self.ui, 45, 7, size=9, placeholder="8388",
            on_enter_next=self._advance_focus
        )
        self.method_input = FormInput(
            self.ui, 57, 7, size=18, placeholder="aes-256-gcm",
            on_enter_next=self._advance_focus
        )
        self.ui.add_ui_element(self.ip_input)
        self.ui.add_ui_element(self.port_input)
        self.ui.add_ui_element(self.method_input)

        # Row 10: Input Field Labels (Row 2)
        lbl_r2 = "  Server Password:".ljust(41) + "Sudo Password (for TUN Mode):"
        self.lbl_row2 = Label(self.ui, 4, 10, lbl_r2)
        self.ui.add_ui_element(self.lbl_row2)

        # Row 11-13: Inputs (Row 2)
        self.pass_input = FormInput(
            self.ui, 4, 11, size=38, placeholder="Enter shadowsocks password",
            is_password=True, on_enter_next=self._advance_focus
        )
        self.sudo_input = FormInput(
            self.ui, 45, 11, size=30, placeholder=self._get_sudo_placeholder(),
            is_password=True, on_enter_next=self._advance_focus
        )
        self.ui.add_ui_element(self.pass_input)
        self.ui.add_ui_element(self.sudo_input)

        # Row 15-17: Action Buttons (5 buttons nicely spaced across 76 columns)
        self.btn_connect = ActionButton(
            self.ui, 3, 15, "[ CONNECT ]", self._on_connect_toggle, width=11
        )
        mode_btn_text = "[MODE: SYSTEM]" if self.vpn.mode == "system" else "[MODE: TUN VPN]"
        self.btn_mode = ActionButton(
            self.ui, 17, 15, mode_btn_text, self._on_mode_toggle, width=15
        )
        ipv6_btn_text = "[IPv6: BLOCKED]" if self.vpn.ipv6_leak_protection else "[IPv6: ALLOWED]"
        self.btn_ipv6 = ActionButton(
            self.ui, 35, 15, ipv6_btn_text, self._on_ipv6_toggle, width=15
        )
        self.btn_ping = ActionButton(
            self.ui, 53, 15, "[ PING ]", self._on_ping_click, width=9
        )
        self.btn_quit = ActionButton(
            self.ui, 65, 15, "[ QUIT ]", self._on_quit_click, width=9
        )
        self.ui.add_ui_element(self.btn_connect)
        self.ui.add_ui_element(self.btn_mode)
        self.ui.add_ui_element(self.btn_ipv6)
        self.ui.add_ui_element(self.btn_ping)
        self.ui.add_ui_element(self.btn_quit)

        # Row 19: Mode Description
        self.mode_desc_lbl = Label(self.ui, 4, 19, self._get_mode_description())
        self.ui.add_ui_element(self.mode_desc_lbl)

        # Row 20: Live Status / Error Message
        self.msg_lbl = Label(self.ui, 4, 20, "Status: Ready. Press TAB to navigate fields.")
        self.ui.add_ui_element(self.msg_lbl)

        # Row 22: Controls & Help Guide
        help_text = "[TAB] Navigate  │  [ENTER] Activate/Select  │  [ESC] Exit Client"
        self.help_lbl = Label(self.ui, 4, 22, help_text)
        self.ui.add_ui_element(self.help_lbl)

    def _get_sudo_placeholder(self) -> str:
        """Determine appropriate placeholder text for sudo password field."""
        if TunController.is_root():
            return "Root user (Full TUN access)"
        if TunController.has_passwordless_sudo():
            return "Passwordless sudo active"
        if self.vpn.mode == "system":
            return "Not required for System mode"
        return "Enter sudo password"

    def _get_mode_description(self) -> str:
        """Return human-readable explanation of current mode and IPv6 guard."""
        ipv6_desc = "IPv6 Blocked (Protected)" if self.vpn.ipv6_leak_protection else "IPv6 Allowed"
        if self.vpn.mode == "system":
            return f"Mode: SYSTEM PROXY  │  SOCKS5 127.0.0.1:1080 (No root)  │  {ipv6_desc}"
        return f"Mode: TUN (VPN)     │  Full system routing via sstun0  │  {ipv6_desc}"

    def _load_saved_values(self) -> None:
        """Pre-populate inputs with loaded values so user only enters IP and Port once."""
        if self.saved_cfg.get("server"):
            self.ip_input.value = str(self.saved_cfg.get("server", ""))
        if self.saved_cfg.get("server_port"):
            self.port_input.value = str(self.saved_cfg.get("server_port", "8388"))
        if self.saved_cfg.get("password"):
            self.pass_input.value = str(self.saved_cfg.get("password", ""))
        if self.saved_cfg.get("method"):
            self.method_input.value = str(self.saved_cfg.get("method", "aes-256-gcm"))

        if has_saved_config():
            self.msg_lbl.text = "Loaded saved configuration from config.json. Ready to connect."

    def _advance_focus(self, current_element: FormInput) -> None:
        """Advance focus to the next interactive element on Enter."""
        self.ui.cycle()
        while not self.ui.interactice_elements[0].is_active:
            self.ui.cycle()

    def _on_connect_toggle(self, btn: ActionButton) -> None:
        """Toggle connection on/off."""
        if self.vpn.is_connected:
            btn.set_label("[DISCONNECTING]")
            self.vpn.disconnect_async(callback=self._on_disconnected)
        elif not self.vpn.is_connecting:
            btn.set_label("[CONNECTING...]")
            server = self.ip_input.value
            port_str = self.port_input.value
            password = self.pass_input.value
            method = self.method_input.value or "aes-256-gcm"
            sudo_pass = self.sudo_input.value

            try:
                port = int(port_str)
            except ValueError:
                port = 8388

            self.vpn.connect_async(
                server=server,
                port=port,
                password=password,
                method=method,
                mode=self.vpn.mode,
                sudo_password=sudo_pass,
                callback=self._on_connect_result,
            )

    def _on_connect_result(self, success: bool, message: str) -> None:
        """Callback invoked when connection attempt completes."""
        pass  # Real-time state handled in tick loop

    def _on_disconnected(self) -> None:
        """Callback invoked when disconnection completes."""
        pass

    def _on_mode_toggle(self, btn: ActionButton) -> None:
        """Toggle between System Mode and TUN Mode."""
        new_mode = self.vpn.toggle_mode()
        if new_mode == "system":
            btn.set_label("[MODE: SYSTEM]")
        else:
            btn.set_label("[MODE: TUN VPN]")

        self.sudo_input.placeholder = self._get_sudo_placeholder()
        self.mode_desc_lbl.text = self._get_mode_description()

        if self.vpn.is_connected:
            self.vpn.status_message = f"Switched mode to {new_mode.upper()}. Reconnect to apply."
        else:
            self.vpn.status_message = f"Active mode set to {new_mode.upper()}."

    def _on_ipv6_toggle(self, btn: ActionButton) -> None:
        """Toggle IPv6 leak protection on/off."""
        is_blocked = self.vpn.toggle_ipv6_leak_protection()
        if is_blocked:
            btn.set_label("[IPv6: BLOCKED]")
            self.vpn.status_message = "IPv6 Leak Guard: BLOCKED (Blackhole route & firewall prevent IPv6 leaks)."
        else:
            btn.set_label("[IPv6: ALLOWED]")
            self.vpn.status_message = "IPv6 Leak Guard: ALLOWED (Warning: IPv6 traffic will bypass proxy)."
        self.mode_desc_lbl.text = self._get_mode_description()

    def _on_ping_click(self, btn: ActionButton) -> None:
        """Test latency to current server."""
        btn.set_label("[PINGING...]")

        def _ping_worker():
            lat = self.vpn.measure_latency()
            if lat is not None:
                self.msg_lbl.text = f"Ping response: {lat} ms to {self.vpn.server}:{self.vpn.server_port}"
            else:
                self.msg_lbl.text = "Ping failed: server unreachable or timeout."
            btn.set_label("[ PING ]")

        threading.Thread(target=_ping_worker, daemon=True).start()

    def _on_quit_click(self, btn: ActionButton) -> None:
        """Exit the client and restore network settings."""
        self.vpn.disconnect_sync()
        self.ui.ExitLoop()

    def tick(self) -> None:
        """Main loop periodic update callback (runs every iteration)."""
        # 1. Update Connection Status
        status = self.vpn.status
        mode = self.vpn.mode
        uptime = self.vpn.uptime_str
        ping_val = self.vpn.ping_ms
        msg = self.vpn.status_message

        # Update Connect button text
        if status == VPNManager.STATUS_CONNECTED:
            self.btn_connect.set_label("[DISCONNECT]")
            status_badge = "● CONNECTED"
        elif status == VPNManager.STATUS_CONNECTING:
            self.btn_connect.set_label("[CONNECTING]")
            status_badge = "⌛ CONNECTING"
        elif status == VPNManager.STATUS_ERROR:
            self.btn_connect.set_label("[RECONNECT]")
            status_badge = "✗ ERROR"
        else:
            self.btn_connect.set_label("[ CONNECT ]")
            status_badge = "○ DISCONNECTED"

        # Update Mode button text
        if mode == "system":
            self.btn_mode.set_label("[MODE: SYSTEM]")
        else:
            self.btn_mode.set_label("[MODE: TUN VPN]")

        # Update IPv6 Leak button text
        if self.vpn.ipv6_leak_protection:
            self.btn_ipv6.set_label("[IPv6: BLOCKED]")
            ipv6_badge = "IPv6: BLOCKED"
        else:
            self.btn_ipv6.set_label("[IPv6: ALLOWED]")
            ipv6_badge = "IPv6: ALLOWED"

        # Update summary label
        ping_str = f"{ping_val} ms" if ping_val is not None else "-- ms"
        mode_badge = "SYSTEM" if mode == "system" else "TUN VPN"
        summary = f" Status: {status_badge}  │ Mode: [{mode_badge}]  │ {ipv6_badge}  │ Ping: {ping_str}  │ Up: {uptime}"
        self.summary_lbl.text = summary

        # Update status message if changed
        if msg != self._last_msg:
            self.msg_lbl.text = f"Status: {msg}"
            self._last_msg = msg

        # Update mode description
        self.mode_desc_lbl.text = self._get_mode_description()

    def run(self) -> None:
        """Run the TUI event loop."""
        try:
            self.ui.Loop(self.tick)
        finally:
            self.vpn.disconnect_sync()


def main():
    app = ShadowsocksApp()
    app.run()


if __name__ == "__main__":
    main()
