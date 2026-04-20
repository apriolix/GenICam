"""Entry point for GenICam master server.

This module starts the master server which:
    - Initializes the GenICam harvester and camera detection
    - Captures images from all configured cameras
    - Distributes images to connected clients over TCP
    - Handles client requests via custom protocol
    - Broadcasts server availability via UDP
"""

import argparse
import sys

from genicam_communication import GenicamCommunication


def main(argv: list[str] | None = None) -> int:
    """Initialize and start the GenICam master server.

    The only required parameter to start a server is the server/master id.

    Usage:
        python3 project/src/main.py --server-id 0

    Args:
        argv: List of command line arguments (for testing). If None, uses sys.argv[1:].

    Returns:
        exit code (0 on success)
    """
    parser = argparse.ArgumentParser(prog="genicam_master")
    parser.add_argument("--server-id", "-i", type=int, default=0,
                        help="Server / Master ID (integer). Default: 0")
    args = parser.parse_args(argv)

    # Start the high-level master server. GenicamCommunication handles
    # initialization of cameras, networking and client handling.
    GenicamCommunication("master", args.server_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())