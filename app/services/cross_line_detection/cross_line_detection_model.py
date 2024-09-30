import cv2
import os
from queue import Queue
import time
from kthread import KThread
from datetime import datetime
import ast
from app.services.loiter_detection.loiter_detection_helper import convert_coordinates
from core.main.video_capture import video_capture
from core.main.head_detect import head_detect_service
from core.main.tracking import tracking_safe_region
from core.main.export_data_v3 import export_data_cross_line_detection
from core.main.drawing import drawing_cross_line
from app.mongo_dal.object_dal.object_cross_line_dal import ObjectCrossLine
from app.mongo_dal.process_dal.process_cross_line_dal import ProcessCrossLineDAL
import numpy as np
object_dal = ObjectCrossLine()
process_dal = ProcessCrossLineDAL()

CV2_SHOW = os.getenv("CV2_SHOW")


class InfoCam(object):
    def __init__(self, cam_name, process_name, info_cam_running, test_video):
        self.cap = cv2.VideoCapture(cam_name)
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.resize = False
        if self.resize:
            self.width = int(640)
            self.height = int(640)
        else:
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frame_video = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_start = 0

        self.process_name = process_name

        # coordinates = get_coordinates_safe_region_from_process_name(process_name, self.width, self.height)
        #
        # # Không giống như điểm danh ở đây có nhiều vùng nên coordinates là một mảng 3 chiều.
        # # coordinates: [[[1305, 129], [1363, 540], [1747, 108], [1824, 518]]]
        # if coordinates is not None:
        #     # coordinates trả về theo tọa độ :
        #     # top, left 0 -> bottom, left 1  -> bottom, right 2 -> top, right 3
        #     # region track lại mong muốn thứ tự top, left 0-> top, right 3-> bottom, right 2-> bottom, left 1
        #     # Đúng ra phải là self.region_track = [coordinates[0], coordinates[3], coordinates[2], coordinates[1]]
        #     # Nhưng mà ...
        #     list_coordinates = []
        #     for region in coordinates:
        #         list_coordinates.append([region[0], region[2], region[3], region[1]])
        #     self.region_track = list_coordinates
        #     # self.region_track = coordinates
        # else:
        # coordinates = np.array([[0, 0], [self.width-300, 0], [self.width-300, self.height], [0, self.height]])
        # coordinates = np.array([[0, 0], [self.width-400, 0], [self.width-400, self.height], [0, self.height]])
        # coordinates = np.array([[self.width-200, 0], [self.width, 0], [self.width, self.height], [self.width-200, self.height]])

        # self.region_track = list([coordinates[0], coordinates[1], coordinates[2], coordinates[3]])

        ## test region
        # test_region_from_fe(self.cap, self.region_track)

        # self.branch_cam = item_cam['branch_cam']
        # self.branch_id = item_cam['branch_id']
        # self.class_cam = item_cam['class_cam']
        # self.class_id = item_cam['class_id']
        # if 'jobs_cam' in item_cam and 'safe_area_regions' in item_cam['jobs_cam'] and 'duration_time' in \
        #         item_cam['jobs_cam']['safe_area_regions']:
        #     # Key exists, safe to access it
        #     self.duration_time = item_cam['jobs_cam']['safe_area_regions']['duration_time']
        # else:
        #     self.duration_time = 3

        coordinates = np.array([[0, 0], [self.width, 0], [self.width, self.height], [0, self.height]])
        self.region_track = list([coordinates[0], coordinates[1], coordinates[2], coordinates[3]])
        self.ip_camera = info_cam_running["ip_camera"]
        # self.is_debug = info_cam_running["is_debug"]
        self.is_debug = False
        self.url_cam = cam_name

        self.frame_step_after_track = 0
        self.show_all = True
        self.test_video = test_video
        # self.test_video = True
        points = ast.literal_eval(info_cam_running["coordinates_lines"])
        points = convert_coordinates(points, self.width, self.height)
        self.point1 = points[0]  # [766, 455]
        self.point2 = points[1]  # [953, 788]


