import numpy as np

from PyQt5.QtCore import QRect, QLine, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QWindow
from PyQt5.QtWidgets import (
    QWidget,
    QLabel
)
from qimage2ndarray import array2qimage
from utils import roundButton

class StimulusWindow(QWidget):
    """
    The second window on which we present stimuli to be viewed by the animals
    """
    def __init__(self, *args, param, corner, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Stimulus Window')
        self.setGeometry(corner[0], corner[1], 500, 500)
        self.setStyleSheet("background-color: black;")

        # prepare attributes to store painting area rects
        self.rect = None # for single window
        self.prect = None # for panorama
        self.param = param # reference to parent parameters (= it is synchronized -- we are not copying anything)

        # ndarray of stimulus frame
        self.frame = None

        # flags
        self.show_calibration_frame = False # if true, show a frame around the paint area

        # get rid of the title bar and show the custom button (not complete... but I guess better?)
        self.setWindowFlags(Qt.Widget | Qt.CustomizeWindowHint)
        self.resize_buttons = [
            roundButton('', self, color_rgb=(200, 40, 20), radius=7), # red for close
            roundButton('', self, color_rgb=(200, 200, 20), radius=7), # yellow for minimize
            roundButton('', self, color_rgb=(40, 200, 20), radius=7), # green for expand/back to normal
        ]
        self.resize_buttons[0].clicked.connect(self.close)
        self.resize_buttons[1].clicked.connect(self.showMinimized)
        self.resize_buttons[2].clicked.connect(self.toggle_maximize)
        for i in range(3):
            self.resize_buttons[i].move(i*20+7, 10)


    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def paintEvent(self, event):
        """
        This is what is called if there is any need for repaint - paint event is emitted when the window is resized
        and update() or repaint() method of a QWidget is called.
        QPainter can only be used within painEvent() method of QWidget.
        """
        qp = QPainter()
        qp.begin(self)

        # todo: delegate actual painting to separate methods?
        # the paint method should receive image bitmap to be shown
        # the paint method should read rect information from the parent and use it to scale things
        # also there should be a choice of doing 1 window vs 3 window

        # todo: Fix how to handle paint scaling
        # Right now we specify the paint area rect from GUI and stretch whatever image returned by the stimulus
        # generator to this rect (instead of for example corresponding single image pixel to single device pixel)
        # This makes sense especially for panorama setups, where I would stretch whatever rendered frame to fit
        # physical screens on the spot (trusting the geometry of the setup). But if we are doing bottom projection
        # and specifying the stimuli in mm units, this can accidentally introduce weird stretching.
        # We could force the GUI-specified rect to retain the same ratio as the frame churned out by the stimulus
        # generator, or alternatively we could force stimulus generator to listen to the app and generate stimuli
        # with the same ratio as the rect.

        qp.setRenderHint(QPainter.SmoothPixmapTransform) # not sure if I want this

        """ Draw the stimulus bitmap """
        if self.frame is not None:
            qp.setBrush(QColor(*np.random.randint(0,255,3).astype(int)))
            qp.setPen(Qt.NoPen)
            qp.drawImage(QRect(self.param.x, self.param.y, self.param.w, self.param.h),
                         array2qimage(self.frame))

        """ Draw frame around the paint area (for calibration) """
        if self.show_calibration_frame:
            qp.setBrush(Qt.NoBrush)
            thick_pen = QPen(QColor(255, 0, 127))
            thick_pen.setWidth(3)
            qp.setPen(thick_pen)
            qp.drawRect(QRect(self.param.x, self.param.y, self.param.w, self.param.h)) # frame
            qp.drawLine(QLine(self.param.x, self.param.y+self.param.h//2,
                              self.param.x+self.param.w, self.param.y+self.param.h//2))
            qp.drawLine(QLine(self.param.x+self.param.w//2, self.param.y,
                              self.param.x+self.param.w//2, self.param.y+self.param.h))

        qp.end()

    def receive_and_paint_new_frame(self, frame):
        """
        This is called from upstream every time new stimulus frame is generated
        Receives a frame bitmap and paint it
        """
        self.frame = frame
        self.repaint()

    def toggle_calibration_frame(self, state):
        """ As we open/close the calibration panel (under ui),
        toggle the calibration frame around the paint area """
        self.show_calibration_frame = state