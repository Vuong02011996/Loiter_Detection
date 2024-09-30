"""
Version2: Only save track have face và nhận diện ra tên.
+ Dùng để giảm dung lượng file lưu phía BE.
+ Xét len mảng matching_info > 0 và có phần tử khác Unknown thì sẽ lưu , nếu đã lưu rồi thì chỉ update lại khoảng cách
nếu khoảng cách nhỏ hơn khoảng cách trước đó đã lưu.
"""
import traceback
import pika
import json
import time
import cv2
import numpy as np
import os
from datetime import datetime
import requests
from sentry_sdk import capture_message
from collections import deque

from app.app_utils.file_io_untils import upload_img_from_disk
from app.minio_dal.minio_client import upload_array_image_to_minio

from app.mongo_dal.process_dal.process_loitering_dal import ProcessLoiteringDAL
from app.mongo_dal.process_dal.process_intrusion_dal import ProcessIntrusionDAL
from app.mongo_dal.process_dal.process_cross_line_dal import ProcessCrossLineDAL
from app.services.cross_line_detection.line_segments_intersect_utils import doIntersect_cross_line
from core.main.drawing import drawing_line_between_two_point
from core.main.main_utils.box_utils import extend_bbox
from core.main.main_utils.draw import draw_region, draw_boxes_tracking, draw_boxes_one_track_id



process_loitering_dal = ProcessLoiteringDAL()
process_intrusion_dal = ProcessIntrusionDAL()
process_cross_line_dal = ProcessCrossLineDAL()

ip_rabbitMQ_server = os.getenv("ip_rabbitMQ_server")
port_rabbitMQ_server = int(os.getenv("port_rabbitMQ_server"))
LOITERING_DETECTION_EXCHANGES = "LOITERING_DETECTION_EXCHANGES"
CROSS_LINE_EXCHANGES = "TRIPWIRE_EXCHANGES"
INTRUSION_EXCHANGES = "INTRUSION_EXCHANGES"

def get_avatar_url(box, frame_ori, frame_count, track_id, name_process):
    box = list(map(int, box))
    image_face = frame_ori[box[1]:box[3], box[0]:box[2]]
    try:
        image_face = cv2.cvtColor(image_face, cv2.COLOR_BGR2RGB)
    except Exception as e:
        capture_message(f"[LOITERING][192.168.103.81][{datetime.today().strftime('%d-%m-%Y %H:%M:%S')}][Error] {str(e).upper()} : {traceback.format_exc()}")
        print("Lỗi image_face", e)
        return "image face is null", "image face is null"
    image_name = name_process + "_frame" + str(frame_count) + "_track_" + str(
        track_id)
    avatar_url_ori = upload_img_from_disk(image_name, image_face)

    # extend bounding box for FE
    box_extend = extend_bbox(box, frame_ori.shape, ext_w=20, ext_h=20)
    image_face_extend = frame_ori[box_extend[1]:box_extend[3], box_extend[0]:box_extend[2]]
    image_face_extend = cv2.resize(image_face_extend, (500, 500))
    image_face_extend = cv2.cvtColor(image_face_extend, cv2.COLOR_BGR2RGB)
    image_name = name_process + "_frame" + str(frame_count) + "_track_" + str(
        track_id) + "_extend"
    avatar_url_extend = upload_img_from_disk(image_name, image_face_extend)

    return avatar_url_extend, avatar_url_ori


