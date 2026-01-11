"""
FlashForge Printer Control Module

Supports discovery and control of FlashForge printers on local network.
Tested with Adventurer 5M/5M Pro.

Protocol based on reverse engineering from:
- https://github.com/Slugger2k/FlashForgePrinterApi
- https://github.com/Mrnt/OctoPrint-FlashForge
"""

import socket
import struct
import time
import zlib
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass


# Protocol constants
DISCOVERY_ADDR = "225.0.0.9"
DISCOVERY_PORT = 19000
PRINTER_PORT = 8899  # Default FlashForge control port
BUFFER_SIZE = 4096
PACKET_HEADER = bytes.fromhex("5a5aa5a5")


@dataclass
class FlashForgePrinter:
    """Represents a discovered FlashForge printer."""
    name: str
    ip: str
    port: int = PRINTER_PORT
    serial: str = ""
    model: str = ""
    firmware: str = ""

    def __str__(self):
        return f"{self.name} ({self.model}) at {self.ip}:{self.port}"


def discover_printers(timeout: float = 3.0) -> List[FlashForgePrinter]:
    """
    Discover FlashForge printers on the local network using UDP broadcast.

    Args:
        timeout: How long to wait for responses (seconds)

    Returns:
        List of discovered FlashForgePrinter objects
    """
    printers = []

    # Create UDP socket for discovery
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)

    # Discovery message (16 bytes)
    discovery_msg = b'\x00' * 16

    try:
        # Send broadcast
        sock.sendto(discovery_msg, (DISCOVERY_ADDR, DISCOVERY_PORT))

        # Collect responses
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                ip = addr[0]

                # Parse response - typically contains printer name
                # Response format varies by model
                try:
                    name = data.decode('utf-8', errors='ignore').strip('\x00').strip()
                    if not name:
                        name = f"FlashForge@{ip}"
                except:
                    name = f"FlashForge@{ip}"

                # Check if we already have this printer
                if not any(p.ip == ip for p in printers):
                    printer = FlashForgePrinter(name=name, ip=ip)
                    # Try to get more info
                    try:
                        info = get_printer_info(ip)
                        printer.model = info.get('model', '')
                        printer.serial = info.get('serial', '')
                        printer.firmware = info.get('firmware', '')
                        if info.get('name'):
                            printer.name = info['name']
                    except:
                        pass
                    printers.append(printer)

            except socket.timeout:
                break
            except Exception as e:
                continue

    finally:
        sock.close()

    return printers


