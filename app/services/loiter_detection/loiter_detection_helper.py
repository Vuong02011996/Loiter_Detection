
from app.mongo_dal.camera_dal import CameraDAL


camera_dal = CameraDAL()


def convert_coordinates(coord, width, height):
    for i in range(len(coord)):
        coord[i][0] *= width
        coord[i][1] *= height
        coord[i] = list(map(int, coord[i]))

    return coord