def export_data_loiter_detection(cam, database_queue, object_dal):
    """
    Logic : Yêu cầu khi có một đối tượng xuất hiện trong vùng tracking quá 5s thì gửi noti.
    Các trường hợp xử lí:
    + Track hiện tại có mà trước không có: chưa đk lưu DB thì lưu DB.(Có trường hợp nào track_id
        đã lưu DB rồi hay không?)
    + Kiểm tra những track đã lưu DB
        + Nếu mới vừa lưu xong ở trên chưa có save_status thì update save_status saving , và frame_start_save.
        + Nếu đã lưu 5s và save_status đang là saving thì bắn thông báo ở đây.
    + Track trước đó có mà hiện tại không có :
        + Check nếu có bắn thông báo thì dữ lại update to_frame.
        + Nếu chưa bắn thông báo có thì xóa.

    # Add task: Tính khoảng thời gian người đó ở trong vùng lảng vảng

    :param cam:
    :param database_queue:
    :param object_dal:
    :return:
    """
    list_track_id_notify = []
    pre_track_id = []
    # Save box of all track of previous frame to take image of frack delete
    pre_track_box = []
    temp_data = []
    image_pre = None
    de = deque(maxlen=3)

    process_id = process_loitering_dal.find_process_id_by_process_name(cam.process_name)
    print('waiting_time: ', cam.waiting_time)
    while cam.cap.isOpened():
        track_bbs_ids, frame_rgb, frame_count = database_queue.get()
        boxes_head = track_bbs_ids[:, :-1]
        track_ids = track_bbs_ids[:, -1]
        pre_track_id = np.array(pre_track_id)
        pre_track_box = np.array(pre_track_box)

        # Check track id not create in database so created
        # tìm những track hiện tại có mà mà frame trước không có
        track_id_start = np.setdiff1d(track_ids, pre_track_id)
        if len(track_id_start) > 0:
            data_insert = []
            for track_id in track_id_start:
                # # Can't get avatar_url_extend it here to because cost time
                # So save temp frame_rgb and box_of_track, to get avatar_url_extend after
                # image_show_ = image_show.copy()
                # data_save = {str(int(track_id)): frame_rgb.copy()}
                # temp_data.append(data_save)
                # idx_box = np.where(track_ids == track_id)[0][0]
                # box = boxes_head[idx_box]
                # box_of_track = list(map(int, box))  # [xmin, ymin, xmax, ymax]
                # avatar_url_extend = get_image_url(frame_rgb, cam, box_of_track, track_id, frame_count)

                objects_data_elem = {
                    "process_name": cam.process_name,
                    "track_id": int(track_id),
                    "from_frame": frame_count,
                    # "box_of_track": box_of_track,
                    "notified": False,
                    "to_frame": None,
                    "save_status": "saving",
                    "created_at": datetime.now(),
                }
                data_insert.append(objects_data_elem)
                if cam.is_debug:
                    try:
                        process_id_ = process_id[0]["process_id"]
                        time_current = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
                        cv2.imwrite(
                            f"/home/oryza/.ai/loiterting/Data/images_person/image_{process_id_}_{frame_count}_{int(track_id)}_{time_current}.png",
                            cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2RGB))
                        print("Save image")
                    except Exception as e:
                        print("Error when save image to trained model")
                        capture_message(f"[LOITERING][192.168.103.81][{datetime.today().strftime('%d-%m-%Y %H:%M:%S')}][Error] {str(e).upper()} : {traceback.format_exc()}")

            if len(data_insert) > 0:
                object_dal.save_document(data_insert)

        # Check in database if track_id have duration_frame > threshold send noti
        list_object_loitering = object_dal.find_all_by_process_name(cam.process_name)
        data_update = []
        list_id = []
        for object_loitering in list_object_loitering:
            if object_loitering.get("save_status") is not None and object_loitering["save_status"] == "saving":
                duration_frame = (frame_count - object_loitering["from_frame"])
                fps = cam.fps if cam.fps is not None else None
                if duration_frame > cam.waiting_time * fps:  # fps là frame/s của camera
                    epoch_start = int(time.mktime(datetime.today().timetuple())) - cam.waiting_time
                    """3. Bắn data qua oryza AI"""
                    # try:
                    # upload image face to minio and get url
                    start_time = time.time()
                    track_id = object_loitering["track_id"]
                    # box_of_track = object_loitering["box_of_track"]
                    # frame_rgb_of_track = next((d[str(track_id)] for d in temp_data if str(track_id) in d), None)

                    # track_ids current if different with track_ids when save track_id(2 list different)
                    # idx_box = np.where(track_ids == track_id)[0][0]
                    # box = boxes_head[idx_box]
                    # box_of_track = list(map(int, box))  # [xmin, ymin, xmax, ymax]
                    print("track_id: ", track_id)
                    # avatar_url_extend = get_image_url(frame_rgb_of_track, cam, box_of_track, track_id, frame_count)
                    avatar_url_extend = upload_array_image_to_minio(frame_rgb, bucket="face",
                                                                    folder_name="loitering_data",
                                                                    image_name="test_" + str(frame_count),
                                                                    mode_rgb="RGB")

                    print(avatar_url_extend)

                    print("Upload file to minio cost: ", time.time() - start_time)

                    data_send = {"id": process_id[0]["process_id"],
                                 "data": {
                                     'camera_ip': cam.ip_camera,
                                     'timestamp': epoch_start,
                                     'image_url': avatar_url_extend,
                                     'track_id': track_id
                                 }
                                 }
                    print("data_send: ", data_send)
                    # pikaPublisher = PikaPublisher()
                    if cam.waiting_time == 0:
                        send_data_rabbit_mq(data_send, INTRUSION_EXCHANGES)
                    else:
                        send_data_rabbit_mq(data_send, LOITERING_DETECTION_EXCHANGES)

                    # update to DB
                    objects_data_elem = {
                        "save_status": "stop_save",
                        "notified": True,
                        "epoch_start": epoch_start,
                        "created_at": datetime.now(),
                    }
                    data_update.append(objects_data_elem)
                    list_id.append(object_loitering["_id"])

                    # except Exception as e:
                    #     print("Lỗi gửi data qua rabbitMQ ", e)
                    #     capture_message(
                    #         f"[LOITERING][192.168.103.81][{datetime.today().strftime('%d-%m-%Y %H:%M:%S')}][Error] {str(e).upper()} : {traceback.format_exc()}")

        #  Update object info to mongDB
        object_dal.update_document(list_id, data_update)

        # TH3: Kiểm tra track frame trước có mà hiện tại không có
        track_id_delete = np.setdiff1d(pre_track_id, track_ids)
        if len(track_id_delete) > 0:
            # Update mongoDB with to_frame, have_face(True), identity
            list_id = []
            list_id_del = []
            data_update = []
            for track_id in track_id_delete:
                track_id = int(track_id)
                object_data = object_dal.find_object_id_by_track_id(track_id, cam.process_name)
                if object_data[0]["notified"] is True:
                    # Update to frame
                    objects_data_elem = {
                        "to_frame": frame_count,
                        "save_status": "stop_save",
                        "created_at": datetime.now(),
                    }
                    list_id.append(object_data[0]["_id"])
                    data_update.append(objects_data_elem)

                    # Send data track id delete for backend
                    # take box of track id delete from previous frame
                    idx_box = np.where(pre_track_id == track_id)[0][0]
                    box = pre_track_box[idx_box]
                    box_of_track = list(map(int, box))  # [xmin, ymin, xmax, ymax]
                    # avatar_url_extend = get_image_url(image_pre, cam, box_of_track, track_id, frame_count)
                    avatar_url_extend = get_image_url(de[0], cam, box_of_track, track_id, frame_count)

                    process_id = process_loitering_dal.find_process_id_by_process_name(cam.process_name)
                    epoch_stop = int(time.mktime(datetime.today().timetuple()))
                    data_send = {"id": process_id[0]["process_id"],
                                 "data": {
                                     'camera_ip': cam.ip_camera,
                                     'timestamp': epoch_stop,
                                     'image_url': avatar_url_extend,
                                     'track_id': track_id,
                                     'duration_time': int(epoch_stop - object_data[0]["epoch_start"] + cam.waiting_time)
                                 }
                                 }
                    print("data_send: ", data_send)
                    # pikaPublisher = PikaPublisher()
                    if cam.waiting_time == 0:
                        send_data_rabbit_mq(data_send, INTRUSION_EXCHANGES)
                    else:
                        send_data_rabbit_mq(data_send, LOITERING_DETECTION_EXCHANGES)
                else:
                    list_id_del.append(object_data[0]["_id"])

            #  Update object info to mongDB
            if len(data_update) > 0:
                object_dal.update_document(list_id, data_update)
            if len(list_id_del) > 0:
                print("Object was deleted , notified is False")
                object_dal.delete_document(list_id_del)

        pre_track_id = track_ids
        pre_track_box = track_bbs_ids[:, :-1]
        # image_pre = frame_rgb.copy()
        de.append(frame_rgb)
        # filename = "/home/oryza/Pictures/images/" + "test_" + str(frame_count) + ".png"
        # cv2.imwrite(filename, frame_rgb)
    cam.cap.release()


