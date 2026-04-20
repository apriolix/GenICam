"""Legacy UDP discovery client for GenICam server.

This is a simple proof-of-concept client that demonstrates basic UDP
broadcast discovery of the GenICam server. It is not actively used but
remains as a reference implementation.

Note: Use GenicamCommunication class for production code instead.
"""

import socket
import numpy as np
import time 


BUFFER = 1000000
PORT = 2000
KEYWORD = "genicam_ros"


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("192.168.0.1", 80))
ips = s.getsockname()
ip_addresses = socket.gethostbyname_ex(local_hostname)[1]
filtered_ips = [ip for ip in ip_addresses if not ip.startswith("127.")] # eliminate all other IPs like external ip until the local network ip is reached

first_ip = filtered_ips[0]
print(first_ip)
        

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# try:
    #sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER)  # z. B. 64 KB

sock.sendto(KEYWORD.encode(), ("255.255.255.255", PORT))
print("Done")
    # sock.recv()

    # time_s = time.time()
    # sock.connect(("255.255.255.255", PORT))

    # img_size = int.from_bytes(sock.recv(4), 'little')
    # print("Size: ", img_size)

    # data = bytes()
    # while len(data) != img_size:
    #     data += sock.recv(BUFFER)


    # print("Time: ", time.time() - time_s, "Size: ", len(data))
    
    # sock.close()
    # sock.detach()

# except:
#     sock.close()
#     sock.detach()
# finally:
#     sock.close()
#     sock.detach()
    # receive buffer (read)

    # send buffer (write)
