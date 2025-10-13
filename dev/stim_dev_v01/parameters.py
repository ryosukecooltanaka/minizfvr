from dataclasses import dataclass
import json
import os
import sys

"""
Class to store parameters for the stimulus app (think names...)
"""

# duplicate of what's in the tail tracker params
# eventually combine into one thing
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
class StimulusAppParams(BaseParams):

    is_panorama: bool = False

    # specify paint area (for single window mode)
    x: int = 0
    y: int = 0
    w: int = 500
    h: int = 500

    # specify panorama window shapes and spacing
    pw: int = 300
    ph: int = 300
    ppad: int = 30 # inner padding to prevent shadowing due to the mirror geometry

    # calibration parameter, for when you want to specify stimulus in terms of mm
    physical_x: float = 10.0
    px_per_mm: float = 1.0

    # saving related
    save_path: str = './'

    # animal metadata
    animal_id: int = 0
    animal_genotype: str = 'WT'
    animal_age: int = 7
    animal_comment: str = ''