def export_data_intrusion_detection(cam, database_queue, object_dal):
    """
    Logic : Yêu cầu khi có một đối tượng xuất hiện trong vùng tracking quá 5s thì gửi noti.
    Các trường hợp xử lí:
    + Track hiện tại có mà trước không có: chưa đk lưu DB thì lưu DB.(Có trường hợp nào track_id
        đã lưu DB rồi hay không?)
    + Kiểm tra những track đã lưu DB
        + Nếu mới vừa lưu xong ở trên chưa có save_status thì update save_status saving , và frame_start_save.
        + Nếu đã lưu 5s và save_status đang là saving thì bắn thông báo ở đây.
    + Track trước đó có mà hiện tại không có :
        + Check nếu có bắn thông báo thì dữ lại update to_frame.
        + Nếu chưa bắn thông báo có thì xóa.

    # Add task: Tính khoảng thời gian người đó ở trong vùng lảng vảng

    :param cam:
    :param database_queue:
    :param object_dal:
    :return:
    """
    pre_track_id = []
    # Save box of all track of previous frame to take image of frack delete
    pre_track_box = []
    process_id = process_intrusion_dal.find_process_id_by_process_name(cam.process_name)
    print('waiting_time: ', cam.waiting_time)
    while cam.cap.isOpened():
        track_bbs_ids, frame_rgb, frame_count = database_queue.get()
        # image_show = frame_rgb.copy()
        boxes_head = track_bbs_ids[:, :-1]
        track_ids = track_bbs_ids[:, -1]
        pre_track_id = np.array(pre_track_id)
        pre_track_box = np.array(pre_track_box)

        # Check track id not create in database so created
        # tìm những track hiện tại có mà mà frame trước không có
        track_id_start = np.setdiff1d(track_ids, pre_track_id)
        if len(track_id_start) > 0:
            data_insert = []
            for track_id in track_id_start:
                # # Can't get avatar_url_extend it here to because cost time
                # So save temp frame_rgb and box_of_track, to get avatar_url_extend after
                # image_show_ = image_show.copy()
                # data_save = {str(int(track_id)): frame_rgb.copy()}
                # temp_data.append(data_save)
                idx_box = np.where(track_ids == track_id)[0][0]
                box = boxes_head[idx_box]
                box_of_track = list(map(int, box))  # [xmin, ymin, xmax, ymax]
                avatar_url_extend = get_image_url(frame_rgb, cam, box_of_track, track_id, frame_count)

                epoch_start = int(time.mktime(datetime.today().timetuple()))
                data_send = {"id": process_id[0]["process_id"],
                             "data": {
                                 'camera_ip': cam.ip_camera,
                                 'timestamp': epoch_start,
                                 'image_url': avatar_url_extend,
                                 'track_id': track_id
                                }
                             }
                print("data_send: ", data_send)
                send_data_rabbit_mq(data_send, INTRUSION_EXCHANGES)

                objects_data_elem = {
                    "process_name": cam.process_name,
                    "track_id": int(track_id),
                    "from_frame": frame_count,
                    # "box_of_track": box_of_track,
                    "notified": False,
                    "to_frame": None,
                    "save_status": "saving",
                    "created_at": datetime.now(),
                }
                data_insert.append(objects_data_elem)
            if len(data_insert) > 0:
                object_dal.save_document(data_insert)
        pre_track_id = track_ids
        pre_track_box = track_bbs_ids[:, :-1]

    cam.cap.release()



