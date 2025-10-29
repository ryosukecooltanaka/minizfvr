import numpy as np

from PyQt5.QtCore import QRect, QLine, Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QTransform, QWindow
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

        qp.setRenderHint(QPainter.SmoothPixmapTransform) # not sure if I want this
        qp.setPen(Qt.NoPen)

        if not self.param.is_panorama:
            self.paint_single_window_stimulus(qp)
        else:
            self.paint_panorama_stimulus(qp)

        qp.end()

    def paint_single_window_stimulus(self, qp:QPainter):
        """
        Draw the stimulus bitmap for single window case
        """

        # origin shift
        qp.translate(self.param.x, self.param.y)

        if self.frame is not None:
            qp.drawImage(QRect(0, 0, self.param.w, self.param.h), array2qimage(self.frame))

        """ Draw frame around the paint area (for calibration) """
        if self.show_calibration_frame:
            qp.setBrush(Qt.NoBrush)
            thick_pen = QPen(QColor(255, 0, 127))
            thick_pen.setWidth(3)
            qp.setPen(thick_pen)
            qp.drawRect(QRect(0, 0, self.param.w, self.param.h))  # frame
            qp.drawLine(QLine(0, self.param.h // 2, self.param.w, self.param.h // 2))
            qp.drawLine(QLine(self.param.w // 2, 0, self.param.w // 2, self.param.h))

    def paint_panorama_stimulus(self, qp:QPainter):
        """
        Draw panoramic stimulus
        When we are doing the panoramic mode, stimulus generator will return a list of 3 rendered images (in upright
        position). We have to appropriately invert and rotate these images considering the mirrors. We achieve this
        inversion using QTransform.
        We assume the frames to be ordered from left to right.
        """

        # first, prepare transforms (with the global origin transform)
        transforms = [QTransform().translate(self.param.x, self.param.y) for i in range(3)]

        # additional translation to top left corner of all images
        transforms[0].translate(self.param.ph, self.param.ph+self.param.ppad+self.param.pw)
        transforms[1].translate(self.param.ph+self.param.ppad, self.param.ph)
        transforms[2].translate(self.param.ph+self.param.ppad*2+self.param.pw, self.param.ph+self.param.ppad)

        # rotation
        transforms[0].rotate(-90)
        transforms[2].rotate(+90)

        # scaling
        transforms = [x.scale(1.0, -1.0) for x in transforms]
        rect = QRect(0, 0, self.param.pw, self.param.ph)

        if self.frame is not None:
            for this_transform, this_frame in zip(transforms, self.frame):
                qp.setTransform(this_transform)
                qp.drawImage(rect, array2qimage(this_frame))

        # calibration frame
        if self.show_calibration_frame:
            qp.setBrush(Qt.NoBrush)
            thick_pen = QPen(QColor(255, 0, 127))
            thick_pen.setWidth(3)
            qp.setPen(thick_pen)
            for this_transform in transforms:
                qp.setTransform(this_transform)
                qp.drawRect(rect)


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
        self.repaint()