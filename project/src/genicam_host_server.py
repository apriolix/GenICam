"""Server-side socket management and client/camera thread handling.

This module implements the server architecture:
    - __Client__: Represents a connected client with TCP socket and subscriptions
    - __CameraQueue__: Thread-safe queue of images per camera per subscriber
    - __ClientHandler__: Master thread controller managing all client threads

The server uses a multi-threaded model:
    - One __master_thread__ for continuous image capture from all cameras
    - One __run_client__ thread per connected client for request handling
    - Queues bridge camera capture and client delivery
"""

from genicam_network_basics import *
from genicam_network_basics import __ClientHealth__,__RequestTypeEnum__,__MarkerTokens__, __PostType__

from collections import deque 

class __Client__():
    """Represents a single connected TCP client to the server.
    
    Stores per-client state including TCP socket, subscribed cameras,
    image scaling preference, and health status.
    
    Attributes:
        ip: Client's (host, port) tuple
        tcp_socket: TCP socket connection to client
        subscribed_cameras: Deque of camera names client is subscribed to
        desired_img_scaler: Image scaling factor (1.0 = full resolution)
        health: __ClientHealth__ enum value
    """
    
    def __init__(self, ip:tuple):
        """Initialize a client connection handler.
        
        Args:
            ip: Tuple of (client_hostname, client_port)
        """
        self.new_image_event = threading.Event()
        
        
        self.health = __ClientHealth__.Good
        self.ip = ip
        self.thread = threading.Thread()
                
        self.init_time = time.time()
        
        self.tcp_socket:socket = socket(AF_INET, SOCK_STREAM)
        self.tcp_socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        self.tcp_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.tcp_socket.settimeout(SOCKET_TIMEOUT)
        
        self.subscribed_cameras:deque[str] = []
        self.desired_img_scaler = 1.0
    
class __CameraQueueItem__():
    """Single image in a camera queue with per-subscriber delivery tracking.
    
    Attributes:
        receivers: Deque of (ip, port) tuples still waiting for this image
        image: The actual image data (numpy array)
    """
    
    def __init__(self, subscribers, img):
        """Initialize a queue item.
        
        Args:
            subscribers: List of subscriber (ip, port) tuples
            img: Image data as numpy array or encoded bytes
        """
        self.receivers:deque[tuple[str,int]] = deque(subscribers)
        self.image = img
        
class __CameraQueue__():
    """Thread-safe queue of images for a single camera.
    
    Manages delivery of images from one camera to multiple subscribers.
    Uses locks to ensure thread-safe access from image capture and client threads.
    
    Attributes:
        queue: Deque of __CameraQueueItem__ containing images and receivers
        registered_subscribers: List of (ip, port) tuples subscribed to this camera
        max_queue_size: Maximum number of image frames to buffer
    """
    
    def __init__(self, max_queue_size = 1):
        """Initialize an image queue for a single camera.
        
        Args:
            max_queue_size: Maximum number of images to buffer (default: 1 = latest only)
        """
        self.max_queue_size = max_queue_size
        self.queue:deque[__CameraQueueItem__] = []
        
        self.num_of_subscribers = 0
        self.queue_lock = threading.Lock()
        
        self.is_connected = True
        
        self.registered_subscribers:deque[tuple[str,int]] = []
    
    def set_disconnected(self):
        with self.queue_lock:
            self.is_connected = False
       
    def add_subscriber(self, ip:tuple[str,int]):
        """Register a new subscriber for this camera's images.
        
        Args:
            ip: Client address tuple (hostname/IP, port)
        """
        with self.queue_lock:
            if not ip in self.registered_subscribers:
                self.registered_subscribers.append(ip)
                self.num_of_subscribers += 1
    
    def deregister_subscriber(self, ip):
        """Unregister a subscriber when client disconnects.
        
        Args:
            ip: Client address tuple
        """
        with self.queue_lock:
            if ip in self.registered_subscribers:
                self.registered_subscribers.remove(ip)
                self.num_of_subscribers -= 1 if self.num_of_subscribers > 0 else 0
                
    def add_image(self, img):
        """Add new image to queue for all current subscribers.
        
        Args:
            img: Image data (numpy array or encoded bytes)
        """
        with self.queue_lock:
            self.is_connected = True
            
            if len(self.queue) > self.max_queue_size:
                self.queue.pop(0)
            self.queue.append(__CameraQueueItem__(self.registered_subscribers, img))
    
    def get_image(self, client_ip):
        """Retrieve latest image for a specific client.
        
        Marks image as delivered to this client. Removes image from queue
        when all subscribers have received it.
        
        Args:
            client_ip: Client address tuple
            
        Returns:
            Image data, or (None, None) if no new image available
        """
        with self.queue_lock:
            if self.queue == [] or client_ip not in self.queue[-1].receivers or not self.is_connected:
                return (None, None)
            
            img = self.queue[-1].image
            self.queue[-1].receivers.remove(client_ip)
               
            if len(self.queue[-1].receivers) == 0:
                self.queue.pop()
                
            return img
    
    def get_queue(self, client_ip):
        """Retrieve all queued images for a specific client.
        
        Args:
            client_ip: Client address tuple
            
        Returns:
            List of all queued images for this client, or None if empty
        """
        with self.queue_lock:
            if self.queue == [] or not self.is_connected:
                return None
            
            result = []
            to_removed_items = []
            
            for item in self.queue:
                if client_ip in item.receivers:
                    result.append(item.image)
                    item.receivers.remove(client_ip)
                    
                    if len(item.receivers) == 0:
                        to_removed_items.append(item)                
                
            
            for item in to_removed_items:
                self.queue.remove(item)
            
            return result if len(result) > 0 else None