def send_data_rabbit_mq(data_send, channel_sent_data):
    start_time = time.time()
    try:
        credentials = pika.PlainCredentials('guest', 'guest')
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=ip_rabbitMQ_server, port=port_rabbitMQ_server,
                                      credentials=credentials))

        channel = connection.channel()
        channel.exchange_declare(exchange=channel_sent_data,
                                 exchange_type='fanout')
        message = json.dumps(data_send)
        # pikaPublisher.send_message(data=data_send, exchange_name='FACE_RECOGNITION_EXCHANGES')
        channel.basic_publish(exchange=channel_sent_data, routing_key='',
                              body=message)
        print("Sent data to rabbitMQ cost: ", time.time() - start_time)
        connection.close()

    except Exception as e:
        print("Connect to ip_rabbitMQ_server error: IP, Port:", ip_rabbitMQ_server,
              port_rabbitMQ_server)
        capture_message(
            f"[LOITERING][192.168.103.81][{datetime.today().strftime('%d-%m-%Y %H:%M:%S')}][Error] {str(e).upper()} : {traceback.format_exc()}")


def get_image_url(image_show_, cam, box_of_track, track_id, frame_count, cross_line=False):
    """

    Args:
        cross_line:
        image_show_:
        cam:
        box_of_track: [xmin, ymin, xmax, ymax]
        track_id:
        frame_count:

    Returns:

    """

    image_show_ = draw_region(image_show_, cam.region_track)
    # image_show = draw_boxes_tracking(image_show, track_bbs_ids)
    # image_show_ = draw_boxes_one_track_id(image_show_, track_bbs_ids, track_id)
    print("track_id inside: ", track_id)
    image_show_ = draw_boxes_one_track_id(image_show_, box_of_track, track_id)
    if cross_line:
        image_show_ = drawing_line_between_two_point(image_show_, cam.point1, cam.point2)

    # cv2.imshow('output_roll_call', cv2.resize(image_show, (800, 500)))
    # cv2.waitKey(0)

    avatar_url_extend = upload_array_image_to_minio(image_show_, bucket="face",
                                                    folder_name="cross_line_data",
                                                    image_name="test_" + str(frame_count),
                                                    mode_rgb="RGB")
    return avatar_url_extend


