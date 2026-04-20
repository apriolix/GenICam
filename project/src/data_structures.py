"""Data structures for camera configuration and state management.

This module defines the core data classes used throughout the GenICam system:
    - CameraIdentificationTags: Uniquely identify cameras by vendor/serial/display name
    - CameraSettings: Store and manage camera acquisition parameters
    - Camera: Complete camera object with state, streaming, and GPU optimization

These structures bridge the gap between YAML configuration and the actual
GenICam/Harvesters library interfaces.
"""

import cv2
import numpy as np
from rclpy.node import Node

import rclpy.logging
from sensor_msgs.msg import CompressedImage, Image
from cv_bridge import CvBridge
import rclpy.publisher

import harvesters.core
from harvesters.core import Harvester

from harvesters.util.pfnc import mono_location_formats, \
    rgb_formats, bgr_formats, \
    rgba_formats, bgra_formats

import time
import threading

from rclpy.qos import *

from math import *

class CameraIdentificationTags():
    """Uniquely identify a camera using vendor, serial number, and display name.
    
    This class wraps the identification parameters that GenICam uses to locate
    a specific camera device. It creates a browse_list for the Harvesters library.
    
    Attributes:
        display_name: Human-readable camera name
        vendor: Camera manufacturer (e.g., "Baumer", "FLIR")
        serial_number: Unique device serial number
        browse_list: Dictionary passed to Harvester.create() for device lookup
        failed: Boolean indicating if identification tags are valid
    """
    
    def __init__(self, yaml_type, logger):
        """Initialize camera identification tags from YAML config.
        
        Args:
            yaml_type: Dictionary containing display_name, vendor, serial_number keys
            logger: ROS 2 logger for error reporting
        """
        self.display_name:str = yaml_type["display_name"]
        self.vendor:str = yaml_type["vendor"]
        self.serial_number:str = yaml_type["serial_number"]
        
        self.browse_list:dict[str,str] = {}
        
        self.failed = False
        
        self.logger = logger
        
        if self.display_name != "":
            self.browse_list["display_name"] = self.display_name
        if self.vendor != "":
            self.browse_list["vendor"] = self.vendor
        if self.serial_number != "":
            self.browse_list["serial_number"] = self.serial_number
            
        if (self.display_name == "" and self. serial_number == "") or (self.display_name == "" and self. serial_number == "" and self.vendor == ""):
            self.failed = True
            self.logger.error("CameraIdentificationTags: self.display_name == \"\" and self. serial_number == \"\") or (self.display_name == \"\" and self. serial_number == \"\" and self.vendor == \"\" -> Not enough tags for identification of given camera! ")
    
    def get_stream_object(self, harvester_object:Harvester) -> harvesters.core.ImageAcquirer:
        """Create a stream object (ImageAcquirer) from identified camera.
        
        Uses the identification tags (vendor, serial, display name) to locate
        and create a stream object from the Harvester.
        
        Args:
            harvester_object: Initialized Harvester instance with loaded drivers
            
        Returns:
            ImageAcquirer object for streaming from this camera, or None on failure
        """
        error_massage = "CameraIdentificationTags: Unable to create stream object!"
        if self.failed:
            self.logger.error(error_massage)
            return None
           
        try:
            return harvester_object.create(self.browse_list)   
        except: 
            self.logger.error(error_massage)
            return None
         
        
        
        

