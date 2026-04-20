## 🎯 Quick Start for Developers

### 1. Project Overview (5 Minutes)

The GenICam Driver project is a **distributed image acquisition system** for industrial cameras:

```
┌─────────────────────────┐
│   MASTER (Server)       │  ← Captures images from cameras
├─────────────────────────┤
│  - Harvesters (GenICam) │
│  - ROS 2 Node           │
│  - TCP/UDP Server       │
└─────────────────────────┘
           ↓ TCP Streaming
┌─────────────────────────┐
│   CLIENT (multiple)     │  ← Receives images over network
├─────────────────────────┤
│  - __RequestServer__    │
│  - API: GenicamCommunication
└─────────────────────────┘
```

**Core idea:** A master continuously captures images from multiple cameras and streams them over TCP to clients, which discover each other via UDP broadcast.

### 2. Understanding Project Structure

```
project/src/                ← 🔥 WHERE THE MAGIC HAPPENS
├── main.py               ← Entry point (start master)
├── example.py            ← Example client (for learning)
├── genicam_node.py       ← ROS 2 node (camera management)
├── genicam_communication.py ← HIGH-LEVEL API (use this!)
├── genicam_host_server.py   ← Server logic (threading, queues)
├── genicam_client_server.py ← Client logic (socket management)
├── genicam_network_basics.py ← Enums & socket utilities
└── data_structures.py    ← Camera, CameraSettings classes
```

**Module dependencies:**

```
main.py
  └─ HarvesterNode (genicam_node.py)
  └─ __ClientHandler__ (genicam_host_server.py)
        └─ Camera (data_structures.py)
        └─ __Client__, __CameraQueue__

example.py / Client code
  └─ GenicamCommunication (genicam_communication.py)
        └─ __RequestServer__ (genicam_client_server.py)
             └─ BufferManagement (genicam_network_basics.py)
```

### 3. The Configuration

**Camera settings:** [`project/config/config.yaml`](project/config/config.yaml)
- Per camera: manufacturer, serial number, capture mode, exposure, gain, etc.
- **Change when:** You add new cameras or adjust image quality

**Network settings:** [`project/config/network.yaml`](project/config/network.yaml)
- Broadcast port, buffer size, heartbeat interval
- **Change when:** You want to optimize network performance

---

## 🛠️ Development Setup

### Installation for Development

```bash
# 1. Clone the repository
git clone <repo-url>
cd GenICamDriver

# 2. Build Docker images (one time)
bash build_image.sh

# 3. Set up host GPU access
bash init_host.sh
```

### Starting Container for Development

```bash
# Terminal 1: Start containers
docker compose up -d

# Terminal 2: Watch logs for `genicam_ros`
docker compose logs -f genicam_ros

# Terminal 3: Enter `genicam_ros` container
docker compose exec genicam_ros bash
```

### Code Editing

```bash
# Code is bound via volume, edit locally:
# VS Code / Editor → open project/src/*.py and edit
# Changes are immediately visible in the container!

# Reload Python code live:
# (In genicam_ros container:)
cd /workspace && python3 -c "import sys; sys.path.insert(0, '.'); from project.src import genicam_communication"
```

---

## 📍 Where to Attack? - Common Development Tasks

### 1. **Add a New Camera**

**Step 1:** Find the serial number
```bash
# In container:
python3 -c "
from harvesters.core import Harvester
h = Harvester()
h.add_file('/opt/**/*.cti')  # Load all drivers
h.update()
for info in h.device_info_list:
    print(f'{info.property.SerialNumberValue}')
"
```

**Step 2:** Extend `project/config/config.yaml`
```yaml
harvester_node:
  ros__parameters:
    camera3:  # New camera
      custom_cam_name: "my_new_camera"
      enable: true
      identification_tags:
        vendor: "Baumer"  # or "FLIR"
        serial_number: "123456789"  # ← Enter serial number
      settings:
        # ... Copy from camera1/camera2 and adjust
```

**Step 3:** Test
```python
# Modify project/src/example.py:
client.subscribe_to_images(["my_new_camera"])
```

---

### 2. **Add a New API Function to the Client**

**Example:** Adjust exposure from client

**File to change:** [`project/src/genicam_communication.py`](project/src/genicam_communication.py)

