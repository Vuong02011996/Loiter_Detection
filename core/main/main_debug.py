import cv2
from queue import Queue
import time
from kthread import KThread
import numpy as np
import connect_db
from video_capture import video_capture
from head_detect import head_detect
from tracking import tracking
from detect_face import detect_face_bbox_head
from recognize_face import get_face_features
from matching_identity import matching_identity
from export_data_v2 import export_data
from drawing import drawing

from flask import Response
from flask import Flask, request
from flask import render_template
import threading

outputFrame = None
lock = threading.Lock()
# initialize a flask object
app = Flask(__name__)

input_path = None


class InfoCam(object):
    def __init__(self, cam_name):
        self.cap = cv2.VideoCapture(cam_name)
        self.frame_start = 0
        self.total_frame_video = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps_video = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.process_name = cam_name.split("/")[-1].split(".")[0]
        self.region_track = np.array([[0, 0],
                                      [2560, 0],
                                      [2560, 1440],
                                      [0, 1440]])
        self.frame_step_after_track = 0
        self.show_all = False


def main():
    start_time = time.time()
    global outputFrame, lock, input_path
    cv2_show = True
    if cv2_show:
        #  "/storages/data/clover_project/Videos-bk/diemdanh/diem_danh_deo_khau_trang2.mp4"
        input_path = "https://minio.core.greenlabs.ai/local/demo_video/diem_danh_deo_khau_trang.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20210926%2F%2Fs3%2Faws4_request&X-Amz-Date=20210926T051355Z&X-Amz-Expires=432000&X-Amz-SignedHeaders=host&X-Amz-Signature=8d664bf575aa9f28bd5ce8859480ce803ac6c0d351559356a3a339a97f8a7d77"
    frame_detect_queue = Queue(maxsize=1)
    detections_queue = Queue(maxsize=1)
    show_all_queue = Queue(maxsize=1)
    frame_final_queue = Queue(maxsize=1)
    face_embedding_queue = Queue(maxsize=1)
    head_bbox_queue = Queue(maxsize=1)
    matching_queue = Queue(maxsize=1)
    show_queue = Queue(maxsize=1)
    database_queue = Queue(maxsize=1)
    cam = InfoCam(input_path)

    thread1 = KThread(target=video_capture, args=(cam, frame_detect_queue))
    thread2 = KThread(target=head_detect, args=(cam, frame_detect_queue, detections_queue))
    thread3 = KThread(target=tracking, args=(cam, detections_queue, show_all_queue, head_bbox_queue))
    thread4 = KThread(target=detect_face_bbox_head, args=(cam, head_bbox_queue, face_embedding_queue))
    thread5 = KThread(target=get_face_features, args=(cam, face_embedding_queue, matching_queue))
    thread6 = KThread(target=matching_identity, args=(cam, matching_queue, database_queue, show_queue))
    thread7 = KThread(target=export_data, args=(cam, database_queue))
    thread8 = KThread(target=drawing, args=(cam, show_queue, show_all_queue, frame_final_queue))

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
    thread4.daemon = True
    thread4.start()
    thread_manager.append(thread4)
    thread5.daemon = True
    thread5.start()
    thread_manager.append(thread5)
    thread6.daemon = True
    thread6.start()
    thread_manager.append(thread6)
    thread7.daemon = True
    thread7.start()
    thread_manager.append(thread7)
    thread8.daemon = True
    thread8.start()
    thread_manager.append(thread8)

    while cam.cap.isOpened():
        image, frame_count = frame_final_queue.get()
        print("frame_count: ", frame_count)
        image = cv2.resize(image, (1400, 640))
        # acquire the lock, set the output frame, and release the
        # lock
        with lock:
            outputFrame = image.copy()
        if cv2_show:
            cv2.imshow('output', image)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cv2.destroyWindow('output')
                break

    total_time = time.time() - start_time
    print("FPS video: ", cam.fps_video)
    print("Total time: {}, Total frame: {}, FPS all process : {}".format(total_time, cam.total_frame_video,
                                                                         1 / (total_time / cam.total_frame_video)), )

    for t in thread_manager:
        if t.is_alive():
            t.terminate()
    cv2.destroyAllWindows()


def generate():
    # grab global references to the output frame and lock variables
    global outputFrame, lock
    # loop over frames from the output stream
    while True:
        # wait until the lock is acquired
        with lock:
            # check if the output frame is available, otherwise skip
            # the iteration of the loop
            if outputFrame is None:
                continue
            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)
            # ensure the frame was successfully encoded
            if not flag:
                continue
        # yield the output frame in the byte format
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
               bytearray(encodedImage) + b'\r\n')


@app.route("/stream")
def stream():
    # return the rendered template
    return render_template("index.html")


@app.route("/start_video", methods=['POST', 'GET'])
def start_video():
    global input_path
    #  https://flask.palletsprojects.com/en/2.0.x/quickstart/#a-minimal-application
    if request.method == 'POST':
        file = request.form["name"]
        input_path = file
        t = KThread(target=main)
        t.daemon = True
        t.start()
    # return the rendered template
    return "<p>OK!</p>"


@app.route("/video_feed")
def video_feed():
    # return the response generated along with the specific media
    # type (mime type)
    return Response(generate(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == '__main__':
    main()
    # # # start the flask app
    # app.run(host="0.0.0.0", port="33333", debug=True,
    #         threaded=True, use_reloader=False)
