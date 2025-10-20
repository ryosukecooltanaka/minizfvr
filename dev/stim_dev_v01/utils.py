"""
This file contains duplicates from trailtracker_dev_01/utils
Eventually combine everything into one place
"""


import numpy as np
import cv2
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QLineEdit,
    QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QWheelEvent

class TypeForcedEdit(QLineEdit):
    """
    Type-checking numeric entries in upper layers is stupid so we subclass LineEdit
    """
    def __init__(self, forced_type: type, scroll_step=None):
        super().__init__()
        self.val = None
        self.forced_type = forced_type

        # We implement wheelEvent so we can scroll to change values
        # We need to adjust the amount of change per one wheel tick
        if not scroll_step: # default
            self.scroll_step = forced_type(1.0) # cast
        else:
            self.scroll_step = forced_type(scroll_step)

        # Every time we type in new values, we make sure they conform to whatever type we expect
        # otherwise we keep the old value
        self.editingFinished.connect(self._force_type)

    def setValue(self, val):
        """
        This is used to set a new value from the program
        """
        try:
            fval = self.forced_type(val) # cast
            self.val = fval
            self.setText(str(fval))
        except ValueError:
            # It is very unlikely we reach here
            print('cannot cast the programmatically set new value into type:', self.forced_type)

    def _force_type(self):
        """
        A callback function after edit finish
        """
        new_text = self.text()
        try:
            casted = self.forced_type(new_text)
            self.val = casted
            self.setText(str(self.val))
        except ValueError:
            print('cannot cast the input into type:', self.forced_type)
            self.setText(str(self.val))

    def value(self):
        """
        Static method, so it will behave similarly to sliders etc.
        """
        return self.val

    def wheelEvent(self, event: QWheelEvent):
        """
        Add scroll behavior for easier interactive control of numeric values
        In a typical mouse while, one tick corresponds to 15 degrees, which is 120 angleDelta (in int)
        """

        # get how many ticks we moved
        # we cast to float, just in case we happen to have a mouse with a finer reso wheel
        tick_delta = float(event.angleDelta().y()) / 120.0
        self.setValue(self.val + tick_delta*self.scroll_step) # casting happens inside
        self.editingFinished.emit()



class roundButton(QLabel):
    """
    For the stimulus window, we do not want the titlebar to be showing because it can be bright
    Instead, we will show a subtle round icon, based on LineEdit
    """

    clicked = pyqtSignal() # make it clickable

    def __init__(self, *args, color_rgb=(255, 0, 0), radius=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.color_rgb = color_rgb
        self.radius = radius
        self.resize(radius*2, radius*2)
        self.changeAlpha(30)

    def changeAlpha(self, alpha):
        self.setStyleSheet(
            """
            text-align: center;
            background-color: rgba({0}, {1}, {2}, {3}%);
            border-radius: {4}px;
            """.format(*self.color_rgb, alpha, self.radius)
        )

    def mousePressEvent(self, e):
        self.clicked.emit()


    def enterEvent(self, *args, **kwargs):
        self.changeAlpha(100)

    def leaveEvent(self, *args, **kwargs):
        self.changeAlpha(30)







