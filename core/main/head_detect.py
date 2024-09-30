import traceback
from datetime import datetime

import cv2
import time
import ast
import pandas as pd
import numpy as np
import requests
# from websockets.sync.client import connect
# import io
import sys
import grpc
from sentry_sdk import capture_message

# from core.main.generate_code_for_grpc import api_pb2_grpc, api_pb2
# from core.main.main_utils.box_utils import save_bbox_head
from core.main.main_utils.helper import generate_random_key
from core.main.shm.writer import SharedMemoryFrameWriter
# from core.models_local.head_detection.yolov8_detection.inference_image import person_detect

# sys.path.append("core/models_local/head_detection/yolov5_detect")
# sys.path.append("../../../core/models_local/head_detection/yolov5_detect")
# from core.models_local.head_detection.yolov5_detect.yolov5_detect_image import Y5Detect

# y5_model = Y5Detect(weights="core/models_local/head_detection/yolov5_detect/model_head/y5headbody_v2.pt")
# y5_model = Y5Detect(weights="../../../core/models_local/head_detection/yolov5_detect/model_head/y5headbody_v2.pt")


# class_names = y5_model.class_names

class_names = ['head', 'body']
# print("class_names: ", class_names)

# url_api_yolov5 = "http://localhost:5000/detect_sort_head"


def head_detect_service(cam, frame_detect_queue, detections_queue, info_cam_running):
    # process_id = "604ef817ef7c20fc5e52a20d"
    process_id = generate_random_key()
    shm_w1 = SharedMemoryFrameWriter(process_id)
    port_service_head = info_cam_running["port_service_head"] if info_cam_running.get(
        "port_service_head") is not None else '6000'
    ip_run_service_head = info_cam_running["ip_run_service_head"] if info_cam_running.get(
        "ip_run_service_head") is not None else 'localhost'

    url_api_yolov5 = "http://" + ip_run_service_head + ":" + str(port_service_head) + "/yolov5/predict/share_memory"
    print("url_api_yolov5: ", url_api_yolov5)
    # url_api_yolov5 = "http://api-head.oryza.vn" + "/yolov5/predict/share_memory"
    time_cost = []
    while cam.cap.isOpened():
        frame_rgb, frame_count = frame_detect_queue.get()
        start_time = time.time()
        # data = nparray_to_bytebuffer(frame_rgb)
        # headers = {'Content-Type': 'image/jpeg'}

        # Using shm
        shm_w1.add(frame_rgb)
        payload = {"share_key": process_id}

        # Using flask api
        # headers = {}
        # response = requests.post(url_api_yolov5, headers=headers, data=payload)
        # response = response.json()

        # Using fast API
        try:
            response = requests.post(url_api_yolov5, json=payload)

            response = response.json()
            response = ast.literal_eval(response)

            boxes = np.array(response["boxes"]).astype(int)
            labels = np.array(response["labels"])
            scores = np.array(response["scores"])
            detections_sort = np.array(response["detections_sort"])
        except Exception as e:
            boxes = []
            labels = []
            scores = []
            detections_sort = []
            capture_message(f"[LOITERING][192.168.103.81][{datetime.today().strftime('%d-%m-%Y %H:%M:%S')}][Error] {str(e).upper()} : {traceback.format_exc()}")
            capture_message("Service head error, post to api url_api_yolov5 error")
            print("Service head error, post to api url_api_yolov5 error")
        time_head_cost = time.time() - start_time
        if time_head_cost > 0.05:
            print("body_detect cost: ", time_head_cost)
        # time_cost.append(time.time() - start_time)
        # print("boxes, labels, scores, detections_sort: ", boxes, labels, scores, detections_sort)

        detections_queue.put([boxes, labels, scores, frame_rgb, detections_sort, frame_count])

    cam.cap.release()
    # df = pd.DataFrame(np.array(time_cost), columns=['Values'])
    # # Save DataFrame to text file
    # df.to_csv('/home/oryza/Desktop/Projects/Face_Detection/data_test/time_cost_head_detect_' + port_model_head + '.txt', index=False)


def head_detect(cam, frame_detect_queue, detections_queue):
    while cam.cap.isOpened():
        frame_rgb, frame_count = frame_detect_queue.get()
        start_time = time.time()
        # boxes, labels, scores, detections_sort = y5_model.predict_sort(frame_rgb, label_select=["body"])
        boxes, labels, scores, detections_sort = person_detect(frame_rgb)

        if time.time() - start_time > 0.05:
            print("head_detect cost: ", time.time() - start_time)
        # Save bounding box head with extend size
        # if len(boxes) > 0:
        #     frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2RGB)
        #     save_bbox_head(frame_bgr, boxes, frame_count, "/home/oryza/Pictures/image_head/")
            # KThread(target=save_bbox_head, args=(frame_origin, boxes, frame_count, path_save_bbox)).start()

        # print("boxes, labels, scores, detections_sort: ", boxes, labels, scores, detections_sort)
        boxes = np.array(boxes)
        labels = np.array(labels)
        scores = np.array(scores)
        detections_sort = np.array(detections_sort)
        detections_queue.put([boxes, labels, scores, frame_rgb, detections_sort, frame_count])
        # print("boxes, labels, scores, detections_sort: ", boxes, labels, scores, detections_sort)

    cam.cap.release()


if __name__ == '__main__':
    pass