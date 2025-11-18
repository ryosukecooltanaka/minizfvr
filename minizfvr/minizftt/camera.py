"""
Classes to handle communication with Camera.
Not sure if I should implement acquisition control from python -- maybe we should just use GUIs?
"""

import numpy as np
import cv2
import time
import multiprocessing as mp
from multiprocessing import shared_memory
from ..utils import encode_frame_to_array

# Camera APIs (not every machine has the API package installed, hence try)
try:
    import PySpin
except ImportError:
    pass

try:
    """
    Note: AVT has released newer version of SDK and python APIs associated.
    I am using older version because I am too lasy to reinstall SDK
    """
    from pymba import Vimba
except ImportError:
    pass

class Camera:
    """
    Camera object archetype
    Camera acquisition will be delegated to a child process using the multiprocessing module.
    To do this, the instantiated Camera object will be Picked and sent to a different processor.
    Certain objects (e.g., stuff that has non-python backend) cannot be pickled.
    So the safest thing is to provide necessary metadata for data acquisition in the constructor, and
    do the initialization in the child process (after pickle-copy).
    """
    def __init__(self, **kwargs):
        """
        We are setting redundant **kwargs as an argument, so we can just dump the parameter dict() to create
        camera objects, without them complaining about unexpected input arguments
        """
        self.camera = None
        self.exit_acquisition_event = mp.Event() # this is a flag used to exit while loop, shared across processes


    def initialize(self, **kwargs):
        """
        Called in the child process at the beginning of continuous acquisition!
        """
        pass

    def fetch_image(self):
        """
        Fetch image.
        Return fetch success (bool), frame (np.ndarray), and timestamp (float?)
        Use perf_counter to get the highest accuracy timestamp -- time.time() resolution can be affected by other
        processes running, and can go down to mere 50Hz or so which is completely inadequate
        """
        time.sleep(0.002)
        return True, np.random.randint(0, 255, (256, 256), 'uint8'), time.perf_counter()

    def close(self):
        pass

    def continuously_acquire_frames(self, timestamp_queue):
        """
        Fetch frames as fast as possible, and put acquired frames into the numpy array based off of shared memory
        """
        self.initialize()
        # connect to shared memory
        raw_frame_memory = shared_memory.SharedMemory(name='raw_frame_memory')
        frame_array = np.ndarray((1000000,), dtype=np.uint8, buffer=raw_frame_memory.buf)

        while not self.exit_acquisition_event.is_set():
            fetch_success, frame, timestamp = self.fetch_image()
            if fetch_success:
                encode_frame_to_array(frame, frame_array)
                timestamp_queue.put(timestamp)

        print('[Camera] Exited continuous acquisition')
        raw_frame_memory.close()
        self.close()


class PointGreyCamera(Camera):
    """
    Point Grey Camera. Uses Spinnaker (PySpin)
    """
    def __init__(self, **kwargs):
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
        return True, converted_image, time.perf_counter()

    def close(self):
        """
        Called from main window close event.
        """
        self.camera.EndAcquisition()
        self.camera.DeInit()
        del self.camera  # this is required for system release
        self.system.ReleaseInstance()

class AVTCamera(Camera):
    """
    AVT Camera. Uses Vimba SDK and its python wrapper.
    There is a newer SDK (Vimba X). If you are going to actually
    use AVT camera for real experiments, consider reimplementing
    this with the new SDK.
    """

    def __init__(self, **kwargs):
        super().__init__()
        self.vimba = None
        self.frame = None

    def initialize(self, **kwargs):
        # Copied over from stytra -- read it carefully at some point!
        self.vimba = Vimba()
        self.vimba.startup()
        self.camera = self.vimba.camera(0)
        self.camera.open()
        self.frame = self.camera.new_frame()
        self.frame.announce()
        self.camera.start_capture()
        self.frame.queue_for_capture()
        self.camera.run_feature_command("AcquisitionStart")

    def fetch_image(self):
        self.frame.wait_for_capture(1000)
        self.frame.queue_for_capture()
        raw_data = self.frame.buffer_data()
        frame = np.ndarray(
            buffer=raw_data,
            dtype=np.uint8,
            shape=(self.frame.data.height, self.frame.data.width),
        )
        return True, frame, time.perf_counter()

    def close(self):
        """
        Called from main window close event.
        """
        self.frame.wait_for_capture(1000)
        self.camera.run_feature_command("AcquisitionStop")
        self.camera.end_capture()
        self.camera.revoke_all_frames()
        self.vimba.shutdown()

class DummyCamera(Camera):
    """
    Load video of an embedded fish, and return frames
    """
    def __init__(self, dummy_video_path, **kwargs):
        super().__init__()
        self.video = None
        self.frame_counter = 0
        self.video_path = dummy_video_path

    def initialize(self):
        """
        Called in the child process
        VideoCapture is a non-Picklable object so this is important
        """
        self.frame_counter = 0
        self.video = cv2.VideoCapture(self.video_path)

    def fetch_image(self):

        if self.frame_counter == self.video.get(cv2.CAP_PROP_FRAME_COUNT):
            self.video.set(cv2.CAP_PROP_POS_FRAMES,0)
            self.frame_counter = 0

        read_success, frame = self.video.read()
        if read_success:
            self.frame_counter += 1
            return True, frame[:, :, 0], time.perf_counter()
        else:
            return False, None, time.perf_counter()

    def close(self):
        self.video.release()

def SelectCameraByName(camera_name, **kwargs):
    """
    Main GUI program calls this function to get the camera object.
    The camera_name should be somehow specified in a config file etc.
    """
    if camera_name=='pointgrey':
        camera = PointGreyCamera()
    elif camera_name=='avt':
        camera = AVTCamera()
    elif camera_name=='dummy':
        camera = DummyCamera(**kwargs)
    else:
        camera = Camera()
    return camera