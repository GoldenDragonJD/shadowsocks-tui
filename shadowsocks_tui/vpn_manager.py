"""VPN Connection Manager.
Orchestrates sslocal process lifecycle, system proxy, TUN device routing,
connectivity probes, latency testing, and auto-saving configuration on success.
"""

import atexit
import socket
import subprocess
import threading
import time
from typing import Callable, Optional

from .config_manager import save_config
from .ipv6_controller import IPv6Controller
from .proxy_controller import ProxyController
from .tun_controller import TunController


class VPNManager:
    """Manages Shadowsocks client connection state and background operations."""

    STATUS_DISCONNECTED = "DISCONNECTED"
    STATUS_CONNECTING = "CONNECTING"
    STATUS_CONNECTED = "CONNECTED"
    STATUS_ERROR = "ERROR"

    def __init__(self):
        self.status = self.STATUS_DISCONNECTED
        self.mode = "system"  # "system" or "tun"
        self.ipv6_leak_protection = True
        self.server = ""
        self.server_port = 8388
        self.password = ""
        self.method = "aes-256-gcm"
        self.sudo_password = ""
        self.local_port = 1080
        self.tun_name = "sstun0"
        self.tun_address = "10.255.0.2/24"

        self.process: Optional[subprocess.Popen] = None
        self.connected_at: Optional[float] = None
        self.last_error: str = ""
        self.status_message: str = "Ready. Configure server and click Connect."
        self.ping_ms: Optional[float] = None

        self._monitor_running = False
        self._lock = threading.Lock()

        # Register cleanup on abnormal exit
        atexit.register(self.disconnect_sync)

    @property
    def is_connected(self) -> bool:
        return self.status == self.STATUS_CONNECTED

    @property
    def is_connecting(self) -> bool:
        return self.status == self.STATUS_CONNECTING

    @property
    def uptime_str(self) -> str:
        if not self.is_connected or not self.connected_at:
            return "00:00:00"
        elapsed = int(time.time() - self.connected_at)
        hours = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        return f"{hours:02d}:{mins:02d}:{secs:02d}"

    def set_mode(self, new_mode: str) -> None:
        """Switch between 'system' and 'tun' mode."""
        if new_mode in ("system", "tun"):
            self.mode = new_mode

    def toggle_mode(self) -> str:
        """Toggle mode between system and tun."""
        self.mode = "tun" if self.mode == "system" else "system"
        return self.mode

    def toggle_ipv6_leak_protection(self) -> bool:
        """Toggle IPv6 leak protection setting, applying/reverting immediately if connected."""
        self.ipv6_leak_protection = not self.ipv6_leak_protection
        if self.is_connected:
            if self.ipv6_leak_protection:
                IPv6Controller.enable_leak_protection(self.sudo_password)
            else:
                IPv6Controller.disable_leak_protection(self.sudo_password)
        return self.ipv6_leak_protection

    def test_reachability(self, host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
        """Test basic TCP socket connectivity to the target server."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True, "Server reachable"
        except socket.timeout:
            return False, "Connection timed out (Check server IP/firewall)"
        except ConnectionRefusedError:
            return False, "Connection refused (Check server port)"
        except Exception as e:
            return False, f"Server unreachable: {e}"

    def measure_latency(self) -> Optional[float]:
        """Measure round-trip time in milliseconds to the active server."""
        if not self.server or not self.server_port:
            return None
        try:
            t0 = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect((self.server, int(self.server_port)))
            sock.close()
            t1 = time.time()
            self.ping_ms = round((t1 - t0) * 1000, 1)
            return self.ping_ms
        except Exception:
            self.ping_ms = None
            return None

    def connect_async(
        self,
        server: str,
        port: int,
        password: str,
        method: str = "aes-256-gcm",
        mode: str = "system",
        sudo_password: str = "",
        callback: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Initiate connection in a dedicated background worker thread."""
        with self._lock:
            if self.status in (self.STATUS_CONNECTING, self.STATUS_CONNECTED):
                return
            self.status = self.STATUS_CONNECTING
            self.status_message = "Initiating connection..."
            self.last_error = ""

        thread = threading.Thread(
            target=self._connect_worker,
            args=(server, port, password, method, mode, sudo_password, callback),
            daemon=True,
        )
        thread.start()

    def _connect_worker(
        self,
        server: str,
        port: int,
        password: str,
        method: str,
        mode: str,
        sudo_password: str,
        callback: Optional[Callable[[bool, str], None]],
    ) -> None:
        server = server.strip()
        self.server = server
        self.server_port = port
        self.password = password
        self.method = method
        self.mode = mode
        self.sudo_password = sudo_password

        # 1. Validation
        if not server:
            self._handle_failure("Server IP or domain is required", callback)
            return

        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                raise ValueError()
        except ValueError:
            self._handle_failure("Invalid port (must be between 1 and 65535)", callback)
            return

        if not password:
            self._handle_failure("Server password is required", callback)
            return

        # 2. Check Sudo permissions for TUN mode
        if mode == "tun":
            self.status_message = "Verifying sudo permissions for TUN mode..."
            ok, sudo_msg = TunController.verify_sudo_access(sudo_password)
            if not ok:
                self._handle_failure(f"Sudo error: {sudo_msg}", callback)
                return

        # 3. Test remote server reachability
        self.status_message = f"Probing {server}:{port_num}..."
        reach_ok, reach_msg = self.test_reachability(server, port_num, timeout=3.5)
        if not reach_ok:
            self._handle_failure(f"Remote check failed: {reach_msg}", callback)
            return

        # 4. Launch Shadowsocks (sslocal)
        self.status_message = f"Launching sslocal in {mode.upper()} mode..."
        success, launch_msg = self._start_sslocal(server, port_num, password, method, mode, sudo_password)
        if not success:
            self._handle_failure(launch_msg, callback)
            return

        # 5. Connection Succeeded!
        with self._lock:
            self.status = self.STATUS_CONNECTED
            self.connected_at = time.time()
            self.status_message = f"Connected! ({mode.upper()} Mode active)"

        # 6. Apply IPv6 Leak Protection if requested
        if self.ipv6_leak_protection:
            ok_ipv6, msg_ipv6 = IPv6Controller.enable_leak_protection(sudo_password)
            if ok_ipv6:
                self.status_message += " [IPv6 Shielded]"

        # 7. Save configuration to file upon successful connection
        save_success = save_config({
            "server": server,
            "server_port": port_num,
            "password": password,
            "method": method,
            "mode": mode,
            "local_port": self.local_port,
            "ipv6_leak_protection": self.ipv6_leak_protection,
        })
        if save_success:
            self.status_message += " [Saved to config.json]"

        # 8. Start monitor thread
        self._start_monitor()

        if callback:
            callback(True, self.status_message)

    def _start_sslocal(
        self,
        server: str,
        port: int,
        password: str,
        method: str,
        mode: str,
        sudo_password: str,
    ) -> tuple[bool, str]:
        """Start the sslocal subprocess according to chosen mode."""
        server_endpoint = f"{server}:{port}"

        if mode == "system":
            # Normal user mode: SOCKS5 proxy on 127.0.0.1:1080
            cmd = [
                "sslocal",
                "-s", server_endpoint,
                "-k", password,
                "-m", method,
                "-b", f"127.0.0.1:{self.local_port}",
                "--protocol", "socks",
                "-U",  # TCP and UDP
            ]
            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except Exception as e:
                return False, f"Failed to start sslocal: {e}"

            time.sleep(0.4)
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                return False, f"sslocal exited prematurely: {err.strip()}"

            if not self._check_socks5_ready():
                self._stop_process()
                return False, "SOCKS5 proxy failed to respond locally"

            ProxyController.enable_proxy("127.0.0.1", self.local_port)
            return True, "System proxy active"

        elif mode == "tun":
            # TUN mode: virtual adapter routing
            gw, dev = TunController.get_default_gateway_and_interface()
            if not dev:
                return False, "Unable to find default network interface"

            cmd = [
                "sslocal",
                "-s", server_endpoint,
                "-k", password,
                "-m", method,
                "--protocol", "tun",
                "--tun-interface-name", self.tun_name,
                "--tun-interface-address", self.tun_address,
                "--outbound-bind-interface", dev,
            ]

            try:
                self.process = TunController.spawn_sudo(cmd, sudo_password)
            except Exception as e:
                return False, f"Failed to spawn sslocal with sudo: {e}"

            time.sleep(0.6)
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                return False, f"TUN sslocal failed: {err.strip()}"

            ok, route_msg = TunController.setup_tun_interface_and_routes(
                server, self.tun_name, sudo_password
            )
            if not ok:
                self._stop_process()
                TunController.cleanup_tun_routes_and_interface(server, self.tun_name, sudo_password)
                return False, route_msg

            return True, "TUN mode VPN active"

        return False, f"Unknown mode: {mode}"

    def _check_socks5_ready(self, timeout: float = 2.0) -> bool:
        """Verify SOCKS5 listener responds to initial handshake greeting."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(("127.0.0.1", self.local_port))
            sock.sendall(b"\x05\x01\x00")
            resp = sock.recv(2)
            sock.close()
            return resp == b"\x05\x00"
        except Exception:
            return False

    def _handle_failure(self, message: str, callback: Optional[Callable[[bool, str], None]]) -> None:
        with self._lock:
            self.status = self.STATUS_ERROR
            self.last_error = message
            self.status_message = f"Error: {message}"
        self._stop_process()
        if callback:
            callback(False, message)

    def _stop_process(self) -> None:
        """Stop sslocal subprocess safely."""
        if self.process:
            pid = self.process.pid
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    if self.mode == "tun":
                        TunController.kill_process(pid, self.sudo_password)
                    else:
                        self.process.kill()
                except Exception:
                    pass
            self.process = None

    def disconnect_sync(self) -> None:
        """Synchronously disconnect and restore all network settings."""
        self._monitor_running = False
        with self._lock:
            if self.status == self.STATUS_DISCONNECTED:
                return
            self.status = self.STATUS_DISCONNECTED
            self.connected_at = None
            self.ping_ms = None
            self.status_message = "Disconnected. Ready to connect."

        # Teardown based on active mode
        if self.mode == "system":
            ProxyController.disable_proxy()
        elif self.mode == "tun":
            TunController.cleanup_tun_routes_and_interface(
                self.server, self.tun_name, self.sudo_password
            )

        # Restore IPv6 routing if leak protection was applied
        if IPv6Controller.is_active():
            IPv6Controller.disable_leak_protection(self.sudo_password)

        self._stop_process()

    def disconnect_async(self, callback: Optional[Callable[[], None]] = None) -> None:
        """Disconnect in background thread."""
        def _worker():
            self.disconnect_sync()
            if callback:
                callback()

        threading.Thread(target=_worker, daemon=True).start()

    def _start_monitor(self) -> None:
        """Monitor connection health, latency, and process liveness in background."""
        self._monitor_running = True

        def _monitor_loop():
            while self._monitor_running and self.is_connected:
                # Check process liveness
                if self.process and self.process.poll() is not None:
                    with self._lock:
                        self.status = self.STATUS_ERROR
                        self.status_message = "Connection lost: sslocal terminated"
                    self.disconnect_sync()
                    break

                # Periodic latency ping
                self.measure_latency()

                # Refresh sudo timestamp if in TUN mode
                if self.mode == "tun" and self.sudo_password:
                    TunController.run_sudo(["-v"], self.sudo_password)

                time.sleep(5.0)

        threading.Thread(target=_monitor_loop, daemon=True).start()
