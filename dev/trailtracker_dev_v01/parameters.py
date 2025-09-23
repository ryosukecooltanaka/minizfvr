from dataclasses import dataclass
import json
import os

"""
Class to store parameters for the tail tracker
Use python dataclass to simplify boiler plates
But basically it's just a bunch of attribtues
"""


@dataclass
class TailTrackerParams:

    # camera settings
    camera_type: str = None
    dummy_video_path: str = './tail_movie.mp4'

    # image preprocessing parameters
    show_raw: bool = True
    image_scale: float = 1.0
    filter_size: int = 3
    color_invert: bool = True
    clip_threshold: int = 0

    def load_config_from_json(self, config_path = './config.json'):
        if os.path.isfile(config_path):
            print('Loading parameters from from ', config_path)
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
                for key in config_dict.keys():
                    if hasattr(self, key): # so we don't inject weird attributes
                        setattr(self, key, config_dict[key])
                        print('loaded', key, '=', config_dict[key])
                    else:
                        print(key, 'is not a valid parameter name!')

    def save_config_into_json(self, config_path = './config.json'):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=4)





