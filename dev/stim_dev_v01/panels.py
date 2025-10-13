from utils import TypeForcedEdit
import numpy as np
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtWidgets import (
    QWidget,
    QCheckBox,
    QGridLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSizePolicy
)

"""
Control UIs for the stimulus app
"""

class StimulusControlPanel(QWidget):
    """
    Main widget of the StimulusControlWindow
    Instead of having a giant list of parameters, delegate these to sub-windows, and
    just have buttons to open the sub-windows here
    """

    def __init__(self, param):
        super().__init__()

        # panorama mode flag
        self.param = param

        # Buttons
        self.start_button = QPushButton('Start')
        self.reset_button = QPushButton('Reset')
        self.connect_button = QPushButton('Connect')
        self.calibrate_button = QPushButton('Calibrate')
        self.metadata_button = QPushButton('Metadata')
        buttons = (self.start_button, self.reset_button, self.connect_button, self.calibrate_button, self.metadata_button)
        height_ratio = (3,1,1,1,1)

        # make buttons stretchy & arrange
        layout = QVBoxLayout()
        for button, hr in zip(buttons, height_ratio):
            button.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
            layout.addWidget(button, hr)
        self.setLayout(layout)

        # prepare subwindows
        self.calibration_panel = CalibrationPanel(param)
        self.metadata_panel = MetadataPanel(param)

        # connect callbacks (just the ones concerning UIs -- callbacks related to actually doing things are
        # set from higher-up
        self.calibrate_button.clicked.connect(self.calibration_panel.refresh_gui)
        self.metadata_button.clicked.connect(self.metadata_panel.refresh_gui)


class CalibrationPanel(QWidget):
    """
    Sub-window for the StimulusControlPanel
    Here you will specify the position and the size of the paint area
    Also you will type in the physical dimension of the screen, so that the program knows
    how many pixels correspond to how many mm (only relevant for non-panorama mode)
    """

    def __init__(self, param):
        super().__init__()

        self.param = param

        # text boxes for typing in rect info
        self.x_box = TypeForcedEdit(int)
        self.y_box = TypeForcedEdit(int)
        self.w_box = TypeForcedEdit(int)
        self.h_box = TypeForcedEdit(int)
        self.pad_box = TypeForcedEdit(int)
        self.physical_x_box = TypeForcedEdit(float)
        boxes = (self.x_box, self.y_box, self.w_box, self.h_box)
        box_names = ('x (px)', 'y (px)', 'width (px)', 'height (px)')

        # arrange widgets & connect callback
        layout = QGridLayout()
        for box, box_name, i in zip(boxes, box_names, range(4)):
            layout.addWidget(QLabel(box_name), i, 0)
            layout.addWidget(box, i, 1)
            box.editingFinished.connect(self.refresh_param)


        # In panorama mode, we need padding, otherwise we need a box for physical dimension
        if self.param.is_panorama:
            layout.addWidget(QLabel('padding (px)'), 4, 0)
            layout.addWidget(self.pad_box, 4, 1)
            self.pad_box.editingFinished.connect(self.refresh_param)
        else:
            layout.addWidget(QLabel('physical x (mm)'), 4, 0)
            layout.addWidget(self.physical_x_box, 4, 1)
            self.physical_x_box.editingFinished.connect(self.refresh_param)

        self.setLayout(layout)

    def refresh_gui(self):
        """
        Put whatever is in the param into the GUI
        """
        self.x_box.setValue(self.param.x)
        self.y_box.setValue(self.param.y)
        if not self.param.is_panorama:
            self.w_box.setValue(self.param.w)
            self.h_box.setValue(self.param.h)
            self.physical_x_box.setValue(self.param.physical_x)
        else:
            self.w_box.setValue(self.param.pw)
            self.h_box.setValue(self.param.ph)
            self.pad_box.setValue(self.param.ppad)
        self.show()

    def refresh_param(self):
        """
        Put whatever is in the GUI into the param
        """
        self.param.x = self.x_box.value()
        self.param.y = self.y_box.value()
        if not self.param.is_panorama:
            self.param.w = self.w_box.value()
            self.param.h = self.h_box.value()
            self.param.physical_x = self.physical_x_box.value()
            self.param.px_per_mm = self.param.w / self.param.physical_x
        else:
            self.param.pw = self.w_box.value()
            self.param.ph = self.h_box.value()
            self.param.ppad = self.pad_box.value()

class MetadataPanel(QWidget):
    """
    Sub-window for the StimulusControlPanel
    Here you will specify the animal metadata
    """

    def __init__(self, param):
        super().__init__()

        self.param = param

        # text boxes for typing in rect info
        self.savepath_box = QLineEdit()
        self.id_box = TypeForcedEdit(int)
        self.genotype_box = QLineEdit()
        self.age_box = TypeForcedEdit(int)
        self.comment_box = QLineEdit()
        self.comment_box.setMinimumHeight(100)

        boxes = (self.savepath_box, self.id_box, self.genotype_box, self.age_box, self.comment_box)
        box_names = ('path', 'id', 'genotype', 'age', 'comment')

        # arrange widgets
        layout = QGridLayout()
        for box, box_name, i in zip(boxes, box_names, range(5)):
            layout.addWidget(QLabel(box_name), i, 0)
            layout.addWidget(box, i, 1)
            box.editingFinished.connect(self.refresh_param)

        self.setLayout(layout)

    def refresh_gui(self):
        """
        Put whatever is in the param into the GUI
        """
        self.savepath_box.setText(self.param.save_path)
        self.id_box.setValue(self.param.animal_id)
        self.genotype_box.setText(self.param.animal_genotype)
        self.age_box.setValue(self.param.animal_age)
        self.comment_box.setText(self.param.animal_comment)
        self.show()

    def refresh_param(self):
        """
        Put whatever is in the GUI into the param
        """
        self.param.save_path = self.savepath_box.text()
        self.param.animal_id = self.id_box.value() # type check callback should happen before we reach here
        self.param.animal_genotype = self.genotype_box.text()
        self.param.animal_age = self.age_box.value()
        self.param.animal_comment = self.comment_box.text()