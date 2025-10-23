from dataclasses import dataclass
import json
import os
from PyQt5.QtCore import QObject, pyqtSignal

"""
Class to store parameters for the tail tracker
Use python dataclass to simplify boiler plates
But basically it's just a bunch of attribtues
"""

class BaseParams:
    """
    Implement methods to read/write parameters from json
    """
    def load_config_from_json(self, config_path = './config.json', verbose=False):
        if os.path.isfile(config_path):
            print('Loading parameters from from ', config_path)
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
                self.read_param_from_dict(config_dict, verbose=verbose)

    def save_config_into_json(self, config_path = './config.json'):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=4)

    def read_param_from_dict(self, param_dict, verbose=False):
        for key in param_dict.keys():
            if hasattr(self, key):  # so we don't inject weird attributes
                setattr(self, key, param_dict[key])
                if verbose:
                    print('loaded', key, '=', param_dict[key])
            else:
                if verbose:
                    print(key, 'is not a valid parameter name!')



@dataclass
class TailTrackerParams(BaseParams):

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




