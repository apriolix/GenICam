# GenICam Driver - User Guide

A complete guide for operating the GenICam Driver system for multi-camera industrial image acquisition and network streaming.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the System](#running-the-system)
5. [Setting Up a Server](#setting-up-a-server)
6. [Using the Client API](#using-the-client-api)
7. [Performance Tuning](#performance-tuning)
8. [Troubleshooting](#troubleshooting)
9. [Examples](#examples)

---

## ⚡ Quick Start

**5 minutes to first image:**

```bash
# 1. Start the system
docker compose up -d

# 2. Wait for `genicam_ros` to be ready (~30 seconds)
# Watch the container logs for camera discovery / startup messages
docker compose logs -f genicam_ros | grep -i "found following cti-files\|camera\|client\|error\|warning"

# 3. Run example client
docker compose exec genicam_ros python3 project/src/example.py

# 4. Check output - you should see images from connected cameras!
```

---

## 📦 Installation

### Prerequisites

- **Linux OS** (Ubuntu 20.04 LTS or newer recommended)
- **Docker** (19.03 or newer)
- **Docker Compose** (1.29 or newer)
- **NVIDIA GPU** (optional, for hardware acceleration)
- **Network Interface** (Ethernet recommended for stability)

### Step 1: Prepare Your System

```bash
# Update package manager
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Allow current user to use Docker (optional but recommended)
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Enable GPU Support (Optional)

If you have an NVIDIA GPU and want hardware-accelerated image processing:

```bash
# Run the initialization script
bash ./init_host.sh

# Verify GPU is accessible
docker run --rm --runtime=nvidia nvidia/cuda:12.0.0-runtime nvidia-smi
```

### Step 3: Build Docker Images

```bash
# This builds all necessary Docker images
bash ./build_image.sh

# Takes ~15-30 minutes depending on system
```

### Step 4: Verify Installation

```bash
# Check if images were built
docker images | grep gennicam

# You should see output similar to:
# REPOSITORY   TAG      IMAGE ID     CREATED      SIZE
# gennicam     latest   xyz123...    5 min ago    2.5GB
```

---

## 🎛️ Configuration

### Camera Configuration (`project/config/config.yaml`)

This file defines all connected cameras and their capture settings.

#### Finding Your Camera's Serial Number

```bash
# Option 1: Using the web camera tool (if connected via USB)
lsusb -v

# Option 2: Using Harvesters (from within container)
docker compose exec genicam_ros python3 << 'EOF'
from harvesters.core import Harvester
import glob

h = Harvester()
for cti_path in glob.glob("/opt/**/*.cti", recursive=True):
    h.add_file(cti_path)

h.update()
for dev_info in h.device_info_list:
    print(f"Camera: {dev_info.property.DisplayName}")
    print(f"  Vendor: {dev_info.property.SerialNumberValue}")
    print(f"  Serial: {dev_info.property.SerialNumberValue}")
    print()
EOF
```

#### Example Configuration - Two Cameras

```bash
# Monitor container performance
docker compose stats

# Watch server logs
docker compose logs -f genicam_ros --tail=50

# Check port usage
netstat -tlnp | grep -E "(49152|50000)"
ss -tlnp | grep -E "(49152|50000)"
```

### Camera Configuration (`project/config/config.yaml`)

```yaml
      settings:
        acquisition:
          AcquisitionMode: "Continuous"
          AcquisitionFrameRate: 120  # Fast continuous capture
        ExposureAuto: "Continuous"
        ExposureAutoMaxValue: 10000    # Fast shutter (10ms)
        GainAuto: "Continuous"
        GainAutoMaxValue: 24
        PixelFormat: "RGB8"
        BalanceWhiteAuto: "Continuous"
        on_device_crop_factor: 1.0
    
    # Low-FPS FLIR camera for detailed inspection
    camera2:
      custom_cam_name: "flir_inspection"
      enable: true
      enable_window: false
      identification_tags:
        vendor: "Teledyne FLIR"
        serial_number: "M0002817"
      settings:
        acquisition:
          AcquisitionMode: "Continuous"
          AcquisitionFrameRate: 15    # Slower, higher quality
        ExposureAuto: "Off"            # Manual exposure for consistency
        GainAuto: "Off"
        PixelFormat: "RGB8"
        on_device_crop_factor: 0.75    # 75% zoom (device-side)
```

### Network Configuration (`project/config/network.yaml`)

Controls network-level parameters.

```yaml
broadcast_key: "genicam"           # Search key for server discovery
broadcast_port: 49152              # UDP broadcast port (don't change unless necessary)
client_port_range: [49152, 65535]  # TCP port range for clients
server_heartbeat: 2.5              # Heartbeat interval in seconds
server_queue_size: 5               # Number of images buffered per camera
```

#### Configuration Explained

| Parameter | Impact | Adjust If |
|-----------|--------|-----------|
| `server_queue_size: 5` | Memory usage, latency | Increase for buffering, decrease if memory-constrained |
| `server_heartbeat: 2.5` | Network overhead | Decrease for faster reconnection, increase to reduce network traffic |
| `broadcast_port` | Network routing | Only if port is already in use |

---

## 🚀 Running the System
### Start a Server (Master / genicam_ros)

To start a GenICam server (master), simply run the `main.py` entry point and provide a numeric server id:

```bash
# From repository root
python3 project/src/main.py --server-id 0
```

That's all that is required to create and run a server. The process will initialize cameras from `project/config/config.yaml` and start the required networking services automatically.

Stop the server with Ctrl-C.

---

If you run the project inside the provided container, you do NOT need to change `docker-compose.yaml` to start the server. Use one of the following approaches to start `main.py` inside the container:

1) Start the container (keep compose unchanged) and run `main.py` inside it:

```bash
# Start container as normal (detached)
docker compose up -d

# Then execute the server inside the running container
docker compose exec genicam_ros python3 /GeniCamROS/src/main.py --server-id 0
```

2) Run the service with an overridden command (one-off):

```bash
# Run the genicam_ros service and execute main.py directly (removes container after exit)
docker compose run --rm genicam_ros python3 /GeniCamROS/src/main.py --server-id 0
```

3) Run the image directly (no compose change):

```bash
# Bind the project folder and run main.py (uses host networking for camera discovery)
docker run --rm -it --network host -v "$PWD/project:/GeniCamROS" genicam_ros \
    python3 /GeniCamROS/src/main.py --server-id 0
```

Choose the approach that fits your workflow; all three start `main.py` in the container without editing `docker-compose.yaml`.

**Software Requirements:**
- Linux OS (Ubuntu 20.04 LTS, 22.04 LTS recommended)
- Docker & Docker Compose
- NVIDIA Container Toolkit (if using GPU)
- Sufficient disk space for camera data retention

### Single Server Setup

#### Quick Setup

```bash
# 1. Navigate to project directory
cd GenICamDriver

# 3. Configure cameras
nano project/config/config.yaml
# Edit and add your cameras with serial numbers

# 4. Start containers (do not modify docker-compose.yaml)
docker compose up -d

# 5. Start the GenICam master (genicam_ros) inside the running container
# (runs main.py with the chosen server id)
docker compose exec genicam_ros python3 /GeniCamROS/src/main.py --server-id 0

# 6. Verify server is running
docker compose ps
```

#### Startup Verification Checklist

```bash
# ✓ Docker container is running
docker compose ps | grep genicam_ros
# Expected: "genicam_ros ... Up X minutes"

# ✓ Cameras are detected
docker compose logs genicam_ros | grep -i "camera"
# Expected: a log line containing camera discovery (e.g. "Camera <id>:") or a printed camera list

# ✓ Server is accepting connections
# Check TCP/UDP ports and container logs for client/server activity
docker compose logs genicam_ros | grep -i "client added\|camera\|error\|warning"
# Also verify ports with netstat/ss
```

### Multi-Server Setup (Distributed System)

For large installations with multiple server machines. Each camera group has its own master server on separate hardware:

```
┌──────────────────┐       ┌──────────────────┐
│  Server Machine 1│       │  Server Machine 2│
│  (Master 0)      │       │  (Master 1)      │
│  - Camera 1      │       │  - Camera 3      │
│  - Camera 2      │       │  - Camera 4      │
│  :49152          │       │  :49152          │
└──────────────────┘       └──────────────────┘
         ↑                        ↑ UDP Discovery
         │                        │
    ┌────┴────────────────────────┴─────┐
    │         Shared Network             │
    └────┬──────────────────────────┬────┘
         │                          │
    ┌────▼──────┐             ┌────▼──────┐
    │  Client 1 │             │  Client 2 │
    └───────────┘             └───────────┘
```

**Setup:**

```bash
# On Machine 1:
docker compose up -d
docker compose exec genicam_ros python3 /GeniCamROS/src/main.py --server-id 0


# On Machine 2:
docker compose up -d
docker compose exec genicam_ros python3 /GeniCamROS/src/main.py --server-id 1
```

**Client Connection:**

```python
# Connect to Server 0 (Machine 1)
client1 = GenicamCommunication("client", server_id=0)

# Connect to Server 1 (Machine 2)
client2 = GenicamCommunication("client", server_id=1)

# Or automatically discover all servers
for server_id in range(5):
    try:
        client = GenicamCommunication("client", server_id=server_id)
        if client.connected_to_server():
            print(f"Found server {server_id}")
    except:
        pass
```

#### Architecture Option 2: Single Master

Primary master with hot standby for failover:

```
┌─────────────────────┐
│       Master        │ Active - Captures images
└─────────────────────┘
         ↓
    Image Transfer
         ↓
┌─────────────────────┐
│       Client        │ 
└─────────────────────┘

```

### Server Performance Tuning

#### CPU/Memory Optimization

```bash
# Check resource usage
docker compose stats

# if CPU-bound:
# 1. Reduce camera FPS in config.yaml
# 2. Increase polling interval in clients
# 3. Enable GPU acceleration if available

# if Memory-bound:
# 1. Reduce server_queue_size in network.yaml (default: 5)
# 2. Use smaller resolution (rescale_data_frame)
# 3. Limit number of clients
```

**Edit project/config/network.yaml:**

```yaml
# For high-load scenarios
server_queue_size: 2        # Reduce from 5 to 2
server_heartbeat: 1.0       # Increase check frequency
broadcast_port: 49152       # Use standard port
client_port_range: [49152, 65535]
```

**Edit project/config/config.yaml:**

```yaml
harvester_node:
  ros__parameters:
    camera1:
      settings:
        acquisition:
          AcquisitionFrameRate: 30    # Lower FPS = lower CPU
        # Disable auto features to reduce processing
        ExposureAuto: "Off"
        GainAuto: "Off"
        BalanceWhiteAuto: "Off"
```

#### Network Optimization

```bash
# Check network performance
iperf3 -s  # On server
iperf3 -c server_ip  # On client, test bandwidth

# Optimize network buffers (Linux)
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 67108864"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 67108864"
```

## �💻 Using the Client API

The GenICam Driver provides a simple Python API for retrieving images from cameras.

### Basic Example

```python
import time
from genicam_communication import GenicamCommunication

# 1. Create a client
client = GenicamCommunication("client", server_id=0)

# 2. Wait for server to be discovered
while not client.connected_to_server():
    print("Searching for server...")
    time.sleep(1)

print("Connected to server!")

# 3. Subscribe to cameras
client.subscribe_to_images(["baumer_monitoring", "flir_inspection"])

# 4. Get images in a loop
try:
    for i in range(100):
        images = client.get_latest_images()
        
        for cam_name, data in images.items():
            print(f"{cam_name}: {data['timestamp']:.3f}s")
            # data contains:
            # - img: numpy array (OpenCV BGR format)
            # - timestamp: float (seconds)
            # - original_img_width: int
            # - original_img_height: int
        
        time.sleep(0.05)  # 20 Hz polling

except KeyboardInterrupt:
    print("Stopped by user")
```

### API Reference

#### Creating a Client

```python
from genicam_communication import GenicamCommunication

client = GenicamCommunication(
    node_type="client",      # "client" or "master"
    server_id=0              # Server ID if multiple masters
)
```

#### Checking Connection Status

```python
if client.connected_to_server():
    print("Connected!")
else:
    print("Still searching for server...")
```

#### Subscribing to Cameras

```python
# Subscribe to specific cameras
client.subscribe_to_images(["camera1", "camera2"])

# Get list of available cameras
available = client.get_alive_cams()
print(f"Available cameras: {available}")
```

#### Getting Latest Images (Fast)

```python
# Get the most recent frame from each subscribed camera
images = client.get_latest_images()

# Output structure:
images = {
    "camera1": {
        "img": np.ndarray(...),      # BGR format, uint8
        "timestamp": 1234.567,        # seconds since epoch
        "original_img_width": 1920,
        "original_img_height": 1080
    },
    "camera2": {
        "img": np.ndarray(...),
        "timestamp": 1234.568,
        "original_img_width": 1280,
        "original_img_height": 960
    }
}

# Process images
for cam_name, data in images.items():
    img = data["img"]
    ts = data["timestamp"]
    
    # Do something with the image
    cv2.imwrite(f"latest_{cam_name}.jpg", img)
```

#### Getting Buffered Images (Complete History)

```python
# Get all buffered frames from each camera
frames = client.get_camera_queues()

# Output structure:
frames = {
    "camera1": {
        "frame_0": {"img": ..., "timestamp": ...},
        "frame_1": {"img": ..., "timestamp": ...},
        # ... up to server_queue_size frames
    }
}

# Process all frames
for cam_name, frame_dict in frames.items():
    for frame_id, data in frame_dict.items():
        print(f"{cam_name} {frame_id}: {data['timestamp']}")
```

#### Adjusting Image Compression

```python
# For network bandwidth optimization
# Values: 0.1 (10% size) to 1.0 (100% size, no compression)

# Low bandwidth: 25% resolution, small JPEG
client.rescale_data_frame(0.25)

# Medium: 50% resolution
client.rescale_data_frame(0.5)

# High quality: full resolution
client.rescale_data_frame(1.0)
```

#### Camera Recovery

```python
# If a camera disconnects, try to restart it
client.try_to_reconnect_cameras()

# Check which cameras are still alive
alive = client.get_alive_cams()
failed = set(subscribed) - set(alive)
print(f"Failed cameras: {failed}")
```

---

## 🎬 Complete Examples

### Example 1: Simple Image Grabber

```python
#!/usr/bin/env python3
"""Simple image grabber - saves images to disk"""

import os
import time
import cv2
from genicam_communication import GenicamCommunication

def main():
    # Create output directory
    os.makedirs("output_images", exist_ok=True)
    
    # Connect to server
    client = GenicamCommunication("client")
    
    while not client.connected_to_server():
        time.sleep(0.5)
    
    print("Connected! Subscribing to cameras...")
    client.subscribe_to_images(["baumer_monitoring", "flir_inspection"])
    
    # Capture 100 images
    for frame_num in range(100):
        images = client.get_latest_images()
        
        for cam_name, data in images.items():
            img = data["img"]
            ts = data["timestamp"]
            
            # Save with timestamp
            filename = f"output_images/{cam_name}_{ts:.3f}.jpg"
            cv2.imwrite(filename, img)
            print(f"Saved: {filename}")
        
        time.sleep(0.1)
    
    print("Done!")

if __name__ == "__main__":
    main()
```

### Example 2: Real-Time Display with OpenCV

```python
#!/usr/bin/env python3
"""Display camera streams in real-time windows"""

import time
import cv2
from genicam_communication import GenicamCommunication

def main():
    client = GenicamCommunication("client")
    
    # Wait for connection
    while not client.connected_to_server():
        print("Searching for server...")
        time.sleep(1)
    
    # Subscribe
    cameras = ["baumer_monitoring"]
    client.subscribe_to_images(cameras)
    
    while True:
        images = client.get_latest_images()
        
        for cam_name, data in images.items():
            img = data["img"]
            ts = data["timestamp"]
            
            # Add timestamp overlay
            cv2.putText(img, f"TS: {ts:.3f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display
            cv2.imshow(cam_name, img)
        
        # Exit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        time.sleep(0.033)  # ~30 Hz
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
```

### Example 3: Image Processing Pipeline

```python
#!/usr/bin/env python3
"""Process images: detect edges and count features"""

import cv2
import numpy as np
import time
from genicam_communication import GenicamCommunication

def process_image(img):
    """Apply edge detection and feature counting"""
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Count edges (contours)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # Draw contours
    result = img.copy()
    cv2.drawContours(result, contours, -1, (0, 255, 0), 2)
    
    return result, len(contours)

def main():
    client = GenicamCommunication("client")
    
    while not client.connected_to_server():
        time.sleep(0.5)
    
    client.subscribe_to_images(["baumer_monitoring"])
    
    print("Processing images...")
    feature_counts = []
    
    for i in range(50):
        images = client.get_latest_images()
        
        for cam_name, data in images.items():
            img = data["img"]
            processed, feature_count = process_image(img)
            feature_counts.append(feature_count)
            
            print(f"Frame {i}: {feature_count} features detected")
        
        time.sleep(0.05)
    
    # Statistics
    avg_features = np.mean(feature_counts)
    print(f"Average features per frame: {avg_features:.1f}")

if __name__ == "__main__":
    main()
```

### Example 4: Network Bandwidth Monitoring

```python
#!/usr/bin/env python3
"""Monitor network bandwidth usage"""

import time
import cv2
from genicam_communication import GenicamCommunication

def estimate_bandwidth(img_bytes, duration_seconds):
    """Estimate bandwidth in Mbps"""
    bits = img_bytes * 8
    mbps = (bits / duration_seconds) / (1000 * 1000)
    return mbps

def main():
    client = GenicamCommunication("client")
    
    while not client.connected_to_server():
        time.sleep(0.5)
    
    client.subscribe_to_images(["baumer_monitoring"])
    
    # Test different compression ratios
    ratios = [1.0, 0.5, 0.25, 0.1]
    
    for ratio in ratios:
        print(f"\nTesting compression ratio: {ratio}")
        client.rescale_data_frame(ratio)
        
        total_bytes = 0
        start_time = time.time()
        
        for _ in range(30):
            images = client.get_latest_images()
            
            for cam_name, data in images.items():
                img = data["img"]
                # Estimate JPEG size
                success, jpeg = cv2.imencode('.jpg', img)
                total_bytes += len(jpeg)
            
            time.sleep(0.033)
        
        elapsed = time.time() - start_time
        mbps = estimate_bandwidth(total_bytes, elapsed)
        
        print(f"  Bandwidth: {mbps:.2f} Mbps")
        print(f"  Total bytes: {total_bytes / 1000:.1f} KB")

if __name__ == "__main__":
    main()
```

---

## 📊 Performance Tuning

### Network Optimization

| Setting | Fast Network | Slow Network |
|---------|--------------|--------------|
| `rescale_data_frame()` | 1.0 (full resolution) | 0.25-0.5 |
| `server_queue_size` | 10 | 2 |
| `AcquisitionFrameRate` | 120+ | 15-30 |
| Polling interval | 10ms | 50-100ms |

### CPU/GPU Optimization

**Enable GPU acceleration:**
```bash
# In docker-compose.yaml, ensure:
runtime: nvidia

# Then in code (automatic):
# cv2.cuda.* functions are used automatically
```

**Reduce processing load:**
```python
# Increase polling interval to reduce CPU
time.sleep(0.1)  # Instead of busy-waiting

# Use smaller resolution
client.rescale_data_frame(0.5)  # 50% size

# Reduce camera FPS in config.yaml
AcquisitionFrameRate: 30  # Instead of 120
```

### Memory Optimization

```python
# For long-running processes, limit queue size
# In project/config/network.yaml:
server_queue_size: 2  # Reduces memory footprint

# Or use latest images instead of queues
images = client.get_latest_images()  # Single frame
# Instead of:
queues = client.get_camera_queues()  # All buffered frames
```

---

## 🐛 Troubleshooting

### Issue: "Server not found"

**Symptoms:**
```
Searching for server...
Searching for server...
Searching for server...
```

**Solutions:**

1. **Verify `genicam_ros` service is running:**
```bash
docker compose ps
# STATUS should show "Up"
```

2. **Check firewall:**
   ```bash
   sudo ufw status
   # Should allow port 49152 (UDP)
   sudo ufw allow 49152/udp
   ```

3. **Verify network connectivity:**
   ```bash
   ping $(docker inspect -f '{{.NetworkSettings.IPAddress}}' container_id)
   ```

4. **Check `genicam_ros` logs:**
```bash
docker compose logs genicam_ros | tail -20
# Look for server/client activity messages (e.g. "Client added" or camera discovery)
```

### Issue: Images are blurry/noisy

**Solutions:**

1. **Adjust camera settings in `config.yaml`:**
   ```yaml
   ExposureAuto: "Continuous"
   GainAuto: "Continuous"
   ExposureAutoMaxValue: 15000  # Increase for more light
   ```

2. **Check physical conditions:**
   - Lighting
   - Camera focus
   - Lens cleanliness

3. **Increase image quality:**
   ```python
   # Use full resolution
   client.rescale_data_frame(1.0)
   ```

### Issue: "Timeout waiting for image"

**Symptoms:**
```
TimeoutError: [Errno 110] Connection timed out
```

**Solutions:**

1. **Increase timeout in client code:**
   ```python
   images = client.get_latest_images()
   time.sleep(0.5)  # Give it more time
   ```

2. **Reduce master load:**
   - Decrease `AcquisitionFrameRate`
   - Reduce `server_queue_size`

3. **Check network performance:**
   ```bash
   # Monitor network statistics
   iftop
   # or
   nethogs
   ```

### Issue: Camera disconnects randomly

**Solutions:**

1. **Check USB cable quality** (if using USB cameras)
   - Replace with high-quality shielded cable
   - Use powered USB hub

2. **Increase retry timeout in `genicam_node.py`:**
   ```python
   time.sleep(30)  # Wait 30 seconds between retries
   ```

3. **Monitor camera health:**
   ```python
   alive = client.get_alive_cams()
   if len(alive) < expected_cameras:
       client.try_to_reconnect_cameras()
   ```

### Issue: High latency/slow response

**Solutions:**

1. **Reduce image resolution:**
   ```python
   client.rescale_data_frame(0.5)  # 50% resolution
   ```

2. **Reduce camera FPS:**
   ```yaml
   AcquisitionFrameRate: 30  # Lower FPS = lower data rate
   ```

3. **Use Ethernet instead of WiFi:**
   - WiFi introduces jitter and latency
   - Wired Ethernet is more stable

4. **Reduce polling overhead:**
   ```python
   # Instead of tight loop:
   for _ in range(1000):
       images = client.get_latest_images()
   
   # Use threading:
   def image_thread():
       while True:
           images = client.get_latest_images()
           process_images(images)
           time.sleep(0.05)
   
   thread = threading.Thread(target=image_thread, daemon=True)
   thread.start()
   ```

---

## 🔍 Logging & Debugging

### Enable Debug Logging

```python
import logging

# Enable debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Then use client as normal
client = GenicamCommunication("client")
```

### Check genicam_ros Logs

```bash
# All logs
docker compose logs genicam_ros

# Last 50 lines
docker compose logs --tail=50 genicam_ros

# Follow in real-time
docker compose logs -f genicam_ros

# Filter for errors
docker compose logs genicam_ros 2>&1 | grep ERROR
```

### Monitor Container Resources

```bash
# CPU and memory usage
docker stats

# Detailed stats for container
docker compose stats
```

---

## 📚 Advanced Features

### Multiple Servers

If you need redundancy or geographic isolation:

```python
# Connect to different server
client1 = GenicamCommunication("client", server_id=0)
client2 = GenicamCommunication("client", server_id=1)

# Both can run simultaneously
while client1.connected_to_server() or client2.connected_to_server():
    images1 = client1.get_latest_images() if client1.connected_to_server() else {}
    images2 = client2.get_latest_images() if client2.connected_to_server() else {}
```

### Custom Image Processing Pipeline

```python
import cv2
from genicam_communication import GenicamCommunication

class ImageProcessingPipeline:
    def __init__(self, camera_names):
        self.client = GenicamCommunication("client")
        self.client.subscribe_to_images(camera_names)
    
    def preprocess(self, img):
        """Denoise and normalize"""
        denoised = cv2.fastNlMeansDenoisingColored(img, h=10)
        normalized = cv2.normalize(denoised, None, 0, 255, cv2.NORM_MINMAX)
        return normalized
    
    def detect_features(self, img):
        """Find keypoints"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        sift = cv2.SIFT_create()
        keypoints, descriptors = sift.detectAndCompute(gray, None)
        return keypoints, descriptors
    
    def process_frame(self):
        images = self.client.get_latest_images()
        for cam_name, data in images.items():
            preprocessed = self.preprocess(data["img"])
            keypoints, descriptors = self.detect_features(preprocessed)
            print(f"{cam_name}: {len(keypoints)} features found")

# Usage
pipeline = ImageProcessingPipeline(["camera1"])
```

---

## ⚡ Best Practices

1. **Always check connection status:**
   ```python
   if not client.connected_to_server():
       client = GenicamCommunication("client")
   ```

2. **Handle exceptions gracefully:**
   ```python
   try:
       images = client.get_latest_images()
   except Exception as e:
       print(f"Error: {e}")
       # Attempt reconnection
   ```

3. **Use appropriate polling rates:**
   - 10-20 Hz for monitoring
   - 30-60 Hz for interactive apps
   - Higher only if needed

4. **Monitor memory usage:**
   ```python
   import psutil
   process = psutil.Process()
   print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
   ```

5. **Log important events:**
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info(f"Received frame at {data['timestamp']}")
   ```

---

## 📞 Getting Help

**If you encounter issues:**

1. Check the [Troubleshooting](#troubleshooting) section
2. Review container logs: `docker compose logs genicam_ros`
3. Verify configuration in `project/config/`
4. Check network connectivity: `ping gateway`, `netstat`
5. Try the simple examples in [Examples](#examples)

**For development questions:**
- See `ReadmeDev.md` for architecture details
- Check inline code documentation in `project/src/`

---

## 📄 License

Apache License 2.0 - See LICENSE file for details

---

**Version:** 1.0  
**Last Updated:** February 2026  
**Status:** Production Ready ✅