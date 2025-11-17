from dataclasses import dataclass
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from ..parameters import BaseParams

@dataclass
class StimulusAppParams(BaseParams):

    is_panorama: bool = False

    # config path (home directory)
    config_path: str = str(Path.home() / 'minizfstim_config.json')

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