class CameraSettings():
    """Store and manage all GenICam acquisition parameters for a camera.
    
    This class represents the configuration of a camera, including:
    - Acquisition mode and frame rate
    - Exposure and gain settings (auto and manual ranges)
    - Color balance and brightness parameters
    - Pixel format and cropping factors
    
    Attributes:
        acquisition_mode: "Continuous", "SingleFrame", or "MultiFrame"
        acquisition_frame_rate_enable: Whether to use frame rate limiting
        acquisition_frame_rate: Target frames per second
        exposure_auto: Automatic exposure mode
        gain_auto: Automatic gain mode
        pixel_format: GenICam pixel format string
        user_on_device_crop_factor: Cropping factor (0.0-1.0)
    """
    
    def __init__(self, yaml_type, logger):
        """Initialize camera settings from YAML configuration.
        
        Args:
            yaml_type: Dictionary containing all acquisition parameters
            logger: ROS 2 logger for warnings/errors
        """
        self.acquisition_mode:str = yaml_type["acquisition"]["AcquisitionMode"]
        self.acquisition_frame_rate_enable:bool = yaml_type["acquisition"]["AcquisitionFrameRateEnable"]
        self.acquisition_frame_rate:int = yaml_type["acquisition"]["AcquisitionFrameRate"]
        
        self.AVILABLE_ACQUISITION_MODES:list[str] = ["Continuous", "SingleFrame", "MultiFrame"]
        
        
        if self.acquisition_frame_rate_enable and self.acquisition_frame_rate <= 0:
            logger.error("Wrong AcquisitionFrameRate! Setting to 1!")
            self.acquisition_frame_rate = 1
        
        self.pixel_format:str = yaml_type["PixelFormat"]
        
        self.exposure_auto:str = yaml_type["ExposureAuto"]
        self.exposure_auto_max_value:int = yaml_type["ExposureAutoMaxValue"]
        self.exposure_auto_min_value:int = yaml_type["ExposureAutoMinValue"]
        
        self.gain_auto:str = yaml_type["GainAuto"]
        self.gain_auto_max_value:int = yaml_type["GainAutoMaxValue"]
        self.gain_auto_min_value:int =  yaml_type["GainAutoMinValue"]
        
        self.brightness_auto_priority:str = yaml_type["BrightnessAutoPriority"]
        
        self.brightness_auto_nominal_value:float = yaml_type["BrightnessAutoNominalValue"]
        self.balance_white_auto:str = yaml_type["BalanceWhiteAuto"]
        
        self.user_on_device_crop_factor:bool = yaml_type["on_device_crop_factor"]
    
        self.sensor_horizontal_pixels = -1
        self.sensor_vertical_pixels = -1
        
        self.horizontal_pixel_steps = -1
        self.vertical_pixel_steps = -1
    
        self.logger = logger
        
        self.gain_error = False
        self.exposure_error = False
        
        self.has_crop_offset = True
        self.crop_request_possible = True if self.user_on_device_crop_factor > 0 else False
        
        if self.gain_auto_max_value <= self.gain_auto_min_value or (self.gain_auto_max_value <= -1 and self.gain_auto_min_value != -1):
            self.gain_error = True
            self.logger.warn("CameraSettings: self.gain_auto_max_value <= self.gain_auto_min_value -> Wrong gain auto settings or unused settings!")
        if self.exposure_auto_max_value <= self.exposure_auto_min_value or (self.exposure_auto_max_value <= -1 and self.exposure_auto_min_value != -1):
            self.exposure_error = True
            self.logger.warn("CameraSettings: self.exposure_auto_max_value <= self.exposure_auto_min_value -> Wrong exposure auto settings or unused settings!")        
    
    def set_settings(self, stream_object:harvesters.core.ImageAcquirer):
        if stream_object is None:
            return
        
        #stream_object.stop()
        node_error_sting = "Camera object has no node attribute called: \""
        
        if stream_object.remote_device.node_map.has_node("AcquisitionMode"):
            if self.acquisition_mode in self.AVILABLE_ACQUISITION_MODES:
                stream_object.remote_device.node_map.get_node("AcquisitionMode").set_value(self.acquisition_mode) 
            else:
                self.logger.warn("Empty AcquisitionMode settings or unsupported type! Supported types are: " +  
                                str(self.AVILABLE_ACQUISITION_MODES) + ". Falling back to default settings!")
        else:
            self.logger.warn(node_error_sting + "AcquisitionMode" + "\"!")
        
        if self.acquisition_mode == "Continuous":
            if self.acquisition_frame_rate_enable:
                
                if stream_object.remote_device.node_map.has_node("AcquisitionFrameRateEnable"):
                    stream_object.remote_device.node_map.get_node("AcquisitionFrameRateEnable").set_value(self.acquisition_frame_rate_enable)
                    stream_object.remote_device.node_map.get_node("AcquisitionFrameRate").set_value(self.acquisition_frame_rate)
                else:
                    self.logger.warn(node_error_sting + "AcquisitionFrameRateEnable" + "\"!")
                
                    
        if stream_object.remote_device.node_map.has_node("PixelFormat"):
            stream_object.remote_device.node_map.get_node("PixelFormat").set_value(self.pixel_format) if self.pixel_format != "" else self.logger.warn("CameraSettings: Empty PixelFormat! Falling back to default settings.")
        else:
            self.logger.warn(node_error_sting + "PixelFormat" + "\"!")
            
        if stream_object.remote_device.node_map.has_node("ExposureAuto"):
            stream_object.remote_device.node_map.get_node("ExposureAuto").set_value(self.exposure_auto) if self.exposure_auto != "" else self.logger.warn("CameraSettings: Empty ExposureAuto settings! Falling back to default settings.")
            if not self.exposure_error:
                stream_object.remote_device.node_map.get_node("ExposureAutoMaxValue").set_value(self.exposure_auto_max_value) if self.exposure_auto_max_value > self.exposure_auto_min_value else self.logger.warn("CameraSettings: Empty ExposureAutoMaxValue settings! Falling back to default settings.")
                stream_object.remote_device.node_map.get_node("ExposureAutoMinValue").set_value(self.exposure_auto_min_value) if self.exposure_auto_min_value > -1 and self.exposure_auto_min_value < self.exposure_auto_max_value else self.logger.warn("CameraSettings: Empty ExposureAutoMinValue settings! Falling back to default settings.")
        else:
            self.logger.warn(node_error_sting + "ExposureAuto" + "\"!")
        
        if stream_object.remote_device.node_map.has_node("GainAuto"):
            stream_object.remote_device.node_map.get_node("GainAuto").set_value(self.gain_auto) if self.gain_auto != "" else self.logger.warn("CameraSettings: Empty GainAuto settings! Falling back to default settings.")
            if not self.gain_error:
                stream_object.remote_device.node_map.get_node("GainAutoMaxValue").set_value(self.gain_auto_max_value) if self.gain_auto_max_value > self.gain_auto_min_value and self.gain_auto_max_value >= 1 else self.logger.warn("CameraSettings: Empty GainAutoMaxValue settings! Falling back to default settings.")
                stream_object.remote_device.node_map.get_node("GainAutoMinValue").set_value(self.gain_auto_min_value) if self.gain_auto_min_value > 0 and self.gain_auto_min_value < self.gain_auto_max_value else self.logger.warn("CameraSettings: Empty GainAutoMinValue settings! Falling back to default settings.")
        else:
            self.logger.warn(node_error_sting + "GainAuto" + "\"!")
            
        if stream_object.remote_device.node_map.has_node("BrightnessAutoPriority"):
            stream_object.remote_device.node_map.get_node("BrightnessAutoPriority").set_value(self.brightness_auto_priority) if self.brightness_auto_priority != "" else self.logger.warn("CameraSettings: Empty BrightnessAutoPriority settings! Falling back to default settings.")
        else:
            self.logger.warn(node_error_sting + "BrightnessAutoPriority" + "\"!")
        
        if stream_object.remote_device.node_map.has_node("BrightnessAutoNominalValue"): 
            stream_object.remote_device.node_map.get_node("BrightnessAutoNominalValue").set_value(self.brightness_auto_nominal_value)  if self.brightness_auto_nominal_value > -1 else self.logger.warn("CameraSettings: Empty BrightnessAutoNominalValue settings! Falling back to default settings.")
        else:
            self.logger.warn(node_error_sting + "BrightnessAutoNominalValue" + "\"!")
        
        if stream_object.remote_device.node_map.has_node("BalanceWhiteAuto"): 
            stream_object.remote_device.node_map.get_node("BalanceWhiteAuto").set_value(self.balance_white_auto) if self.balance_white_auto != "" else self.logger.warn("CameraSettings: Empty BalanceWhiteAuto settings! Falling back to default settings.")
        else:
            self.logger.warn(node_error_sting + "BalanceWhiteAuto" + "\"!")
            
        node_map = stream_object.remote_device.node_map
        if node_map.has_node("SensorHeight") and node_map.has_node("SensorWidth"):
            self.sensor_horizontal_pixels = int(node_map.get_node("SensorWidth").value)
            self.sensor_vertical_pixels = int(node_map.get_node("SensorHeight").value)
            
            # Resetting offsets
            try:
                if node_map.has_node("OffsetY") and node_map.has_node("OffsetY"):
                    node_map.get_node("OffsetY").set_value(0)
                    node_map.get_node("OffsetX").set_value(0)
            except:
                self.has_crop_offset = False
                self.logger.warn(node_error_sting + f" OffsetY and OffsetX or they are only readable! Could result in problems while crop request of image on camera.")
            
            if node_map.has_node("Width") and node_map.has_node("Height"):
                # figure the step width out
                self.vertical_pixel_steps
                self.horizontal_pixel_steps
                
                pixel_steps_found = False
                
                for i in range(10):
                    step = int(2**i)
                    
                    if self.vertical_pixel_steps == -1:
                        try:
                            node_map.get_node("Height").set_value(self.sensor_vertical_pixels - step)
                            node_map.get_node("Height").set_value(self.sensor_vertical_pixels - step * int(2))
                            
                            self.vertical_pixel_steps = step
                        except:
                            pass
                            
                            
                    if self.horizontal_pixel_steps == -1:
                        try:
                            node_map.get_node("Width").set_value(self.sensor_horizontal_pixels - step)
                            node_map.get_node("Width").set_value(self.sensor_horizontal_pixels - step * int(2))
                            
                            self.horizontal_pixel_steps = step
                        except:
                            pass
                            
                    
                    if self.vertical_pixel_steps != -1 and self.horizontal_pixel_steps != -1:
                        pixel_steps_found = True
                        break  
                
                # reset size
                if pixel_steps_found:                    
                    self.set_camera_crop(stream_object)
                else:
                    self.crop_request_possible = False
                    self.logger.error("Unable to find pixel_steps for image cropping => Disabling image cropping! Nodes may be only readable!")
            else:
                self.crop_request_possible = False
                self.logger.warn(node_error_sting + f" Height and Width! Crop request of image on camera not possible.")
                
                
    
           
    def update_max_gain_auto(self, stream_object:harvesters.core.ImageAcquirer, new_value:int = None):
        stream_object.stop()
        self.gain_auto_max_value = new_value if new_value != None else self.gain_auto_max_value
        
        if self.gain_auto_max_value > 0 and self.gain_auto_max_value > self.gain_auto_min_value:
            stream_object.remote_device.node_map.get_node("GainAutoMaxValue").set_value(self.gain_auto_max_value)
            
        stream_object.start()
        
    def set_camera_crop(self, stream_object:harvesters.core.ImageAcquirer, crop_factor = None) -> bool:
        if stream_object is None or not self.crop_request_possible:
            return False
        
        if crop_factor is not None:
            self.user_on_device_crop_factor = crop_factor
        
        if self.user_on_device_crop_factor > 1.0 or self.user_on_device_crop_factor <= 0:
            self.logger.error("Invalide crop factor! Factor needs to be in-between 0.0 and 1.0!")
            return False
        
        try:
            if stream_object.is_acquiring():
                stream_object.stop()
                
            node_map = stream_object.remote_device.node_map
            
            if self.horizontal_pixel_steps != -1 and self.vertical_pixel_steps != -1:
                height = self.sensor_vertical_pixels
                width = self.sensor_horizontal_pixels
                
                if self.has_crop_offset:
                    old_row_offset = 0.0
                    old_cols_offset = 0.0
                
                new_height = height * self.user_on_device_crop_factor
                new_width = width * self.user_on_device_crop_factor
                
                height_diff = self.sensor_vertical_pixels - new_height
                width_diff =  self.sensor_horizontal_pixels - new_width
                
                height_steps = round( height_diff / self.vertical_pixel_steps)
                width_steps = round( width_diff / self.horizontal_pixel_steps)
                
                new_height =  self.sensor_vertical_pixels - self.vertical_pixel_steps * height_steps 
                new_width = self.sensor_horizontal_pixels - self.horizontal_pixel_steps * width_steps 
                
                new_height = new_height if new_height <= self.sensor_vertical_pixels else self.sensor_vertical_pixels
                new_width = new_width if new_width <= self.sensor_horizontal_pixels else self.sensor_horizontal_pixels
                
                try:
                    node_map.get_node("Height").set_value(new_height)
                    node_map.get_node("Width").set_value(new_width)
                    
                    row_offset_steps = round(((self.sensor_vertical_pixels - new_height) / 2) / self.vertical_pixel_steps)
                    cols_offset_steps = round(((self.sensor_horizontal_pixels - new_width) / 2) / self.horizontal_pixel_steps)
                    
                    row_offset = row_offset_steps * self.vertical_pixel_steps
                    cols_offset = cols_offset_steps * self.horizontal_pixel_steps
                    
                    if self.has_crop_offset:
                        node_map.get_node("OffsetY").set_value(row_offset)
                        node_map.get_node("OffsetX").set_value(cols_offset)
                    
                    return True
                except:
                    node_map.get_node("Height").set_value(height)
                    node_map.get_node("Width").set_value(width)
                    
                    if self.has_crop_offset:
                        node_map.get_node("OffsetY").set_value(old_row_offset)
                        node_map.get_node("OffsetX").set_value(old_cols_offset)
                    
                    return False
        except:
            self.logger.error("Camera exception! May be disconnected or does not support resizing?")
            self.failed = True
            return False
    
    def set_gain_max(self, stream_object:harvesters.core.ImageAcquirer, gain_val):
        try:
            stream_object.remote_device.node_map.get_node("GainAutoMaxValue").set_value(gain_val)
            return True
        except:
            return False
    
    def set_exposure_max(self, stream_object:harvesters.core.ImageAcquirer, exposure_val):
        try:
            stream_object.remote_device.node_map.get_node("ExposureAutoMaxValue").set_value(exposure_val)
            return True
        except:
            return False


