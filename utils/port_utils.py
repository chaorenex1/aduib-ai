"""
Port utility functions for cross-platform port management.
"""
import logging
import socket
from typing import Tuple, Optional

log = logging.getLogger(__name__)


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a port is already in use.

    Args:
        port: Port number to check
        host: Host address to check (default: "0.0.0.0")

    Returns:
        True if port is in use, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_free_port(start_port: int, max_attempts: int = 100, host: str = "0.0.0.0") -> Optional[int]:
    """
    Find a free port starting from start_port.

    Args:
        start_port: Starting port number
        max_attempts: Maximum number of ports to try (default: 100)
        host: Host address to check (default: "0.0.0.0")

    Returns:
        Available port number or None if no free port found
    """
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port, host):
            log.info(f"Found free port: {port}")
            return port

    log.error(f"No free port found in range {start_port}-{start_port + max_attempts}")
    return None


def get_free_port(preferred_port: Optional[int] = None, host: str = "0.0.0.0") -> int:
    """
    Get a free port, either the preferred port if available or find a new one.

    Args:
        preferred_port: Preferred port number (optional)
        host: Host address to check (default: "0.0.0.0")

    Returns:
        Available port number
    """
    if preferred_port is not None:
        if not is_port_in_use(preferred_port, host):
            log.info(f"Using preferred port: {preferred_port}")
            return preferred_port
        else:
            log.warning(f"Preferred port {preferred_port} is in use, finding alternative...")
            free_port = find_free_port(preferred_port + 1, host=host)
            if free_port is not None:
                return free_port

    # Fallback: let OS assign a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        s.listen(1)
        port = s.getsockname()[1]
        log.info(f"OS assigned free port: {port}")
        return port


def get_local_ip() -> str:
    """
    Get the local IP address of the machine.
    Cross-platform compatible.

    Returns:
        Local IP address as string
    """
    try:
        # Create a socket and connect to an external address
        # This doesn't actually send data, just determines the local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Use Google's DNS server to determine local IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            return ip
    except Exception as e:
        log.warning(f"Could not determine local IP: {e}, falling back to 127.0.0.1")
        return "127.0.0.1"


def get_ip_and_free_port(preferred_port: Optional[int] = None, host: str = "0.0.0.0") -> Tuple[str, int]:
    """
    Get local IP and a free port.

    Args:
        preferred_port: Preferred port number (optional)
        host: Host address to check (default: "0.0.0.0")

    Returns:
        Tuple of (ip_address, port_number)
    """
    ip = get_local_ip()
    port = get_free_port(preferred_port, host)
    return ip, port

