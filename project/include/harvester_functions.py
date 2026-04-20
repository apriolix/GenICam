"""Harvester utility functions for image acquisition.

This module provides helper functions for working with the Harvesters library:
    - acquire_image: Fetch a single frame from a camera stream with format conversion
    - Handles: Multiple pixel formats (RGB, BGRA, mono), resizing, format conversion

These functions abstract away the complexity of GenICam buffer management
and numpy array reshaping.
"""

import cv2
import numpy as np
from rclpy.node import Node
from harvesters.core import Harvester

from harvesters.util.pfnc import mono_location_formats, \
    rgb_formats, bgr_formats, \
    rgba_formats, bgra_formats

def acquire_image(stream_object, desired_image_width :int = None, node_object: Node = None) -> cv2.Mat:
    """Acquire a single image from a Harvesters stream object.
    
    Handles format conversion from various GenICam pixel formats to OpenCV BGR.
    
    Args:
        stream_object: ImageAcquirer object from Harvester.create()
        desired_image_width: Optional target width for resizing
        node_object: Optional ROS 2 Node for logging
        
    Returns:
        cv2.Mat: BGR image as numpy array, or empty Mat on error
    """
    if not isinstance(stream_object, type(Harvester().create())):
        logger = node_object.get_logger() if node_object else rclpy.logging.get_logger("function_acquire_image")
        logger.error("Invalid stream Object")
        return cv2.Mat()  
    
    with stream_object.fetch() as buffer:
        # Work with the Buffer object. It consists of everything you need.
        w = buffer.payload.components[0].width
        hi = buffer.payload.components[0].height
        data_format = buffer.payload.components[0].data_format
        component = buffer.payload.components[0]
            
        if data_format in rgb_formats or \
            data_format in rgba_formats or \
            data_format in bgr_formats or \
            data_format in bgra_formats:
            image = np.copy(component.data.reshape(hi,w, int(component.num_components_per_pixel)))
        else:
            image = np.copy(buffer.payload.components[0].data.reshape(hi,w))
                
        if data_format in rgb_formats:
            image = cv2.cvtColor(np.copy(image), cv2.COLOR_RGB2BGR)
        elif data_format in rgba_formats:
            image = cv2.cvtColor(np.copy(image), cv2.COLOR_RGBA2BGRA)
            
        if desired_image_width != None:
            rows,cols = image.shape[:2]
            scale_factor = cols / rows
            new_rows = cols / scale_factor
            
            image = cv2.resize(image, (new_rows, desired_image_width))
        
        return image