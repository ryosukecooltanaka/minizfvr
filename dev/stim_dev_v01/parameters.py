from dataclasses import dataclass
import json
import os
import sys
from PyQt5.QtCore import QObject, pyqtSignal

"""
Class to store parameters for the stimulus app (think names...)
"""

# duplicate of what's in the tail tracker params
# eventually combine into one thing
class BaseParams:
    """
    Implement methods to read/write parameters from json
    """
    def load_config_from_json(self, config_path = './config.json', verbose=False):
        if os.path.isfile(config_path):
            print('Loading parameters from ', config_path)
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
                self.read_param_from_dict(config_dict, verbose=verbose)

    def save_config_into_json(self, config_path = './config.json'):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=4)
        print('Saved parameters to ', config_path)

    def read_param_from_dict(self, param_dict, verbose=False):
        for key in param_dict.keys():
            if hasattr(self, key):  # so we don't inject weird attributes
                current_type = type(getattr(self, key))
                setattr(self, key, current_type(param_dict[key]))
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
    physical_w: float = 10.0
    px_per_mm: float = 1.0

    # relates to scaling
    bitmap_w: int = 0
    bitmap_h: int = 0
    force_equal_ratio: bool = False

    # desired frame rate
    frame_rate: int = 60

    # saving related
    save_path: str = './'
    save_buffer_size: int = 500

    # animal metadata
    animal_id: int = 0
    animal_genotype: str = 'WT'
    animal_age: int = 7
    animal_comment: str = ''

class StimParamObject(QObject, StimulusAppParams):
    """
    We combine the parameter class with QObject, so it can emit an event.
    This helps us keep the GUI and parameter behind it in sync without messing things up.

    Whenever we edit things from the GUI panel, callback functions will update the parameter.
    Then we will make the StimParamObject emit the paramChanged signal.
    This signal is then connected to a method that updates the GUI panel.

    This is better than calling the GUI update method directly from the GUI callback in terms of modularity
    (that is, direct calls can become too tangled as the app gets bigger)

    We can also connect other methods, such as the stimulus window update, to this paramChanged signal,
    such that parameter changes from the GUI is immediately reflected to what is painted etc.
    """
    paramChanged = pyqtSignal() # this is a class attribute (as opposed to instance attribute)


