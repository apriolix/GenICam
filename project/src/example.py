"""Example client implementation for GenICam communication.

Demonstrates how to:
    - Connect to the master server
    - Subscribe to camera image streams
    - Retrieve live images and image queues
    - Adjust image scaling and cropping
    - Handle reconnection scenarios
    - Display images using OpenCV

Usage:
    python3 example.py
"""

import cv2
import os
import time
from genicam_communication import GenicamCommunication
#from genicam_enums import *




currend_working_dir = os.getcwd() # Read the set working directory path (/GeniCamROS)
config_path = os.path.join(currend_working_dir, "config", "config.yaml") # create final path

cam_name = "flir_1130"

def main():
    """Run the example client to receive and display camera images."""
    genicam_client = GenicamCommunication("client", 0)
    
    while True:
        i = 0
        # init
        genicam_client.subscribe_to_images([cam_name])

        cv2.namedWindow("requested image", cv2.WINDOW_GUI_EXPANDED)
        
        ## New crop factor 
        genicam_client.set_new_crop_factor(0.5)

        while genicam_client.connected_to_server():
            
                t = time.time()
                
                if i < 100:
                    ## request latest captured images
                    image_dict = genicam_client.get_latest_images()
                    queue_dict = None
                else:
                    ## request image queues of all cameras
                    queue_dict = genicam_client.get_camera_queues()
                    image_dict = None
                
                ## request alive cams
                list_of_alive_cams = genicam_client.get_alive_cams()
                
                ## restart genicam to reconnect disconnected cameras
                if not cam_name in list_of_alive_cams:
                    genicam_client.try_to_reconnect_cameras()
                
                if i == 50:
                    genicam_client.update_genicam_config_file(config_path)
                
                ### request image size adjustment (no cropping)
                capture_time = time.time() - t
                desired_capture_time = 0.05
                
                ## calculate scaler for desired capture time
                scaler = desired_capture_time / capture_time
                
                if i == 3 or i == 103:
                    ## post new scaler for transfered data frame
                    genicam_client.rescale_data_frame(scaler)
                
                img = None
                ## read out of latest images dictionary
                if image_dict is not None:
                    img = image_dict[cam_name]["img"]
                    timestamp = image_dict[cam_name]["timestamp"]
                    uncroped_size = (image_dict[cam_name]["original_img_width"], image_dict[cam_name]["original_img_height"])
                            
                
                ## read out of queue of e.g. baumer camera
                if queue_dict is not None:
                    baumer_cam_queue_dict:dict = queue_dict[cam_name]
                    
                    if baumer_cam_queue_dict is not None:
                        ## accsessing data of queue
                        for keys, value_dict in baumer_cam_queue_dict.items():
                            ## e.g. queue element 1
                            img = value_dict["img"]
                            timestamp = value_dict["timestamp"]
                            uncroped_size = (value_dict["original_img_width"], value_dict["original_img_height"])

                
                if img is not None:
                    cv2.imshow("requested image", img)
                        
                cv2.waitKey(1)
                    
                i += 1
                
        genicam_client = GenicamCommunication("client", 0)
            
            
        #time.sleep(0.01)
        
if __name__ == "__main__":
    main()