```python
class GenicamCommunication:
    # ... existing methods ...
    
    def set_camera_exposure(self, cam_name: str, exposure_us: int) -> bool:
        """Change exposure time of a camera
        
        Args:
            cam_name: Camera name (e.g. "baumer_vcxg")
            exposure_us: Exposure time in microseconds
        
        Returns:
            True if successful, False if error
        """
        if not self.connected_to_server():
            return False
        
        # Send request to server using BufferManagement
        request = f"REQUEST set_camera_exposure {cam_name} {exposure_us}"
        BufferManagement.send_buffer(self.request_server.socket, request.encode())
        
        # Read response using BufferManagement
        response = BufferManagement.read_buffer(self.request_server.socket).decode()
        return "OK" in response
```

**File to change:** [`project/src/genicam_host_server.py`](project/src/genicam_host_server.py)

```python
class __ClientHandler__:
    def __run_client__(self, client, sock):
        # ... in request processing loop ...
        
        if "set_camera_exposure" in request:
            parts = request.split()
            cam_name = parts[3]
            exposure = int(parts[4])
            
            if cam_name in self.cameras:
                success = self.cameras[cam_name].set_new_exposure_max(
                    self.cameras[cam_name].stream_object, 
                    exposure
                )
                response = "POST OK" if success else "POST ERROR"
            else:
                response = "POST ERROR Unknown camera"
            
            BufferManagement.send_buffer(sock, response.encode())
```

**Test:**
```python
# project/src/example.py:
client.set_camera_exposure("baumer_vcxg", 10000)  # 10ms
```

---

### 3. **Make Image Processing GPU-Accelerated**

**File:** [`project/src/data_structures.py`](project/src/data_structures.py)

**Extend method `Camera.cuda_optimization()`:**

```python
def cuda_optimization(self, gpu_mat) -> gpu_mat:
    """GPU-accelerated processing"""
    
    # Existing: Denoising
    result = cv2.cuda.fastNlMeansDenoisingColored(gpu_mat, h=10)
    
    # New: Edge detection
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        edges = cv2.cuda.createCannyEdgeDetector(100, 200)
        result = edges.detect(result)
    
    return result
```

**Where is it called?** 
→ `Camera.acquire_image()` in the image capture loop

---

### 4. **Extend Network Communication**

**If you:** Want to add a new request type

**File 1:** [`project/src/genicam_network_basics.py`](project/src/genicam_network_basics.py)
```python
class __RequestTypeEnum__:
    SingleFrame = "REQUEST single_frame"
    MultyFrame = "REQUEST multy_frame"
    # New:
    GetCameraStatus = "REQUEST get_camera_status"  # ← Add this
```

**File 2:** [`project/src/genicam_host_server.py`](project/src/genicam_host_server.py)
```python
def __run_client__(self, client, sock):
    while True:
        request = BufferManagement.read_buffer(sock)
        
        if "get_camera_status" in request:
            # Collect status from all cameras
            status = {}
            for name, cam in self.cameras.items():
                status[name] = {
                    "enabled": cam.enabled,
                    "failed": cam.failed,
                    "frame_rate": 30  # Example
                }
            
            # Send as JSON
            import json
            response = json.dumps(status).encode()
            BufferManagement.send_buffer(sock, response)
```

**File 3:** [`project/src/genicam_client_server.py`](project/src/genicam_client_server.py)
```python
class __RequestServer__:
    def get_camera_status(self) -> dict:
        """Request server status"""
        request = "REQUEST get_camera_status"
        BufferManagement.send_buffer(self.socket, request.encode())
        response = BufferManagement.read_buffer(self.socket)
        
        import json
        return json.loads(response.decode())
```

**File 4:** [`project/src/genicam_communication.py`](project/src/genicam_communication.py)
```python
class GenicamCommunication:
    def get_camera_status(self) -> dict:
        """High-level: Get camera status"""
        if not self.connected_to_server():
            return {}
        return self.request_server.get_camera_status()
```

---

## 🔍 Code Structure in Detail

