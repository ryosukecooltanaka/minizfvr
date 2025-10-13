"""
This file contains duplicates from trailtracker_dev_01/utils
Eventually combine everything into one place
"""


import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QLineEdit,
)

class TypeForcedEdit(QLineEdit):
    """
    Type-checking numeric entries in upper layers is stupid so we subclass LineEdit
    """
    def __init__(self, forced_type: type):
        super().__init__()
        self.val = None
        self.forced_type = forced_type
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
