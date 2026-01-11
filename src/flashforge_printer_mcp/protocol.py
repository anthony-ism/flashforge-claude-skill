"""
FlashForge Printer Network Protocol

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
from dataclasses import dataclass, asdict


# Protocol constants
DISCOVERY_ADDR = "225.0.0.9"
DISCOVERY_PORT = 19000
PRINTER_PORT = 8899
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

    def to_dict(self) -> dict:
        return asdict(self)


def discover_printers(timeout: float = 5.0) -> List[FlashForgePrinter]:
    """
    Discover FlashForge printers on the local network using UDP broadcast.

    Args:
        timeout: How long to wait for responses (seconds)

    Returns:
        List of discovered FlashForgePrinter objects
    """
    printers = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)

    discovery_msg = b'\x00' * 16

    try:
        sock.sendto(discovery_msg, (DISCOVERY_ADDR, DISCOVERY_PORT))

        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                ip = addr[0]

                try:
                    name = data.decode('utf-8', errors='ignore').strip('\x00').strip()
                    if not name:
                        name = f"FlashForge@{ip}"
                except:
                    name = f"FlashForge@{ip}"

                if not any(p.ip == ip for p in printers):
                    printer = FlashForgePrinter(name=name, ip=ip)
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
            except Exception:
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

        sock.send(b"~M601 S1\r\n")
        time.sleep(0.1)
        sock.recv(1024)

        cmd = f"~{command}\r\n".encode()
        sock.send(cmd)

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
        if 'T' in response:
            for part in response.split():
                if part.startswith('T'):
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
        if 'byte' in response.lower():
            parts = response.split()
            for part in parts:
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
            sock.recv(1024)

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