class Camera():
    """Complete camera object representing a single physical camera.
    
    Encapsulates:
    - Camera identification (vendor, serial number)
    - Camera settings (exposure, gain, frame rate, etc.)
    - Harvesters stream object for image acquisition
    - State tracking (enabled, failed, etc.)
    - OpenCV window management for preview
    
    Attributes:
        custom_cam_name: User-friendly name for this camera
        stream_object: Harvesters ImageAcquirer for image streaming
        cam_settings: CameraSettings object with GenICam parameters
        cam_identifier: CameraIdentificationTags for device lookup
        enabled: Whether this camera should be actively streaming
        failed: Whether initialization failed
    """
    
    def __init__(self, yaml_cam_item, harvester_object:Harvester):
        """Initialize a camera from YAML configuration.
        
        Loads identification tags, settings, and creates stream object.
        
        Args:
            yaml_cam_item: YAML dictionary with camera configuration
            harvester_object: Initialized Harvester with drivers loaded
        """
        self.custom_cam_name:str = yaml_cam_item["custom_cam_name"]
        self.enabled:bool = yaml_cam_item["enable"]
        self.enabled_window:bool = yaml_cam_item["enable_window"]
        self.max_gain_trackbar_value:int = yaml_cam_item["max_gain_trackbar_value"]
        
        self.auto_enhancement:bool = yaml_cam_item["auto_enhancement"]
        
        self.camera_logger = rclpy.logging.get_logger("Camera: " + self.custom_cam_name)
        
        self.cam_settings = CameraSettings(yaml_cam_item["settings"], self.camera_logger)
        self.cam_identifier = CameraIdentificationTags(yaml_cam_item["identification_tags"], self.camera_logger)
        
        self.harvester_object = harvester_object
        self.stream_object = self.cam_identifier.get_stream_object(self.harvester_object)
        
        self.failed = False
        
        if self.stream_object == None or not self.enabled:
            self.failed = True
        else:
            self.cam_settings.set_settings(self.stream_object)
            
            if self.enabled_window:
                cv2.namedWindow(self.custom_cam_name, cv2.WINDOW_GUI_EXPANDED)
                
                self.trackbar_name = "Gain Max Auto"
                if self.max_gain_trackbar_value >= 1:
                    cv2.createTrackbar(self.trackbar_name, self.custom_cam_name, 0, self.max_gain_trackbar_value, lambda x: None)
                else:
                    self.camera_logger.warn("TrackbarSettings: Not able to create gain trackbar! Please check the max_gain_trackbar_value value!")
        
        
           
    
    def set_new_crop_factor(self, factor):
        return self.cam_settings.set_camera_crop(self.stream_object, factor)
    
    def set_new_gain_max(self, gain:int):
        return self.cam_settings.set_gain_max(self.stream_object, gain)  

    def set_new_exposure_max(self, exposure:int):
        return self.cam_settings.set_exposure_max(self.stream_object, exposure)
            
    
    def restart(self):        
        self.stream_object = self.cam_identifier.get_stream_object(self.harvester_object)
        
        if self.stream_object is not None:
            self.cam_settings.set_settings(self.stream_object)
    
    def stop(self):
        if not self.failed:
            try:
                if self.stream_object.is_acquiring():
                    self.stream_object.stop()
            except:
                self.camera_logger.error("Camera exception! May be disconnected?")
                self.failed = True
    
    def close(self):
        if self.failed:
            return 
        
        try:
            self.stop()
            self.stream_object.destroy()
        except:
            self.camera_logger.error("Camera exception! May be disconnected?")
            self.failed = True
    
    def on_shutdown(self):
        if self.stream_object != None:
            try:
                self.stream_object.stop()
                self.stream_object.destroy()
            except:
                self.camera_logger.error("Camera exception! May be disconnected?")
                self.failed = True
    
    def set_as_disconnected(self):
        self.failed = True
         
    def acquire_image(self, max_wait):  
        
        # while not shutdown_event.is_set():
        ac_image = None
        cv_image = None
        timestamp = 0
    
        if not self.failed:  
            try:  
                if not self.stream_object.is_acquiring() or self.cam_settings.acquisition_mode != "Continuous": 
                    self.stream_object.start()
    
                #print("Trigger time: ", time.time() - t1)
                
                timestamp = time.time()
                 
                with self.stream_object.fetch(timeout=max_wait) as buffer:
                    # campture_time = timestamp - t1
                    # print("Capture time: ", campture_time)

                    # buffer = self.stream_object.fetch()
                    # Work with the Buffer object. It consists of everything you need.
                    
                    data_format = buffer.payload.components[0].data_format
                    component = buffer.payload.components[0]
                    
                    cols = buffer.payload.components[0].width
                    rows = buffer.payload.components[0].height
                    depth = component.num_components_per_pixel
                    
                    cv_image = np.copy(component.data.reshape(rows,cols, int(depth)))
                    
                    if not (cv2.cuda.getCudaEnabledDeviceCount() > 0):
                        if data_format in rgb_formats:
                            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
                        elif data_format in rgba_formats:
                            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGRA)
                    else:
                        gpu_image = cv2.cuda.GpuMat()
                        gpu_image.upload(cv_image)
                        
                        if data_format in rgb_formats:
                            gpu_image = cv2.cuda.cvtColor(gpu_image, cv2.COLOR_RGB2BGR)
                        elif data_format in rgba_formats:
                            gpu_image = cv2.cuda.cvtColor(gpu_image, cv2.COLOR_RGBA2BGRA)
            except:
                ## Timed out -> Camera seems to be disconnected
                self.camera_logger.error("Timed out while waiting for new image! Please check if camera is still connected or \
                                         increase the minimal_server_heart_beat")
                
                self.failed = True
                return None
                
            
            # Apply auto enhancement and convert gpu mat to default mat
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:     
                if self.auto_enhancement:
                    gpu_image = self.cuda_optimization(gpu_image)
                    
                cv_image = gpu_image.download()

            ##Render image to window
            if self.enabled_window:
                
                ##Adjust Max-ISO-Value
                if self.max_gain_trackbar_value >= 1:
                    new_gain_value = cv2.getTrackbarPos(self.trackbar_name, self.custom_cam_name)
                    if new_gain_value != self.cam_settings.gain_auto_max_value:
                        self.cam_settings.gain_auto_max_value = new_gain_value
                        self.cam_settings.update_max_gain_auto(self.stream_object)
                        
                cv2.imshow(self.custom_cam_name, cv_image)
            
            return (timestamp, cv_image)
            # converted_image = self.cv2_bridge.cv2_to_compressed_imgmsg(cv_image)
            # self.publisher.publish(converted_image)

        else:
            return None
                
                                        
                    # buffer.queue()
            
    def cuda_optimization(self, gpu_mat:cv2.cuda.GpuMat) -> cv2.cuda.GpuMat:
          
        if gpu_mat.channels() > 1:
            # op_mat = cv2.cuda.GpuMat()
            # if scaled_mat.channels() == 3:
            #     op_mat = cv2.cuda.cvtColor(scaled_mat, cv2.COLOR_BGR2GRAY)
            # else:
            #     op_mat = cv2.cuda.cvtColor(scaled_mat, cv2.COLOR_BGRA2GRAY)
                
            # luminace_noise = cv2.cuda.meanStdDev(op_mat).download()[0][0]
            
            # op_mat = scaled_mat
            
            # if scaled_mat.channels() > 3:
            #     op_mat = cv2.cuda.cvtColor(scaled_mat, cv2.COLOR_BGRA2BGR)
            
            # seq_mat = cv2.cuda.split(op_mat) ## sequence of Mats 
            
            # blue_noise = cv2.cuda.meanStdDev(seq_mat[0]).download()
            # green_noise = cv2.cuda.meanStdDev(seq_mat[1]).download()
            # red_noise = cv2.cuda.meanStdDev(seq_mat[2]).download()
            
            # color_noise = (blue_noise + green_noise + red_noise)[0][0] / 3
            
            denoised_mat = cv2.cuda.fastNlMeansDenoisingColored(gpu_mat, 10, 10, cv2.cuda.GpuMat(), 21, 7)
        else:
            # luminace_noise = cv2.cuda.meanStdDev(scaled_mat)(0)
            denoised_mat = cv2.cuda.fastNlMeansDenoising(gpu_mat, 10, cv2.cuda.GpuMat())
            
        return denoised_mat
