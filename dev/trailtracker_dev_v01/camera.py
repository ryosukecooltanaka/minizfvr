"""
Classes to handle communication with Camera.
Not sure if I should implement acquisition control from python -- maybe we should just use GUIs?
"""

import numpy as np
import PySpin
import cv2
from time import time

class Camera():
    """
    Camera object archetype
    """
    def __init__(self):
        self.camera = None

    def initialize(self, **kwargs):
        pass

    def fetch_image(self):
        return np.random.randint(0, 255, (256, 256), 'uint8'), time()

    def close(self):
        pass



class PointGreyCamera(Camera):
    """
    Point Grey Camera. Uses Spinnaker (PySpin)
    """
    def __init__(self):
        self.system = PySpin.System.GetInstance()
        self.camera = self.system.GetCameras()[0]

    def initialize(self, **kwargs):
        self.camera.Init()
        self.camera.BeginAcquisition()

    def fetch_image(self):
        fetched_image = self.camera.GetNextImage()
        converted_image = None
        if not fetched_image.IsIncomplete():
            converted_image = np.array(fetched_image.GetData(), dtype='uint8').reshape(
                (fetched_image.GetHeight(), fetched_image.GetWidth()))
        fetched_image.Release()
        return converted_image, time()

    def close(self):
        """
        Called from main window close event.
        """
        self.camera.EndAcquisition()
        self.camera.DeInit()
        del self.camera  # this is required for system release
        self.system.ReleaseInstance()


class DummyCamera():
    """
    Load video of an embedded fish, and return frames
    """
    def __init__(self):
        self.camera = []
        self.video = None
        self.frame_counter = 0

    def initialize(self, video_path='tail_movie.mp4'):
        self.video = cv2.VideoCapture(video_path)

    def fetch_image(self):
        if self.frame_counter == self.video.get(cv2.CAP_PROP_FRAME_COUNT):
            self.video.set(cv2.CAP_PROP_POS_FRAMES,0)
            self.frame_counter = 0

        read_success, frame = self.video.read()
        if read_success:
            self.frame_counter += 1
            return frame[:, :, 0], time()
        else:
            return None, time()

    def close(self):
        self.video.release()




def SelectCameraByName(camera_name=None, **kwargs):
    """
    Main GUI program calls this function to get the camera object.
    The camera_name should be somehow specified in a config file etc.
    """
    if camera_name=='pointgrey':
        camera = PointGreyCamera()
    elif camera_name=='dummy':
        camera = DummyCamera()
    else:
        camera = Camera()
    camera.initialize(**kwargs)
    return camera