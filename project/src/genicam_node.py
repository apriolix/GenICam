"""ROS 2 node for camera detection and initialization using Harvesters.

This module wraps the GenICam Harvesters library to:
    - Load camera drivers (CTI files) from the system
    - Auto-detect connected industrial cameras
    - Parse camera configuration from YAML
    - Create Camera objects for each configured device
    - Provide a ROS 2 node interface for logging and lifecycle management

The HarvesterNode manages the camera discovery and initialization process
before the actual streaming threads are started by other components.
"""

from harvesters.core import Harvester
import numpy as np

#import numpy.core.multiarray
import cv2
import glob

import yaml
import time

from data_structures  import *

from rclpy.node import Node
import os

class HarvesterNode(Node):
    """ROS 2 node for GenICam camera discovery and initialization.
    
    This node loads camera drivers (CTI files), detects connected cameras,
    and creates Camera objects according to YAML configuration.
    
    Attributes:
        cameras: Dictionary mapping camera names to Camera objects
        harvester_object: Harvesters.Harvester instance managing drivers
        config: Parsed YAML configuration for all cameras
    """
    
    def __init__(self):
        """Initialize the harvester node.
        
        Loads configuration, discovers CTI drivers, detects cameras,
        and creates corresponding Camera objects.
        """
        super().__init__('harvester_node')
       
        cv2.setUseOptimized(True)
       
        currend_working_dir = os.getcwd() # Read the set working directory path (/GeniCamROS)
        
        file_path = os.path.join(currend_working_dir, "config", "config.yaml") # create final path
        
        file = open(file_path, "r")
        self.config = yaml.load(file, Loader=yaml.Loader)
        file.close()
        
        self.cameras:dict[str, Camera] = {}
        self.harvester_object = Harvester()
        
        self.cti_files = glob.glob("/opt/**/*.cti", recursive=True) # Find existing cti-files
        
        ## Reading cti files and load available cameras
        if self.cti_files == []:
            self.get_logger().error("No cti files installed!")
        else:
            for path in self.cti_files:
                self.harvester_object.add_file(path)
            
            self.get_logger().info("Found following cti-files: " + str(self.harvester_object.cti_files))
            
            self.create_cameras()
            
        

            # ##Create acquire threads
            # self.threads:list[threading.Thread] = []
            # self.shutdown_event = threading.Event()
            
            # for cam in self.cameras:
            #     if not cam.failed:
            #         self.threads.append(threading.Thread(target=cam.acquire_image, args=(self.shutdown_event,)))
            #         self.threads[-1].start()
           
    def create_cameras(self):
        """Discover and create Camera objects from detected hardware.
        
        Queries Harvesters for available cameras, matches against YAML config,
        and instantiates Camera objects for streaming.
        
        Retries with 15-second intervals if no cameras are initially found.
        """
        self.cameras.clear()
        
        retry_interval = 15
        retry_enabled = True
        
        ## Get available cameras
        while retry_enabled:
            self.harvester_object.update() 
        
            if self.harvester_object.device_info_list == []:
                self.get_logger().error("No cameras available! Retry in " + str(retry_interval) + " seconds!")
                time.sleep(retry_interval)
            else:
                retry_enabled = False
                self.get_logger().info("\nFollowing cameras were found: \n")
                id = 0
                for cam in self.harvester_object.device_info_list:
                    print("Camera " + str(id) + ": " + str(cam) + "\n------------------\n")
                    id += 1
        
        ##Remove head
        camera_list = self.config["harvester_node"]["ros__parameters"]
        
        ## Create cameras
        for camera_item in camera_list.values():
            self.cameras[camera_item["custom_cam_name"]] = Camera(camera_item, self.harvester_object)
             
            
    def on_shutdown(self):
        """Cleanup handler called on ROS 2 node shutdown.
        
        Stops all camera acquisition threads and performs cleanup.
        """
        
        for thread in self.threads:
            self.shutdown_event.set()
            thread.join()
            
        for cam in self.cameras:
            cam.on_shutdown()