def export_data_cross_line_detection(cam, database_queue, object_dal):
    """
    Logic : Yêu cầu khi có một đối tượng di qua line

    :param cam:
    :param database_queue:
    :param object_dal:
    :return:
    """
    list_track_id_notify = []
    pre_track_id = []
    # Save box of all track of previous frame to take image of frack delete
    pre_track_box = []
    temp_data = []
    process_id = process_cross_line_dal.find_process_id_by_process_name(cam.process_name)
    while cam.cap.isOpened():
        track_bbs_ids, frame_rgb, frame_count = database_queue.get()
        # image_show = frame_rgb.copy()
        boxes_head = track_bbs_ids[:, :-1]
        track_ids = track_bbs_ids[:, -1]
        pre_track_id = np.array(pre_track_id)
        pre_track_box = np.array(pre_track_box)

        track_id_the_same = np.intersect1d(track_ids, pre_track_id)
        if len(track_id_the_same) > 0:
            # print("track_id_the_same: ", track_id_the_same)
            for track_the_same in track_id_the_same:
                idx_box_before = np.where(pre_track_id == track_the_same)[0][0]
                box_before = get_center_box(pre_track_box[idx_box_before])
                idx_box_after = np.where(track_ids == track_the_same)[0][0]
                box_after = get_center_box(boxes_head[idx_box_after])

                # box_before = [670, 747] # [1250, 402]
                # box_after = [1081, 494] # []
                result = doIntersect_cross_line(cam.point1, cam.point2, box_before, box_after)
                # print("result: ", result)
                # cross line
                if result:
                    print("result: ", result)
                    box = boxes_head[idx_box_after]
                    box_of_track = list(map(int, box))  # [xmin, ymin, xmax, ymax]
                    avatar_url_extend = get_image_url(frame_rgb, cam, box_of_track, track_the_same, frame_count, cross_line=True)
                    timestamp = int(time.mktime(datetime.today().timetuple()))
                    data_send = {"id": process_id[0]["process_id"],
                                 "data": {
                                     'camera_ip': cam.ip_camera,
                                     'timestamp': timestamp,
                                     'image_url': avatar_url_extend,
                                     'track_id': int(track_the_same),
                                 }
                                 }
                    print("data_send: ", data_send)
                    send_data_rabbit_mq(data_send, CROSS_LINE_EXCHANGES)

        pre_track_id = track_ids
        pre_track_box = boxes_head
    cam.cap.release()


def get_center_box(bounding_box):
    # Extract coordinates
    x_min, y_min, x_max, y_max = bounding_box

    # Calculate the center point coordinates
    x_center = int((x_min + x_max) / 2)
    y_center = int((y_min + y_max) / 2)

    return [x_center, y_center]