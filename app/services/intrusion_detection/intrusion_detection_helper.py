
from app.mongo_dal.camera_dal import CameraDAL


camera_dal = CameraDAL()


def get_coordinates_safe_region_from_process_name(process_name, width, height):
    process = process_dal.find_camera_by_process_name(process_name)[0]
    camera_id = process["camera"]
    item_camera = camera_dal.find_by_id(camera_id)
    list_coordinates = []
    # resize coordinates
    if item_camera.get("jobs_cam") is None \
            or item_camera["jobs_cam"].get("safe_area_regions") is None \
            or item_camera["jobs_cam"]["safe_area_regions"].get("coordinates") is None \
            or len(item_camera["jobs_cam"]["safe_area_regions"]["coordinates"]) == 0:
        list_coordinates = None
    else:
        coordinates = item_camera["jobs_cam"]["safe_area_regions"]["coordinates"]
        print("coordinates: ", coordinates)
        # coordinates:  [{'name_regions': 'Vùng 1', 'coord': [[0.68, 0.12], [0.71, 0.5], [0.91, 0.1], [0.95, 0.48]]},
        #                {'name_regions': 'Vùng 1', 'coord': [[0.68, 0.12], [0.71, 0.5], [0.91, 0.1], [0.95, 0.48]]},..]
        for item_coord in coordinates:
            coord = item_coord["coord"]
            for i in range(len(coord)):
                coord[i][0] *= width
                coord[i][1] *= height
                coord[i] = list(map(int, coord[i]))
            list_coordinates.append(coord)

    return list_coordinates


def convert_coordinates(coord, width, height):
    for i in range(len(coord)):
        coord[i][0] *= width
        coord[i][1] *= height
        coord[i] = list(map(int, coord[i]))

    return coord
