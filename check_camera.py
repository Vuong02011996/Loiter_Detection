import cv2
import os
import shutil
import time

url = "rtsp://digesttest2:Oryza@123@192.168.111.59:7001/8c02e348-7567-f847-700d-657752a9eb7c"  # lop clover
# url = "rtsp://admin:Oryza@123@192.168.111.6:5546/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"  # lop clover
# url = "rtsp://admin:Oryza@123@192.168.111.6:5546/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"  # lop clover

# open the feed
cap = cv2.VideoCapture(url)
ret, frame = cap.read()
h, w, c = frame.shape
print(h, w, c)

count = 0
start_time = time.time()
while True:
    # read next frame
    ret, frame = cap.read()
    if ret is False:
        break
    print(f"ret: {ret}")
    count += 1
    print(f"frame.shape: {frame.shape}")
    print(f"count: {count}")
    print(f"Time: {time.time() - start_time}")

# close the connection and close all windows
cap.release()
cv2.destroyAllWindows()