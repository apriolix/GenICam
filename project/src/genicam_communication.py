"""High-level API for GenICam client-server communication.

This module provides the main user-facing API for:
    - Master mode: Initialize server, manage cameras, broadcast discovery
    - Client mode: Connect to server, request images, adjust camera settings
    - Error handling and connection state management
    - Configuration loading from YAML files

GenicamCommunication is a facade that hides the complexity of socket
management, threading, and protocol details from the user.

Usage:
    # For master (server):
    master = GenicamCommunication("master", 0)
    
    # For client:
    client = GenicamCommunication("client", 0)
    client.subscribe_to_images(["camera1", "camera2"])
    images = client.get_latest_images()
"""

from genicam_client_server import * 
from genicam_client_server import __RequestServer__
from genicam_host_server import __ClientHandler__
from genicam_network_basics import __ClientHealth__,__RequestTypeEnum__,__MarkerTokens__, __PostType__,__Failures__

        
class GenicamCommunication():
    """High-level API facade for GenICam client-server communication.
    
    Provides simple methods for:
    - Master mode: Initialize server, manage cameras, broadcast availability
    - Client mode: Connect to server, request images, adjust parameters
    
    Attributes:
        is_master: Boolean indicating master (True) or client (False) mode
        genicam_node: HarvesterNode instance (master only)
        subscriber_handler: __ClientHandler__ instance (master only)
        subscriber: __RequestServer__ instance (client only)
    """
    
    def __init__(self, node_type=("client", "master"), server_id:int = 0):
        """Initialize GenICam communication in master or client mode.
        
        Master mode:
            - Loads camera configuration from config.yaml
            - Initializes Harvesters camera discovery
            - Starts UDP broadcast listener and TCP server
            - Begins image capture from all cameras
            
        Client mode:
            - Loads network configuration from network.yaml
            - Creates TCP request server on random port
            - Initiates UDP discovery of master server
            
        Args:
            node_type: "master" or "client"
            server_id: Optional server ID (for multi-server scenarios)
        """
        self.is_master = True if node_type == "master" else False  
        
        currend_working_dir = os.getcwd() # Read the set working directory path (/GeniCamROS)
        
        file_path = os.path.join(currend_working_dir, "config", "network.yaml") # create final path
    
        file = open(file_path, "r")
        self.config = yaml.load(file, Loader=yaml.Loader)
        
        self.broadcast_port:int = self.config["broadcast_port"]
        self.client_port_range:list[int] = self.config["client_port_range"]
        self.broadcast_key:str = self.config["broadcast_key"] + " "
        
        
        self.broadcast_socket = socket(AF_INET, SOCK_DGRAM)
        self.broadcast_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        
        self.broadcast_thread = threading.Thread()
        
        
        self.subscriber = None
        self.subscriber_handler = None
        
        self.server_id = server_id
        self.genicam_node = None
        
        if node_type == "master":
            rclpy.init()
            
            self.genicam_node = HarvesterNode()
            self.broadcast_socket.bind(("255.255.255.255", self.broadcast_port))
            self.subscriber_handler = __ClientHandler__(self.genicam_node, self.config["server_heartbeat"], self.config["server_queue_size"])
            self.broadcast_thread = threading.Thread(target=self.__master_broadcast_listener__)
            self.broadcast_thread.start()
            
        elif node_type == "client" or node_type != "master":
            self.subscriber = __RequestServer__(self.client_port_range)
            self.__register_client_to_genicam__()
            
    
    def connected_to_server(self) -> bool:
        """Check if client is currently connected to master server.
        
        Returns:
            True if connection is active and healthy
        """
        return self.subscriber.is_connected
    
    def subscribe_to_images(self, cam_names:list[str]):
        """Subscribe to image stream from specific cameras.
        
        After subscription, images can be retrieved via get_latest_images().
        
        Args:
            cam_names: List of camera names to subscribe to
            
        Returns:
            True if successful, False on error
        """
        try:
            self.subscriber.subscribe_to_images(cam_names)
            return True
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return False
            
    
    def get_latest_images(self) -> dict:
        """Retrieve latest image from each subscribed camera.
        
        Returns:
            Dictionary mapping camera_name -> {"img": numpy_array, ...}
            or None on error
        """
        try:
            return self.subscriber.request_latest_images()
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return None
    
    def get_camera_queues(self) -> dict:
        """Retrieve queued images from each subscribed camera.
        
        Returns:
            Dictionary mapping camera_name -> [img1, img2, ...]
            or None on error
        """
        try:
            return self.subscriber.request_camera_queues()
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return None
    
        
    def get_alive_cams(self) -> list[str]:
        """Get list of currently active cameras on server.
        
        Returns:
            List of active camera names, or empty list on error
        """
        try:
            return self.subscriber.get_alive_cams()
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return []
            
    def update_genicam_config_file(self, abs_config_path) -> bool:
        """Send updated camera configuration to server.
        
        Args:
            abs_config_path: Absolute path to config.yaml file
            
        Returns:
            True if successful, False on error
        """
        file = open(abs_config_path, "r")
        yaml_obj = yaml.load(file, Loader=yaml.Loader)
        file.close()
        
        try:
            self.subscriber.update_genicam_config_file(yaml_obj)
            return True
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return False
    
    def try_to_reconnect_cameras(self):
        """Request server to retry connecting to previously failed cameras.
        
        Returns:
            True if successful, False on error
        """
        try:
            self.subscriber.try_to_reconnect_cameras()
            return True
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return False
        

    def rescale_data_frame(self, desired_scaler:float):
        """Adjust image scaling for network transfer optimization.
        
        Args:
            desired_scaler: Target scaling factor (1.0 = full resolution)
            
        Returns:
            True if successful, False on error
        """
        try:
            self.subscriber.post_data_frame_rescale_factor(desired_scaler)
            return True
        except Exception as ex:
            print(f"Exception: {ex}")
            self.subscriber.is_connected = False
            return False
    
    def set_new_crop_factor(self, new_crop:float):
        """Adjust image cropping on the server side.
        
        Args:
            new_crop: Crop factor (0.0-1.0, where 0.5 keeps center 50%)
            
        Returns:
            True if successful, False on error
        """
        try:
            self.subscriber.request_new_crop_factor(new_crop)
            return True
        except Exception as ex:
            print(f"Exception: {ex}")
            return False
    
    def __master_broadcast_listener__(self):
        """Master thread listening for UDP discovery broadcasts from clients.
        
        Continuously listens for client discovery requests on broadcast socket
        and registers new clients with the __ClientHandler__.
        
        Runs in background thread until server shutdown.
        """
        while True:
            msg, client = self.broadcast_socket.recvfrom(len(self.broadcast_key.encode() + " ".encode()) + 4 * 2)
            
            key_string = msg[:len(self.broadcast_key)].decode()
            port = int().from_bytes(msg[len(self.broadcast_key):], 'little')
            server_id = int().from_bytes(msg[len(self.broadcast_key) + 4:], 'little')
            
            if key_string == self.broadcast_key and port >= self.client_port_range[0] and port <= self.client_port_range[1] and server_id == self.server_id:
                self.subscriber_handler.add_client((client[0], port))
        

    def __register_client_to_genicam__(self):
        """Client thread broadcasting discovery UDP packets to find master.
        
        Repeatedly broadcasts client's listening port to the network until
        the master responds with a connection.
        
        Runs in background thread in client mode.
        """
        while not self.subscriber.is_connected:
            if self.subscriber.port != -1:
                self.broadcast_socket.sendto(self.broadcast_key.encode() + self.subscriber.port.to_bytes(4, 'little') + self.server_id.to_bytes(4,'little'), ("255.255.255.255", self.broadcast_port))
            time.sleep(0.05)
    
