"""
Test script for port utilities.
"""
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from utils.port_utils import (
    is_port_in_use,
    find_free_port,
    get_free_port,
    get_local_ip,
    get_ip_and_free_port
)

def test_port_utils():
    print("=" * 60)
    print("Testing Port Utilities")
    print("=" * 60)

    # Test 1: Get local IP
    print("\n1. Testing get_local_ip():")
    ip = get_local_ip()
    print(f"   Local IP: {ip}")

    # Test 2: Check if a port is in use
    print("\n2. Testing is_port_in_use():")
    test_ports = [80, 443, 8080, 50000]
    for port in test_ports:
        in_use = is_port_in_use(port)
        print(f"   Port {port}: {'IN USE' if in_use else 'FREE'}")

    # Test 3: Find free port from a starting point
    print("\n3. Testing find_free_port():")
    free_port = find_free_port(50000)
    print(f"   Found free port starting from 50000: {free_port}")

    # Test 4: Get free port with preferred port
    print("\n4. Testing get_free_port() with preferred port:")
    preferred = 50051
    port = get_free_port(preferred_port=preferred)
    print(f"   Preferred port {preferred}, got: {port}")

    # Test 5: Get free port without preference
    print("\n5. Testing get_free_port() without preference:")
    port = get_free_port()
    print(f"   Got free port: {port}")

    # Test 6: Get IP and free port
    print("\n6. Testing get_ip_and_free_port():")
    ip, port = get_ip_and_free_port(preferred_port=50052)
    print(f"   IP: {ip}, Port: {port}")

    # Test 7: Test with occupied port (simulate)
    print("\n7. Testing port conflict resolution:")
    import socket
    # Create a socket to occupy a port
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.bind(("0.0.0.0", 0))
    test_socket.listen(1)
    occupied_port = test_socket.getsockname()[1]
    print(f"   Occupied port: {occupied_port}")

    # Try to get the occupied port
    result_port = get_free_port(preferred_port=occupied_port)
    print(f"   Requested {occupied_port}, got alternative: {result_port}")

    # Cleanup
    test_socket.close()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_port_utils()

