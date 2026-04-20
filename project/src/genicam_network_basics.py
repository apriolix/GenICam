"""Low-level network utilities, enums, and socket buffer management.

This module provides foundational networking components:
    - Enums: Request types, response types, error types, connection status
    - BufferManagement: Send/receive protocol with 4-byte length prefix
    - IPRequest: Local IP address detection
    - Constants: Socket timeouts, buffer sizes, token separators

All socket communication uses the 4-byte length prefix protocol to ensure
correct message framing even for large image data transfers.

Request Protocol:
    1. Client sends: [4-byte length] [message data]
    2. Server reads length, then reads exactly that many bytes
    3. Server responds: [4-byte length] [response data]
"""

from socket import *
import threading
import yaml
import data_structures
import cv2
import numpy as np
import socketserver
import time
import os
from enum import Enum
from math import *
from genicam_node import HarvesterNode
import rclpy.logging
import datetime

import random

CAMERA_REQUEST_FORMAT_STRING = "requested_cameras:"
CAMERA_SEPARATION_TOKEN = ","

CLIENT_REACCEPTION_DELAY_TIME = 90
SOCKET_TIMEOUT = CLIENT_REACCEPTION_DELAY_TIME

class __RequestTypeEnum__(Enum):
    """Request message types sent from client to server.
    
    Each request type has a unique string prefix that the server uses to
    route to the appropriate handler.
    """
    CameraSubscriptions:str = "REQUEST cameras_to_subscripe "
    SingleFrame:str = "REQUEST single_frame "
    MultyFrame:str = "REQUEST multy_frame "
    DataFrameSizeAdjustment:str = "REQUEST camera_frame_size_adjustment "
    CameraCropFactorAdjustment:str = "REQUEST camera_crop_factor_adjustment "
    RestartFailedCams:str = "REQUEST restart_failed_cams "
    RestartGenicam:str = "REQUEST restart_genicam "
    GetAliveCameras:str = "REQUEST get_alive_cameras "
    SplitToken:str = " "

class __PostType__(Enum):
    """Response message types sent from server to client (status codes)."""
    DataFrameAdjustmentErrors:str = "POST frame_size_adjustment_error "
    OK:str = "POST OK "
    ERROR:str = "POST ERROR "
    
class __MarkerTokens__(Enum):
    """Token strings used to separate multiple values in messages."""
    CameraSeparationToken:str = " "
    
class __Failures__(Enum):
    """Error/status codes used in communication."""
    ConnectionFailure:str = "Connection Failed!"
    OK:str = "OK"
    Errors = "Errors"

class __Exception__(Enum):
    """Exception message prefix."""
    ExceptionHead:str = "POST EXCEPTION MESSAGE: "

class __ClientHealth__(Enum):
    """Client connection health status."""
    Good:str = "good"
    Crashed:str = "crashed" 

BUFFER_SIZE = 28000000

class IPRequest():
    """Utility class for local IP address detection."""
    
    def get_local_ip() -> str:
        """Determine the local IP address of this machine in the network.
        
        Connects to a local network gateway and extracts the local IP
        from the resulting socket name.
        
        Returns:
            IP address string (e.g., "192.168.1.100")
        """
        # ping local ip to get socketname == the ip-adress of local machine in network
        s = socket(AF_INET, SOCK_DGRAM)
        s.connect(("192.168.0.1", 80))
        ip = s.getsockname()[0]
        return ip



class BufferManagement():
    """Utility class for sending/receiving data over TCP with length prefix.
    
    All messages use a 4-byte little-endian length prefix to enable
    correct framing even for binary image data.
    
    Protocol:
        1. Send 4-byte length (little-endian unsigned int)
        2. Send message data (can be binary)
        3. Receiver reads length, then reads exactly that many bytes
    """
    
    def send_exception(tcp_socket:socket, exception):
        """Send an exception message to the other endpoint.
        
        Args:
            tcp_socket: Active TCP socket
            exception: Exception object or error message string
        """
        if not isinstance(exception, str):
            exception = str(exception)
        
        BufferManagement.send_buffer(tcp_socket, __Exception__.ExceptionHead.value + exception)

    def read_buffer(tcp_socket:socket):
        """Receive a message from TCP socket using length-prefixed protocol.
        
        Args:
            tcp_socket: Active TCP socket
            
        Returns:
            Received message as bytes
            
        Raises:
            Exception: If connection lost or exception message received
        """
        # Read subsrcibed camera names
        buff_size = int().from_bytes(tcp_socket.recv(4), 'little')
        
        buffer = bytes()
        while len(buffer) != buff_size:
            rec_buffer = tcp_socket.recv(buff_size - len(buffer))
            
            ## cheching if connection got lost
            if rec_buffer == bytes():
                raise Exception("Connection lost") 
            else:
                buffer += rec_buffer

        if buffer.find(__Exception__.ExceptionHead.value.encode()) != -1:
            print(f"[Exception received {datetime.datetime.now()}] {buffer.decode()} \n [Canceling operation...]")
            raise Exception("Exception msg received while reading buffer!")

        return buffer
    
    def send_buffer(tcp_socket:socket, buffer:bytes|str):
        """Send a message over TCP socket using length-prefixed protocol.
        
        Automatically converts strings to bytes and prepends 4-byte length.
        
        Args:
            tcp_socket: Active TCP socket
            buffer: Message data (str or bytes)
            
        Raises:
            Exception: If buffer is not string or bytes type
        """
        if isinstance(buffer, str):
            buffer = buffer.encode()

        if not isinstance(buffer, bytes):
            raise Exception(f"Buffer type dosen't matches type of string or bytes! The type is: {type(buffer)}")

        tcp_socket.sendall(len(buffer).to_bytes(4, 'little'))
        tcp_socket.sendall(buffer)