### The Three Layers of Architecture

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: HIGH-LEVEL API                             │
│ (GenicamCommunication)                              │
│ → User-friendly functions                           │
│ → Exception handling                                │
│ → Connection management                             │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Layer 2: MID-LEVEL PROTOCOL                         │
│ (__RequestServer__, __ClientHandler__)              │
│ → Socket management                                 │
│ → Request/response handling                         │
│ → Client/server threading                           │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Layer 3: LOW-LEVEL UTILITIES                        │
│ (BufferManagement, __NetworkUtils__)                │
│ → Byte-level socket operations                      │
│ → Enums & constants                                 │
│ → Network primitives                                │
└─────────────────────────────────────────────────────┘
```

**Rule:** Always use the highest appropriate layer!
- **Camera streaming?** → `GenicamCommunication.get_latest_images()`
- **Custom protocol?** → `__RequestServer__` / `__ClientHandler__`
- **Raw bytes?** → `BufferManagement`

---

### Threading Model

```
MASTER:
  Main thread
    ├─ HarvesterNode init
    └─ __ClientHandler__ started
        ├─ __master_thread__()        [Image capture]
        │   └─ for each Camera: acquire_image()
        │       └─ Updates CameraQueues
        │
        └─ __run_client__() × N       [TCP handler per client]
            └─ Responds to requests
```

```
CLIENT:
  Main thread
    └─ GenicamCommunication init
        ├─ __RequestServer__ started
        │   └─ __thread_listen__()    [UDP discovery + TCP connect]
        │
        └─ Main loop
            └─ get_latest_images()
                └─ __run_client__() waits for data
```

**⚠️ Threading Gotchas:**

1. **Lock-free queue for images** 
   - Uses `deque` (thread-safe in CPython)
   - But only for simple operations!

2. **TCP socket is not thread-safe**
   - `__RequestServer__` has only **one** socket
   - Serialize requests if multiple threads use client

3. **Master thread priorities**
   - `__master_thread__()` should never be blocked
   - `__run_client__()` may block (per client thread)

---

## 🧪 Testing & Debugging

### Writing Unit Tests

**Where:** `project/test/`

Example:

```python
# test_new_feature.py
import unittest
from project.src.data_structures import Camera, CameraSettings

class TestCameraSettings(unittest.TestCase):
    def setUp(self):
        self.settings = CameraSettings()
    
    def test_exposure_range(self):
        """Exposure should be in valid range"""
        self.settings.exposure_auto_max_value = 50000
        self.assertGreaterEqual(50000, 15)
        self.assertLessEqual(50000, 60000)
    
    def test_crop_factor_range(self):
        """Crop factor should be 0-1"""
        self.assertGreaterEqual(self.settings.user_on_device_crop_factor, 0.0)
        self.assertLessEqual(self.settings.user_on_device_crop_factor, 1.0)

if __name__ == "__main__":
    unittest.main()
```

**Run tests:**
```bash
docker compose exec genicam_ros python3 -m pytest project/test/test_new_feature.py -v
```

### Enable Debug Logging

**In every file:**
```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # ← Enable debug

# ...

logger.debug("Camera thread started")
logger.info("Image acquired from camera1")
logger.warning("Timeout waiting for image")
logger.error("Failed to connect to camera", exc_info=True)
```

**Container logs:**
```bash
docker compose logs -f genicam_ros 2>&1 | grep -i "debug\|error"
```

### Breakpoint Debugging

```python
# In code directly:
def acquire_image(self, max_wait):
    import pdb; pdb.set_trace()  # ← Breakpoint
    
    # Then in container:
    # (i) = info          (l) = list code      (n) = next
    # (s) = step          (c) = continue       (q) = quit
```

---

## 🎨 Code Style & Best Practices

### Python Style Guide (PEP 8)

```python
# ❌ WRONG
def getImg(cam,timeout):
    return cam.acquire_image(timeout)

# ✅ RIGHT
def get_image_from_camera(camera: Camera, timeout: float) -> np.ndarray:
    """Retrieve current image from camera with timeout"""
    return camera.acquire_image(timeout)
```

### Use Type Hints

```python
# ❌ WRONG
def send_image(img, client):
    pass

# ✅ RIGHT
def send_image(img: np.ndarray, client: __Client__) -> bool:
    """Send image to client via TCP"""
    pass
```

### Docstrings for All Public Functions

```python
def subscribe_to_images(self, cam_names: list[str]) -> None:
    """Subscribe to image stream of given cameras
    
    Args:
        cam_names: List of camera names to subscribe to
        
    Returns:
        None
        
    Raises:
        ConnectionError: If not connected to server
        
    Example:
        >>> client.subscribe_to_images(["camera1", "camera2"])
    """
    pass