class __ClientHandler__():    
    # __highest_image_frame_scaler_priority__ = 0
    logger = rclpy.logging.get_logger("GeniCam__Clientandler__")
    
    
    def __init__(self, genicam_node:HarvesterNode, server_heart_beat:float, queue_size:int):
        self.camera_lock = threading.Lock()
        self.genicam_restarted = True
        
        self.server_minimal_heart_beat = server_heart_beat
        
        self.genicam_node = genicam_node
        self.cameras = self.genicam_node.cameras
        
        self.queue_lock = threading.Lock()
        self.camera_queues:dict[str, __CameraQueue__] = {}
        self.camera_queue_size = queue_size
        
        for queue_name in self.cameras.keys():
            self.camera_queues[queue_name] = __CameraQueue__(queue_size)
        
        self.clients_lock = threading.Lock()
        self.clients:deque[__Client__] = []
        
        self.main_thread = threading.Thread(target=self.__master_thread__)
        self.main_thread.start()
    
    # Creating new client for subcriber
    def add_client(self, ip):
        
        with self.clients_lock:
            found = False
            
            # removing of died clients
            to_remove:list[__Client__] = []
            for client in self.clients:
                if client.health == __ClientHealth__.Crashed:
                    if client.thread.is_alive():
                        client.thread.join()
                    to_remove.append(client)
                    
                elif client.ip == ip and time.time() - client.init_time > CLIENT_REACCEPTION_DELAY_TIME:
                    found = True
                    
            for client in to_remove:                  
                self.clients.remove(client)
                    
            # Add new client
            if not found and not ip in [client.ip for client in self.clients]:
                self.clients.append(__Client__(ip))
                
                self.clients[-1].thread = threading.Thread(target=self.__run_client__, args=(self.clients[-1],))
                self.clients[-1].thread.start()
                
                __ClientHandler__.logger.info("Client added: " + str(self.clients[-1].ip))
                return True
            
            return False
        
    
    def __run_client__(self, client:__Client__):
        tcp_socket:socket = client.tcp_socket
        
        try:
            # Connect to client (ip, port)
            tcp_socket.connect(client.ip)
            
            
            
            # Main loop
            while True:            
                request:str = BufferManagement.read_buffer(tcp_socket).decode()
                
                if request == "":
                    raise Exception("Client died -> Timed out")
                
                # Send camera images
                if request.find(__RequestTypeEnum__.SingleFrame.value) != -1:
                    self.__send_images__(tcp_socket, client)
                    
                elif request.find(__RequestTypeEnum__.MultyFrame.value) != -1:
                    self.__send_image_queues__(tcp_socket, client)
                    
                elif request.find(__RequestTypeEnum__.CameraSubscriptions.value) != -1:
                    client.subscribed_cameras = request.removeprefix(__RequestTypeEnum__.CameraSubscriptions.value) \
                        .split(__MarkerTokens__.CameraSeparationToken.value)   
                    
                    with self.queue_lock:
                        for cam in client.subscribed_cameras:
                            self.camera_queues[cam].add_subscriber(client.ip)   
                                  
                elif request.find(__RequestTypeEnum__.RestartFailedCams.value) != -1:
                    with self.camera_lock:
                        if not self.genicam_restarted:
                            self.genicam_restarted = True
                            
                            ## Try if cameras are still connected. If they got disconnected an exception will appear
                            try:
                                for cam in self.cameras.values():
                                    cam.close()
                            except:
                                pass
                            
                            self.genicam_node.create_cameras()
                        
                        BufferManagement.send_buffer(tcp_socket, __PostType__.OK.value.encode())  
                        
                elif request.find(__RequestTypeEnum__.GetAliveCameras.value) != -1:
                    with self.camera_lock:
                        alive_cams = "cameras:"
                        for cam in self.cameras.values():
                            if not cam.failed:
                                alive_cams += __MarkerTokens__.CameraSeparationToken.value + cam.custom_cam_name
                                
                    BufferManagement.send_buffer(tcp_socket, alive_cams.encode())
                        
                elif request.find(__RequestTypeEnum__.RestartGenicam.value) != -1:
                    yaml_data = yaml.safe_load(BufferManagement.read_buffer(tcp_socket).decode())
                    
                    with self.camera_lock:
                        if not self.genicam_restarted:
                            self.genicam_restarted = True
                            
                            ## Try if cameras are still connected. If they got disconnected an exception will appear
                            try:
                                for cam in self.cameras.values():
                                    cam.close()
                            except:
                                pass
                                
                            self.genicam_node.config = yaml_data
                            self.genicam_node.create_cameras()
                            
                            for cam_name in self.cameras.keys():
                                if cam_name not in self.camera_queues.keys():
                                    self.camera_queues[cam_name] = __CameraQueue__(self.camera_queue_size)
                                
                        
                        BufferManagement.send_buffer(tcp_socket, __PostType__.OK.value.encode())  
                                        
                # Adjust camera size
                elif request.find(__RequestTypeEnum__.DataFrameSizeAdjustment.value) != -1:
                    scaler = float().fromhex(request.removeprefix(__RequestTypeEnum__.DataFrameSizeAdjustment.value))
                    
                    client.desired_img_scaler = scaler
                    
                    BufferManagement.send_buffer(tcp_socket, __PostType__.OK.value.encode())

                elif request.find(__RequestTypeEnum__.CameraCropFactorAdjustment.value) != -1:
                    success, error_msg = self.__adjust_camera_crop__(request)

                    if not success:
                        BufferManagement.send_exception(client.tcp_socket, error_msg.encode())
                    else:
                        BufferManagement.send_buffer(client.tcp_socket, __PostType__.OK.value.encode())

        except Exception as ex:
            print(f"Client run exception: {ex}")

            client.health = __ClientHealth__.Crashed
            client.tcp_socket.close()
            __ClientHandler__.logger.info("Client died: " + str(client.ip))
            
            # deregister from queues
            for queue in self.camera_queues.values():
                queue.deregister_subscriber(client.ip)
            return
                    
                    
                        
                    
                
    def __adjust_camera_crop__(self, request:str) -> tuple[bool, str]:
        scaler = float().fromhex(request.removeprefix(__RequestTypeEnum__.DataFrameSizeAdjustment.value))
        success = True
        cam_status = {}
        with self.camera_lock:
            
            for cam_name, camera in self.cameras.items():
                cam_status[cam_name] = {}
                try:
                    if not camera.failed:
                        cam_status[cam_name]["connected"] = True
                        cam_status[cam_name]["crop_failed"] = False
                        
                       
                        if not camera.set_new_crop_factor(scaler):
                            cam_status[cam_name]["crop_failed"] = True
                            success = False
                        
                        #camera.stream_object.start()
                    else:
                        cam_status[cam_name]["connected"] = False
                            
                except:
                    cam_status[cam_name]["exception"] = True
                    success = False
        
        return (success, yaml.dump(cam_status))
                       
    
    def __send_images__(self, tcp_socket, client:__Client__):                
        # Image format: timestamp, image
        images:deque = [] 
        
        # capture images
        while images == []: 
            client.new_image_event.wait()
            client.new_image_event.clear()
            
            for cam_name in client.subscribed_cameras:
                time, img = self.camera_queues[cam_name].get_image(client.ip)
                if not img is None:
                    rows, cols = img.shape[0:2]

                    try:
                        img = cv2.resize(img, (int(cols * client.desired_img_scaler), int(rows * client.desired_img_scaler)))
                    except Exception as ex:
                        exception_msg = f"Exception for client.desired_img_scaler: {ex} \n Resetting it to 1"
                        print(exception_msg)
                        BufferManagement.send_exception(client.tcp_socket, exception_msg.encode())

                        client.desired_img_scaler = 1.0
                        return
                    
                    images.append((cam_name, (time, img)))
                    
                    # rows, cols = images[-1][1][1].shape[0:2]
                    # res = cv2.resize(np.copy(images[-1][1][1]), (int(cols * client.desired_img_scaler), int(rows * client.desired_img_scaler)))
                    
                    #images[-1][1][1] = cv2.resize(np.copy(images[-1][1][1]), (int(cols * client.desired_img_scaler), int(rows * client.desired_img_scaler)))
        
        BufferManagement.send_buffer(tcp_socket, "single_frame".encode())
        self.__send_image_queue__(tcp_socket, images)
        
    def __send_image_queues__(self, tcp_socket, client:__Client__):
        images:deque[deque] = []
        
        while images == []: 
            client.new_image_event.wait()
            client.new_image_event.clear()
            
                    
            for cam_name in client.subscribed_cameras:
                queue = self.camera_queues[cam_name].get_queue(client.ip)
                
                if not queue is None:
                    images.append([])
                    for i in range(len(queue)):
                        time, img = queue[i]
                        
                        rows, cols = img.shape[0:2]

                        try:
                            img = cv2.resize(img, (int(cols * client.desired_img_scaler), int(rows * client.desired_img_scaler)))
                        except Exception as ex:
                            exception_msg = f"Exception for client.desired_img_scaler: {ex} \n Resetting it to 1"
                            print(exception_msg)
                            BufferManagement.send_exception(client.tcp_socket, exception_msg.encode())

                            client.desired_img_scaler = 1.0
                            return
                                                
                        if i == 0:
                            images[-1].append((cam_name, (time, img)))
                        else:
                            images[-1].append((cam_name + f"_{i}", (time, img)))
                        
                        
            
        
        BufferManagement.send_buffer(tcp_socket, "multy_frame ".encode() + len(images).to_bytes(4, 'little'))
        for queue in images:
            # first cam name
            BufferManagement.send_buffer(tcp_socket, queue[0][0].encode())
            
            self.__send_image_queue__(tcp_socket, queue)
        
            
    def __send_image_queue__(self, tcp_socket, images):
        cam_num = "cam_num: ".encode() + str(len(images)).encode()
        BufferManagement.send_buffer(tcp_socket, cam_num)
            
        # sending images
        for img in images:
            # preparing data
            # t1 = time.time()
            cam_name = str(img[0])
            timestamp = float(img[1][0]).hex().encode() 
            image = cv2.imencode(".jpg", img[1][1])[1].tobytes()
            
            with self.camera_lock:
                try:
                    original_img_width = str(self.cameras[cam_name].cam_settings.sensor_horizontal_pixels).encode()
                    original_img_height = str(self.cameras[cam_name].cam_settings.sensor_vertical_pixels).encode()
                # In case of passing a queue, use the first items camera name as true custom name
                except:
                    original_img_width = str(self.cameras[images[0][0]].cam_settings.sensor_horizontal_pixels).encode()
                    original_img_height = str(self.cameras[images[0][0]].cam_settings.sensor_vertical_pixels).encode()
            
            
            # send data
            # tcp_socket.sendall(package_size)
            BufferManagement.send_buffer(tcp_socket, cam_name.encode())
            BufferManagement.send_buffer(tcp_socket, timestamp)
            
            BufferManagement.send_buffer(tcp_socket, original_img_width)
            BufferManagement.send_buffer(tcp_socket, original_img_height)
            
            BufferManagement.send_buffer(tcp_socket, image)
            
            # send_time = time.time() - t1
            # print("send time: ", send_time, " send_read_time: ", send_time * 2 )
            
            
    def __master_thread__(self):
        
        while True:
            t1 = time.time()
    
            with self.camera_lock:
                for name, cam in self.cameras.items():
                    acquisition_data = cam.acquire_image(self.server_minimal_heart_beat)
                    
                    if acquisition_data is not None:
                        self.camera_queues[name].add_image(acquisition_data)
                    else:
                        self.camera_queues[name].set_disconnected()
                                          
            
            with self.clients_lock:
                for client in self.clients:
                    client.new_image_event.set()
                    
            