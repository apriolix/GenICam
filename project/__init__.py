"""GenICam ROS2 Driver - Distributed image acquisition system.

This package provides a distributed image acquisition system for industrial
cameras using the GenICam standard. It includes a master node that captures
images from multiple cameras and streams them over the network to clients.

Core modules:
    - main: Entry point to start the master server
    - example: Example client implementation
    - genicam_node: ROS 2 node for camera management
    - genicam_communication: High-level API for client-server communication
    - genicam_host_server: Server-side socket and threading logic
    - genicam_client_server: Client-side request handling
    - genicam_network_basics: Low-level network utilities and enums
    - data_structures: Camera and configuration data structures
"""
