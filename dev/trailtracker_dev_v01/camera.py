"""
Classes to handle communication with Camera.
Not sure if I should implement acquisition control from python -- maybe we should just use GUIs?
"""

import numpy as np
import PySpin
import cv2
import time
import multiprocessing as mp

class Camera():
    """
    Camera object archetype
    """
    def __init__(self):
        self.camera = None
        self.exit_acquisition_event = mp.Event() # this is a flag used to exit while loop, shared across processes

    def initialize(self, **kwargs):
        pass

    def fetch_image(self):
        """
        Fetch image.
        Return fetch success (bool), frame (np.ndarray), and timestamp (float?)
        """
        time.sleep(0.002)
        return True, np.random.randint(0, 255, (256, 256), 'uint8'), time.time()

    def close(self):
        pass

    def continuously_acquire_frames(self, queue):
        """
        Fetch frames as fast as possible, and put acquired frames into the queue with timestamps
        """
        while not self.exit_acquisition_event.is_set():
            fetch_success, frame, timestamp = self.fetch_image()
            if fetch_success:
                queue.put((frame, timestamp))


class PointGreyCamera(Camera):
    """
    Point Grey Camera. Uses Spinnaker (PySpin)
    """
    def __init__(self):
        super().__init__()
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
        return True, converted_image, time.time()

    def close(self):
        """
        Called from main window close event.
        """
        self.camera.EndAcquisition()
        self.camera.DeInit()
        del self.camera  # this is required for system release
        self.system.ReleaseInstance()


class DummyCamera(Camera):
    """
    Load video of an embedded fish, and return frames
    """
    def __init__(self):
        super().__init__()
        self.camera = []
        self.video = None
        self.frame_counter = 0
        self.video_path = None

    def initialize(self, video_path='tail_movie.mp4'):
        self.video_path = video_path

    # TODO: This is hacky! fix
    def fetch_image(self, capture_object):
        if self.frame_counter == capture_object.get(cv2.CAP_PROP_FRAME_COUNT):
            capture_object.set(cv2.CAP_PROP_POS_FRAMES,0)
            self.frame_counter = 0

        read_success, frame = capture_object.read()
        if read_success:
            self.frame_counter += 1
            return True, frame[:, :, 0], time.time()
        else:
            return False, None, time.time()

    def continuously_acquire_frames(self, queue):
        """
        Fetch frames as fast as possible, and put acquired frames into the queue with timestamps
        """

        capture_object = cv2.VideoCapture(self.video_path)

        while not self.exit_acquisition_event.is_set():
            fetch_success, frame, timestamp = self.fetch_image(capture_object)
            if fetch_success:
                queue.put((frame, timestamp))

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