```

### Error Handling

```python
# ❌ WRONG
try:
    img = camera.acquire_image(timeout)
except:  # ← Too broad!
    pass

# ✅ RIGHT
try:
    img = camera.acquire_image(timeout)
except TimeoutError as ex:
    logger.warning(f"Image acquisition timeout: {ex}")
    self.failed = True
except Exception as ex:
    logger.error(f"Unexpected error: {ex}", exc_info=True)
    raise
```

---

## 📚 Understanding Important Concepts

### GenICam Standard

**What is GenICam?** 
- Standard for camera interfaces (USB, GigE, etc.)
- Defines properties: ExposureTime, Gain, PixelFormat, etc.
- **Harvesters** is an abstraction layer over it

**Where do you encounter GenICam in code?**
```python
# In genicam_node.py:
stream_object = camera_tags.get_stream_object(harvester)
# stream_object is of type: harvesters.core.ImageAcquirer
#   └─ Has stream_object.timeout_ms
#   └─ stream_object.fetch() ← Get managed buffer with image
```

### Harvesters Library

**Core classes:**
```python
from harvesters.core import Harvester, ImageAcquirer

h = Harvester()
h.add_file("path/to/driver.cti")  # Load camera driver
h.update()                         # Scan for connected cameras

info = h.device_info_list[0]
stream = h.create(info)           # ImageAcquirer - virtual camera

with stream.fetch() as buffer:    # Get image
    image_data = buffer.payload.components[0].data
    height = buffer.payload.components[0].height
    width = buffer.payload.components[0].width
```

### ROS 2 Integration

**ROS 2 is only wrapped here:**
```python
# In genicam_node.py:
class HarvesterNode(Node):
    def __init__(self):
        super().__init__('harvester_node')
        self.get_logger().info("Harvester node started")  # ← ROS logging (watch for camera discovery messages)
        self.create_timer(1.0, self.timer_callback)  # ← Optional
```

**You don't need to understand ROS 2 for new features!**
- ROS 2 is only a wrapper for configuration/logging
- Core logic is pure Python

---

## 🚀 Build & Deployment

### Customize Docker Image

**If you:** Add new Python dependencies

**File:** [`requirements.txt`](requirements.txt)
```
harvesters==1.4.1
opencv-python==4.8.0.76
numpy==1.24.3
pyyaml==6.0
# New:
scipy==1.11.0
scikit-image==0.21.0
```

```bash
# Rebuild
docker compose build
```

**If you:** Need system packages (e.g. ffmpeg)

**File:** [`packages.txt`](packages.txt)
```
build-essential
cmake
libusb-1.0-0-dev
# New:
ffmpeg
libavcodec-dev
```

```bash
# Rebuild
docker compose build
```

### Production Deployment

```bash
# 1. Build image and push
docker compose build
docker tag gennicam:latest your-registry/gennicam:latest
docker push your-registry/gennicam:latest

# 2. Pull and start on target machine
docker pull your-registry/gennicam:latest
docker compose up -d
```

---

## 🔗 Common Debugging Scenarios

### Client Cannot Connect

**Checklist:**
```bash
# 1. Check `genicam_ros` service is running
docker ps | grep gennicam

# 2. Check firewall
sudo ufw status

# 3. Check broadcast port
docker exec genicam_ros_container netstat -tlnp | grep 49152

# 4. Client logs
docker exec client_container tail -f /tmp/client.log
```

**Code level:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

client = GenicamCommunication("client")

# You should see:
# DEBUG: Sending broadcast discovery to port 49152
# DEBUG: Connection established to master at X.X.X.X:50000
```

### Master Loses Camera

**In `genicam_node.py`:**
```python
# Retry logic is here:
while True:
    self.harvester_object.update()
    if self.harvester_object.device_info_list:
        break
    self.get_logger().warning("No cameras found, retrying in 15s...")
    time.sleep(15)

# If this loop exits → Camera is truly disconnected
```

**Fix:**
```python
# Extend retry logic:
max_retries = 10
retry_count = 0

while retry_count < max_retries:
    self.harvester_object.update()
    if self.harvester_object.device_info_list:
        break
    retry_count += 1
    time.sleep(30)  # Longer delay

if retry_count >= max_retries:
    self.get_logger().error("Camera not found after retries!")
```

