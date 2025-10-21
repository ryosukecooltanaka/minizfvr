from dataclasses import dataclass
import json
import os

"""
Class to store parameters for the tail tracker
Use python dataclass to simplify boiler plates
But basically it's just a bunch of attribtues
"""

class BaseParams:
    """
    Implement methods to read/write parameters from json
    """
    def load_config_from_json(self, config_path = './config.json'):
        if os.path.isfile(config_path):
            print('Loading parameters from from ', config_path)
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
                self.read_param_from_dict(config_dict, verbose=True)

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






