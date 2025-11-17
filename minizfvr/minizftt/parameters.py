from dataclasses import dataclass
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from ..parameters import BaseParams

"""
Class to store parameters for the tail minizftt
Use python dataclass to simplify boiler plates
But basically it's just a bunch of attribtues
"""

@dataclass
class TailTrackerParams(BaseParams):

    # default config path (home directory)
    config_path: str = str(Path.home() / 'minizftt_config.json')

    # camera settings
    camera_type: str = None
    dummy_video_path: str = './tail_movie.mp4'

    # image preprocessing parameters
    show_raw: bool = True
    image_scale: float = 1.0
    filter_size: int = 3
    color_invert: bool = True
    clip_threshold: int = 0

    # tracking algo parameters
    base_x: float = 10.0  # in the post-rescaling coordinate
    base_y: float = 10.0
    tip_x: float = 100.0
    tip_y: float = 100.0
    n_segments: int = 7
    search_area: int = 15

    # visualization related parameters
    angle_trace_length: int = 1000

class TrackerParamObject(QObject, TailTrackerParams):
    """
    We combine the parameter class with QObject, so it can emit an event.
    This helps us keep the GUI and parameter behind it in sync without messing things up.

    Whenever we edit things from the GUI panel, callback functions will update the parameter.
    Then we will make the StimParamObject emit the paramChanged signal.
    This signal is then connected to a method that updates the GUI panel.

    This is better than calling the GUI update method directly from the GUI callback in terms of modularity
    (that is, direct calls can become too tangled as the app gets bigger)
    """
    # When the parameter object is changed in the GUI callback function, we emit this paramChagned signal.
    # This signal will be connected to the GUI refresh function of the control panel, to which the parameter object
    # itself will be handed as an argument. In addition, we also might need to update the scale of the tail standard
    # if the scale of the frame presented changed (i.e., by changing rescaling factor or toggling between showing
    # raw and processed frames). This rescaling factor pertains to the history of the parameter and as such cannot
    # be computed solely based on the current parameter. As such, we need to compute this rescale factor in the
    # paramChanged callback, and hand it to the camera_panel gui refresh method through the signal argument (hence
    # the fload argument of this signal).
    paramChanged = pyqtSignal(float)




