#!/usr/bin/env python3
"""
FlashForge Printer Control CLI

Discover and control FlashForge printers on your network.

Usage:
    python printer_cli.py list                    # Find printers on network
    python printer_cli.py status                  # Get printer status
    python printer_cli.py send file.gcode         # Send file to printer
    python printer_cli.py send file.gcode --print # Send and start print
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="FlashForge Printer Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                         Find printers on network
  %(prog)s status                       Show printer status
  %(prog)s status --ip 192.168.1.192    Status of specific printer
  %(prog)s send model.gcode             Upload file to printer
  %(prog)s send model.gcode --print     Upload and start printing
  %(prog)s camera                       Show camera stream URL
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # List command
    list_parser = subparsers.add_parser("list", help="Discover printers on network")
    list_parser.add_argument("--timeout", type=float, default=5.0,
                             help="Discovery timeout in seconds (default: 5)")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get printer status")
    status_parser.add_argument("--ip", help="Printer IP (auto-detect if not specified)")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send file to printer")
    send_parser.add_argument("file", help="G-code file to send")
    send_parser.add_argument("--ip", help="Printer IP (auto-detect if not specified)")
    send_parser.add_argument("--print", action="store_true", dest="start_print",
                             help="Start printing after upload")

    # Camera command
    camera_parser = subparsers.add_parser("camera", help="Get camera stream URL")
    camera_parser.add_argument("--ip", help="Printer IP (auto-detect if not specified)")

    # Info command
    info_parser = subparsers.add_parser("info", help="Get printer info")
    info_parser.add_argument("--ip", help="Printer IP (auto-detect if not specified)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "list":
            return cmd_list(args)
        elif args.command == "status":
            return cmd_status(args)
        elif args.command == "send":
            return cmd_send(args)
        elif args.command == "camera":
            return cmd_camera(args)
        elif args.command == "info":
            return cmd_info(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def get_printer_ip(args):
    """Get printer IP from args or auto-detect."""
    if hasattr(args, 'ip') and args.ip:
        return args.ip

    from printer.flashforge import discover_printers
    printers = discover_printers(timeout=3.0)

    if not printers:
        raise RuntimeError("No printers found. Use --ip to specify manually.")

    if len(printers) == 1:
        return printers[0].ip

    print("Multiple printers found:")
    for i, p in enumerate(printers, 1):
        print(f"  [{i}] {p.name} at {p.ip}")
    print("\nUse --ip to specify which printer to use.")
    raise RuntimeError("Multiple printers found")


def cmd_list(args):
    """List printers on network."""
    from printer.flashforge import list_printers
    printers = list_printers()
    return 0 if printers else 1


def cmd_status(args):
    """Show printer status."""
    from printer.flashforge import get_printer_status, get_printer_info

    ip = get_printer_ip(args)
    print(f"Printer: {ip}\n")

    # Get info
    info = get_printer_info(ip)
    if info.get('name'):
        print(f"Name: {info['name']}")
    if info.get('model'):
        print(f"Model: {info['model']}")

    # Get status
    status = get_printer_status(ip)

    print(f"\nState: {status.get('state', 'unknown').upper()}")

    if 'nozzle_temp' in status:
        print(f"Nozzle: {status['nozzle_temp']:.0f}°C / {status.get('nozzle_target', 0):.0f}°C")
    if 'bed_temp' in status:
        print(f"Bed: {status['bed_temp']:.0f}°C / {status.get('bed_target', 0):.0f}°C")

    if 'progress' in status:
        print(f"Progress: {status['progress']:.1f}%")

    return 0


def cmd_send(args):
    """Send file to printer."""
    from printer.flashforge import send_file

    filepath = Path(args.file)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {args.file}")

    ip = get_printer_ip(args)
    filesize = filepath.stat().st_size

    print(f"Sending {filepath.name} to {ip}...")
    print(f"Size: {filesize / 1024:.1f} KB")

    def progress(sent, total):
        pct = sent / total * 100
        bar = "=" * int(pct / 5) + ">" + " " * (20 - int(pct / 5))
        print(f"\r[{bar}] {pct:.0f}%", end="", flush=True)

    success = send_file(
        ip=ip,
        filepath=str(filepath),
        start_print=args.start_print,
        progress_callback=progress
    )

    print()  # New line after progress bar

    if success:
        if args.start_print:
            print(f"Upload complete! Printing started.")
        else:
            print(f"Upload complete! File saved to printer.")
            print(f"Start print from printer screen or use: python printer_cli.py send {args.file} --print")
    return 0


def cmd_camera(args):
    """Show camera stream URL."""
    from printer.flashforge import get_camera_url

    ip = get_printer_ip(args)
    url = get_camera_url(ip)

    print(f"Camera stream URL:")
    print(f"  {url}")
    print(f"\nOpen in browser or VLC to view live feed.")
    return 0


def cmd_info(args):
    """Show printer info."""
    from printer.flashforge import get_printer_info

    ip = get_printer_ip(args)
    info = get_printer_info(ip)

    print(f"Printer: {ip}\n")
    for key, value in info.items():
        print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