### Images are Blurry/Compressed

**Root cause:**
- JPEG compression is applied by server
- Controlled by `client.desired_img_scaler`

**In `genicam_host_server.py`:**
```python
# Images are compressed with:
def __send_images__(self, tcp_socket, client):
    if client.desired_img_scaler < 1.0:
        # Resize + JPEG compress
        h, w = img.shape[:2]
        new_h = int(h * client.desired_img_scaler)
        new_w = int(w * client.desired_img_scaler)
        img = cv2.resize(img, (new_w, new_h))
        
        # Adjust JPEG quality:
        _, compressed = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
```

**Fix:**
```python
# Increase JPEG quality:
_, compressed = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 98])

# Or avoid scaling entirely:
client.rescale_data_frame(1.0)  # Full resolution
```

---

## 🎓 Learning & Further Education

### Understand Prerequisites

1. **TCP/IP Networking**
   - `BufferManagement.send_buffer()` sends 4-byte length prefix
   - Why? → So receiver knows how many bytes are coming
   
2. **Python Threading**
   - Master uses `threading.Thread` for image capture
   - Client uses `threading.Thread` for UDP discovery
   
3. **OpenCV Basics**
   - `cv2.imdecode()` / `cv2.imencode()` for JPEG
   - `cv2.resize()` for scaling
   - CUDA functions: `cv2.cuda.*`

### Learning Resources

- **[Real Python: Threading](https://realpython.com/intro-to-python-threading/)**
- **[OpenCV: Image Processing](https://docs.opencv.org/)**
- **[Harvesters: GitHub Docs](https://github.com/genicam/harvesters)**
- **[ROS 2: Humble Docs](https://docs.ros.org/en/humble/)**

---

## 📋 Checklist for New Features

When implementing a feature:

- [ ] **Describe the feature:** What do we do and why?
- [ ] **Write code:** With type hints & docstrings
- [ ] **Write tests:** At least one happy-path test
- [ ] **Document:** Update README/docstring
- [ ] **Client & server:** Implement both sides if needed
- [ ] **Testing:** Manually test with real cameras
- [ ] **Backward compatibility:** Break any old features?
- [ ] **Logging:** Add debug logs for troubleshooting
- [ ] **Error handling:** What if network breaks?

---

## 🤝 Git Workflow

```bash
# 1. Create feature branch
git checkout -b feature/new-awesome-feature

# 2. Make changes and test
git add project/src/my_changes.py
git commit -m "feat: add new awesome feature"

# 3. Run tests
docker compose exec genicam_ros python3 -m pytest

# 4. Create PR
git push origin feature/new-awesome-feature
# → Open pull request with description

# 5. Code review & merge
git checkout develop
git merge feature/new-awesome-feature
```

---

## 🆘 Frequently Asked Questions (FAQ)

**Q: I don't understand socket communication**
A: Read [`genicam_network_basics.py`](project/src/genicam_network_basics.py) → `BufferManagement` class. It's only 10 lines of code!

**Q: Where is the image actually captured?**
A: In `Camera.acquire_image()` in [`data_structures.py`](project/src/data_structures.py).

**Q: Why are there both `genicam_communication.py` and `genicam_client_server.py`?**
A: 
- `genicam_client_server.py` = Low-level socket handling
- `genicam_communication.py` = High-level API for users

**Q: How do I debug image quality issues?**
A: 
1. Check `config.yaml`: `ExposureAuto`, `GainAuto` settings
2. Save raw images: `cv2.imwrite("debug.png", img)`
3. Check scaling factor: `client.desired_img_scaler`

**Q: Can I save images locally?**
A: Yes! In `genicam_host_server.py` `__master_thread__()`:
```python
cv2.imwrite(f"frame_{timestamp}.jpg", img)
```

**Q: How many cameras simultaneously?**
A: Unlimited. Each camera = separate thread in `__master_thread__()`.
   Limit = network bandwidth + disk I/O.

---

## 📞 Support & Contact

**Questions about code?** 
→ First check the `.py` file docstrings

**Found a bug?**
→ Open GitHub issue with:
- What happens?
- What should happen?
- How to reproduce?
- Logs & error messages

**Feature request?**
→ Discuss first in GitHub discussions

---

**Good luck with development! 🚀**