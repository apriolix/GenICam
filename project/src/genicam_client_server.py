"""Client-side request handling and TCP communication.

This module implements the client's low-level communication layer:
    - __RequestServer__: Manages TCP connection and sends/receives requests
    - Request types: Images, camera status, configuration updates
    - Port binding: Dynamic allocation within configured port range
    - Connection handling: UDP discovery notification of server

The __RequestServer__ encapsulates all socket operations for the client,
freeing higher layers to work with simple method calls.
"""

from genicam_network_basics import *
from genicam_network_basics import __ClientHealth__,__RequestTypeEnum__,__MarkerTokens__, __PostType__, __Failures__


class __RequestServer__():
    """Client-side request handler managing TCP connection to master server.
    
    Handles:
    - Socket binding to an available port within a given range
    - Waiting for master discovery via UDP broadcast
    - Sending structured requests to master
    - Receiving and parsing responses
    
    Attributes:
        ip: Client's local IP address
        port: Bound TCP port number
        server: TCP socket object
        connection: Established connection to master (after discovery)
        is_connected: Boolean flag for connection status
    """
    
    logger = rclpy.logging.get_logger("__RequestServer__")
    
    def __init__(self, port_range:list[int]):
        """Initialize request server and bind to first available port.
        
        Args:
            port_range: List [min_port, max_port] to search within
        """
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        #self.server.setsockopt(SOL_SOCKET, SO_RCVBUF, BUFFER_SIZE)
        self.server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server.settimeout(SOCKET_TIMEOUT)
        
        self.ip = IPRequest.get_local_ip()
        self.port = self.bind_socket(port_range[0], port_range[1])
        
        self.server.listen(1)
        
        self.connection = None
        
        self.is_connected = False
        self.connection_thread = threading.Thread(target=self.__await_connection__)
        self.connection_thread.start()
           
    def bind_socket(self, lower_port:int, upper_port:int) -> int:
        """Recursively find and bind to an available port in given range.
        
        Uses binary search algorithm to find first available port.
        
        Args:
            lower_port: Minimum port to try
            upper_port: Maximum port to try
            
        Returns:
            Successfully bound port number, or -1 if all ports busy
        """
        middle_port = int((upper_port - lower_port) / 2) + lower_port
        
        if upper_port - lower_port == 1:
            # Try bind
            try:
                self.server.bind((self.ip, lower_port))
                return lower_port
            except:
                pass
            try:
                self.server.bind((self.ip, upper_port))
                return upper_port
            except:
                return -1
        else:
            try:
                self.server.bind((self.ip, middle_port))
                return middle_port
            except:
                next_side = random.randint(0,1)
                
                port = -1
                # right side foirst
                if next_side == 1:
                    port = self.bind_socket(middle_port, upper_port)
                    if port == -1:
                        port = self.bind_socket(lower_port, middle_port)
                else:
                    port = self.bind_socket(lower_port, middle_port)
                    if port == -1:
                        port = self.bind_socket(middle_port, upper_port)

                return port
    
    def post_data_frame_rescale_factor(self, desired_scaler:float) -> str:
        """Request server to adjust image scaling factor.
        
        Args:
            desired_scaler: Target scaling factor (1.0 = full resolution)
            
        Returns:
            Server response status string
        """
        buffer = __RequestTypeEnum__.DataFrameSizeAdjustment.value.encode() + desired_scaler.hex().encode()
        BufferManagement.send_buffer(self.connection, buffer)
        
        return BufferManagement.read_buffer(self.connection).decode()
    
    def request_new_crop_factor(self, new_crop_factor:float) -> str:
        """Request server to adjust image cropping.
        
        Args:
            new_crop_factor: Crop factor (0.0-1.0)
            
        Returns:
            Server response status string
        """
        buffer = __RequestTypeEnum__.CameraCropFactorAdjustment.value.encode() + new_crop_factor.hex().encode()
        BufferManagement.send_buffer(self.connection, buffer)
        
        return BufferManagement.read_buffer(self.connection).decode()
    
    def update_genicam_config_file(self, yaml_obj) -> __PostType__:
        """Send updated camera configuration YAML to server.
        
        Args:
            yaml_obj: Configuration dictionary to send
            
        Returns:
            Server response status
        """
        BufferManagement.send_buffer(self.connection, __RequestTypeEnum__.RestartGenicam.value.encode())
        
        buffer = str(yaml.dump(yaml_obj)).encode()
        BufferManagement.send_buffer(self.connection, buffer)
        
        return BufferManagement.read_buffer(self.connection).decode()
    
    def try_to_reconnect_cameras(self) ->__PostType__:
        """Request server to retry connecting to failed cameras.
        
        Returns:
            Server response status
        """
        BufferManagement.send_buffer(self.connection, __RequestTypeEnum__.RestartFailedCams.value.encode())
        return BufferManagement.read_buffer(self.connection).decode()
    
    def get_alive_cams(self) -> list[str]:
        """Request list of currently active cameras from server.
        
        Returns:
            List of camera names currently available
        """
        BufferManagement.send_buffer(self.connection, __RequestTypeEnum__.GetAliveCameras.value.encode())
        return bytes(BufferManagement.read_buffer(self.connection)).decode().split(__MarkerTokens__.CameraSeparationToken.value)
    
    def subscribe_to_images(self, cam_names:list[str])->__Failures__:
        """Subscribe to image stream from specific cameras.
        
        Args:
            cam_names: List of camera names to subscribe to
            
        Returns:
            Success status
        """
        buffer = __RequestTypeEnum__.CameraSubscriptions.value.encode()
        for cam in cam_names:
            buffer += cam.encode() + (__MarkerTokens__.CameraSeparationToken.value.encode() if cam != cam_names[-1] else "".encode())
        
        BufferManagement.send_buffer(self.connection, buffer)
        
        return __Failures__.OK
    
    def request_alive_cams(self):
        """Request list of currently active cameras from server.
        
        Returns:
            Tuple of (status, camera_list) where camera_list is list of camera names
        """
        BufferManagement.send_buffer(self.connection, __RequestTypeEnum__.GetAliveCameras.value.encode())
        cams = BufferManagement.read_buffer(self.connection).decode().split(__MarkerTokens__.CameraSeparationToken.value)
        
        return __Failures__.OK, cams
    
    def request_latest_images(self):
        """Request the latest single frame from each subscribed camera.
        
        Returns:
            Dictionary mapping camera_name -> image_dict with image data
        """
        BufferManagement.send_buffer(self.connection, __RequestTypeEnum__.SingleFrame.value.encode())
        return self.get_images(False)
    
    def request_camera_queues(self):
        """Request all queued frames from each subscribed camera.
        
        Returns:
            Dictionary mapping camera_name -> [image_dict1, image_dict2, ...]
        """
        BufferManagement.send_buffer(self.connection, __RequestTypeEnum__.MultyFrame.value.encode())
        return self.get_images(True)
    
    def get_images(self, queue_request = False):
        """Receive image data from server (single frame or queued frames).
        
        Args:
            queue_request: True for multiple frames, False for single frame
            
        Returns:
            Dictionary of images from server, or None on error
        """
        if not self.is_connected:
            return None
        
        
        # Get type and num of datas
        post:str = BufferManagement.read_buffer(self.connection).decode()
        
        output: dict = {}
        
        
        if post.find("multy_frame ") != -1 and queue_request:
            num_of_queues = int().from_bytes(post.removeprefix("multy_frame ").encode(), 'little')
            
            if num_of_queues == 0:
                return None
            
            for i in range(num_of_queues):
                queue_name = BufferManagement.read_buffer(self.connection).decode()
                output[queue_name] = {}
                self.recieve_cam_dict(output[queue_name])
                
        elif post.find("single_frame") != -1 and not queue_request:
            self.recieve_cam_dict(output)
        
        else:
            return None
        
        #buffer = bytes()
        
        # # Reading cameras as yaml
        # for cam in range(cam_num):
        #     buffer += read_buffer(self.connection)
        
        
        # splitted_lines = buffer.split(b'0xFFF')
        
        # if splitted_lines[-1] == b'':
        #     splitted_lines.pop()
        
    
        return output
    
    def recieve_cam_dict(self, dict):
        """Receive image data for multiple cameras and populate dictionary.
        
        Reads serialized camera data from server including metadata (timestamps,
        dimensions) and JPEG-encoded image data.
        
        Args:
            dict: Dictionary to populate with camera data
        """
        # Get num of cams
        num_of_entries = int(BufferManagement.read_buffer(self.connection).decode().removeprefix("cam_num: "))
    
        if num_of_entries == 0:
            dict = None
            return
            
        for cam_id in range(num_of_entries):
            # extract cam name
            cam_name = BufferManagement.read_buffer(self.connection).decode()
                
            dict[cam_name] = {}
            
            # extracting timestamp
            dict[cam_name]["timestamp"] = float().fromhex(BufferManagement.read_buffer(self.connection).decode())
            
            dict[cam_name]["original_img_width"] = int(BufferManagement.read_buffer(self.connection).decode())
            dict[cam_name]["original_img_height"] = int(BufferManagement.read_buffer(self.connection).decode())
            
            # extracting image            
            buff_image = np.frombuffer(BufferManagement.read_buffer(self.connection), dtype=np.uint8)
            
            cv_image = cv2.imdecode(buff_image, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
            
            dict[cam_name]["img"] = cv_image

    def __await_connection__(self):
        """Background thread waiting for master server to connect.
        
        Blocks on socket.accept() until master initiates TCP connection.
        Updates is_connected flag when connection established.
        """
        while not self.is_connected:
            try:
                self.connection, _ = self.server.accept()
                self.is_connected = True
            except:
                __RequestServer__.logger.error("Timed out while waiting for genicam server to be available!")