def _send_command(ip: str, command: str, port: int = PRINTER_PORT, timeout: float = 5.0) -> str:
    """
    Send a G-code command to the printer and get response.

    Args:
        ip: Printer IP address
        command: G-code command (e.g., "M115")
        port: Printer port (default 8899)
        timeout: Response timeout

    Returns:
        Response string from printer
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((ip, port))

        # Send hello
        sock.send(b"~M601 S1\r\n")
        time.sleep(0.1)
        sock.recv(1024)  # Read hello response

        # Send command
        cmd = f"~{command}\r\n".encode()
        sock.send(cmd)

        # Read response
        response = b""
        while True:
            try:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
                if b"ok" in response.lower() or b"error" in response.lower():
                    break
            except socket.timeout:
                break

        # Send bye
        sock.send(b"~M602\r\n")

        return response.decode('utf-8', errors='ignore')

    finally:
        sock.close()


def get_printer_info(ip: str, port: int = PRINTER_PORT) -> Dict:
    """
    Get printer information (model, firmware, etc.)

    Args:
        ip: Printer IP address
        port: Printer port

    Returns:
        Dict with printer info
    """
    response = _send_command(ip, "M115", port)

    info = {}
    for line in response.split('\n'):
        line = line.strip()
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip().lower().replace(' ', '_')
            value = value.strip()

            if 'machine_type' in key or 'type' in key:
                info['model'] = value
            elif 'machine_name' in key or 'name' in key:
                info['name'] = value
            elif 'firmware' in key or 'version' in key:
                info['firmware'] = value
            elif 'serial' in key or 'sn' in key:
                info['serial'] = value
            elif 'x:' in key.lower():
                info['build_x'] = value
            elif 'y:' in key.lower():
                info['build_y'] = value
            elif 'z:' in key.lower():
                info['build_z'] = value

    return info


def get_printer_status(ip: str, port: int = PRINTER_PORT) -> Dict:
    """
    Get current printer status (temperatures, print progress, etc.)

    Args:
        ip: Printer IP address
        port: Printer port

    Returns:
        Dict with status info
    """
    status = {}

    # Get temperature (M105)
    try:
        response = _send_command(ip, "M105", port)
        # Parse: T0:205 /205 B:60 /60
        if 'T' in response:
            for part in response.split():
                if part.startswith('T'):
                    # Nozzle temp
                    temps = part.split(':')[1] if ':' in part else ''
                    if '/' in temps:
                        current, target = temps.split('/')
                        status['nozzle_temp'] = float(current)
                        status['nozzle_target'] = float(target)
                elif part.startswith('B:'):
                    temps = part.split(':')[1]
                    if '/' in temps:
                        current, target = temps.split('/')
                        status['bed_temp'] = float(current)
                        status['bed_target'] = float(target)
    except:
        pass

    # Get print progress (M27)
    try:
        response = _send_command(ip, "M27", port)
        # Parse: SD printing byte X/Y
        if 'byte' in response.lower():
            parts = response.split()
            for i, part in enumerate(parts):
                if '/' in part:
                    current, total = part.split('/')
                    status['bytes_printed'] = int(current)
                    status['bytes_total'] = int(total)
                    if int(total) > 0:
                        status['progress'] = round(int(current) / int(total) * 100, 1)
    except:
        pass

    # Get status (M119)
    try:
        response = _send_command(ip, "M119", port)
        if 'idle' in response.lower():
            status['state'] = 'idle'
        elif 'print' in response.lower():
            status['state'] = 'printing'
        elif 'pause' in response.lower():
            status['state'] = 'paused'
        else:
            status['state'] = 'unknown'
    except:
        status['state'] = 'unknown'

    return status


def send_file(ip: str, filepath: str, port: int = PRINTER_PORT,
              start_print: bool = False, progress_callback=None) -> bool:
    """
    Send a G-code/GX file to the printer.

    Args:
        ip: Printer IP address
        filepath: Path to .gcode or .gx file
        port: Printer port
        start_print: Start printing after upload
        progress_callback: Optional callback(bytes_sent, total_bytes)

    Returns:
        True if successful
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    filename = filepath.name
    filesize = filepath.stat().st_size

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)

    try:
        sock.connect((ip, port))

        # Hello
        sock.send(b"~M601 S1\r\n")
        time.sleep(0.2)
        sock.recv(1024)

        # Prepare to receive file (M28)
        cmd = f"~M28 {filesize} 0:/user/{filename}\r\n"
        sock.send(cmd.encode())
        time.sleep(0.2)
        response = sock.recv(1024)

        if b"ok" not in response.lower():
            raise RuntimeError(f"Printer rejected file transfer: {response}")

        # Send file in chunks
        bytes_sent = 0
        packet_num = 0

        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break

                # Build packet with header, counter, length, CRC
                # Format: HEADER(4) + COUNTER(4) + LENGTH(4) + DATA + CRC(4)
                crc = zlib.crc32(chunk) & 0xFFFFFFFF
                header = PACKET_HEADER
                counter = struct.pack('<I', packet_num)
                length = struct.pack('<I', len(chunk))
                crc_bytes = struct.pack('<I', crc)

                packet = header + counter + length + chunk + crc_bytes
                sock.send(packet)

                bytes_sent += len(chunk)
                packet_num += 1

                if progress_callback:
                    progress_callback(bytes_sent, filesize)

                # Small delay to not overwhelm printer
                time.sleep(0.01)

        # End transfer (M29)
        sock.send(b"~M29\r\n")
        time.sleep(0.5)
        response = sock.recv(1024)

        if b"ok" not in response.lower():
            raise RuntimeError(f"File transfer failed: {response}")

        # Start print if requested (M23)
        if start_print:
            cmd = f"~M23 0:/user/{filename}\r\n"
            sock.send(cmd.encode())
            time.sleep(0.2)
            response = sock.recv(1024)

        # Bye
        sock.send(b"~M602\r\n")

        return True

    except Exception as e:
        raise RuntimeError(f"Failed to send file: {e}")
    finally:
        sock.close()


def get_camera_url(ip: str) -> str:
    """Get the camera stream URL for the printer."""
    return f"http://{ip}:8080/?action=stream"


# CLI functions
def list_printers():
    """Discover and print all FlashForge printers on the network."""
    print("Scanning for FlashForge printers...")
    printers = discover_printers(timeout=5.0)

    if not printers:
        print("No printers found. Make sure:")
        print("  - Printer is on and connected to WiFi/Ethernet")
        print("  - Computer is on the same network")
        print("  - Printer's LAN mode is enabled")
        return []

    print(f"\nFound {len(printers)} printer(s):\n")
    for i, p in enumerate(printers, 1):
        print(f"  [{i}] {p.name}")
        print(f"      IP: {p.ip}")
        if p.model:
            print(f"      Model: {p.model}")
        if p.firmware:
            print(f"      Firmware: {p.firmware}")
        print(f"      Camera: {get_camera_url(p.ip)}")
        print()

    return printers


if __name__ == "__main__":
    list_printers()