def run_cross_line(item_cam, end_time_s, info_cam_running, test_video=False, cv2_show=True, window="test"):
    print("vào run_safe_region...")
    start_time = time.time()
    frame_detect_queue = Queue(maxsize=1)
    detections_queue = Queue(maxsize=1)
    show_all_queue = Queue(maxsize=1)
    frame_final_queue = Queue(maxsize=1)
    database_queue = Queue(maxsize=1)
    # time.sleep(30)

    input_path = item_cam["url_cam"]
    print("cam_name: ", input_path)
    process_name = info_cam_running["process_name"]
    cam = InfoCam(input_path, process_name, info_cam_running, test_video)
    frame_count = cam.total_frame_video
    # -------------------------------------------------------------------------

    thread1 = KThread(target=video_capture, args=(cam, frame_detect_queue, input_path))
    # thread2 = KThread(target=head_detect, args=(cam, frame_detect_queue, detections_queue))
    thread2 = KThread(target=head_detect_service, args=(cam, frame_detect_queue, detections_queue, info_cam_running))
    # thread3 = KThread(target=tracking, args=(cam, detections_queue, show_all_queue, head_bbox_queue))
    thread3 = KThread(target=tracking_safe_region, args=(cam, detections_queue, show_all_queue, database_queue))
    thread7 = KThread(target=export_data_cross_line_detection, args=(cam, database_queue, object_dal))
    # thread8 = KThread(target=drawing, args=(cam, show_queue, show_all_queue, frame_final_queue))
    thread8 = KThread(target=drawing_cross_line, args=(cam, show_all_queue, frame_final_queue))

    thread_manager = []
    thread1.daemon = True  # sẽ chặn chương trình chính thoát khi thread còn sống.
    thread1.start()
    thread_manager.append(thread1)
    thread2.daemon = True
    thread2.start()
    thread_manager.append(thread2)
    thread3.daemon = True
    thread3.start()
    thread_manager.append(thread3)

    thread7.daemon = True
    thread7.start()
    thread_manager.append(thread7)
    thread8.daemon = True
    thread8.start()
    thread_manager.append(thread8)

    while cam.cap.isOpened():
        image, frame_count = frame_final_queue.get()
        if test_video is False and frame_count % 1000 == 0:
            print("frame_count_" + item_cam["id_camera"] + ":    ", frame_count)
        # if test_video is False:
        #     print("frame_count: ", frame_count)

        # STREAMING
        # if process_stream is not None:
        #     process_stream.stdin.write(image.tobytes())

        if CV2_SHOW == "true":
            image_show = cv2.resize(image, (500, 300))
            # image_show = image
            cv2.imshow(window, image_show)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cv2.destroyWindow(window)
                break
        # Get time current
        time_utc_now = datetime.utcnow()
        time_now_seconds = time_utc_now.timestamp()
        if time_now_seconds >= end_time_s:
            print("time_current: ", time_now_seconds)
            print("end_time_roll_call_s: ", end_time_s)
            break

    total_time = time.time() - start_time
    print("FPS video: ", cam.fps)
    if cam.fps == 0:
        print("Camera didn't connected")
    else:
        print("Total time: {}, Total frame: {}, FPS all process : {}".format(total_time, frame_count,
                                                                             1 / (total_time / frame_count)), )

    for t in thread_manager:
        if t.is_alive():
            t.terminate()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    pass
    # input_path = "rtsp://admin:Admin123@14.241.120.239:554"
    # input_path = "/home/vuong/Videos/test_phu.mp4"
    # process_stream = None
    # process_name = "642e8ea65fcc5d739067a0e0_safe_area_regions_7_2023:04:11-10:35:15"
    # item_cam = find_info_cam_from_process_name(process_dal, process_name)
    # thread_safe_region_manager = []
    # time_now = datetime.now()
    # time_now_seconds = time_now.timestamp()
    # end_time_s = time_now_seconds + 5000
    # run_loiter(item_cam, process_name, end_time_s, test_video=True, cv2_show=True)
