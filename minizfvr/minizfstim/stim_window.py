from PyQt5.QtCore import QRect, QLine, Qt
from PyQt5.QtGui import QPainter, QPen, QColor, QTransform
from PyQt5.QtWidgets import (
    QWidget,
)
from qimage2ndarray import array2qimage
from ..utils import roundButton
from .parameters import StimParamObject

class StimulusWindow(QWidget):
    """
    The second window on which we present stimuli to be viewed by the animals
    """
    def __init__(self, *args, param: StimParamObject, corner, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Stimulus Window')
        self.setGeometry(corner[0], corner[1], 500, 500)
        self.setStyleSheet("background-color: black;")

        # reference to parent parameters (= it is synchronized -- we are not copying anything)
        self.param = param

        ## Prepare paint areas (as list, to force unified behaviors)
        if not self.param.is_panorama:
            self.canvas = [PaintCanvas(parent=self)]
        else:
            self.canvas = [
                PaintCanvas(parent=self, rotation=-90, invert=True, screen_name='L', screen_color=(200, 30, 30)),
                PaintCanvas(parent=self, rotation=0,   invert=True, screen_name='F', screen_color=(30, 200, 30)),
                PaintCanvas(parent=self, rotation=+90, invert=True, screen_name='R', screen_color=(30, 30, 200))
            ]
        self.adjust_canvas()

        ## Get rid of the title bar and show the custom button
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

    def adjust_canvas(self):
        """
        Set the new geometry for paint canvas according to the latest parameter.
        This is a parameter change callback.
        """

        if not self.param.is_panorama:
            self.canvas[0].paint_area_rect = (0 , 0, self.param.w, self.param.h)
            self.canvas[0].setGeometry(self.param.x, self.param.y, self.param.w, self.param.h)
        else:
            # Move paint canvas according to the parameter
            # also, take care of translation necessary for fitting flipped/rotated image into the widget
            # left screen
            self.canvas[0].setGeometry(self.param.x,
                                       self.param.y+self.param.ph+self.param.ppad,
                                       self.param.ph, self.param.pw)
            self.canvas[0].paint_area_offset = (self.param.ph, self.param.pw)
            # front screen
            self.canvas[1].setGeometry(self.param.x+self.param.ph+self.param.ppad,
                                       self.param.y,
                                       self.param.pw, self.param.ph)
            self.canvas[1].paint_area_offset = (0, self.param.ph)
            # right screen
            self.canvas[2].setGeometry(self.param.x+self.param.ph+self.param.ppad*2+self.param.pw,
                                       self.param.y+self.param.ph+self.param.ppad,
                                       self.param.ph, self.param.pw)
            self.canvas[2].paint_area_offset = (0, 0)
            for canvas in self.canvas:
                canvas.paint_area_rect = (0, 0, self.param.pw, self.param.ph)


    def receive_and_paint_new_frame(self, frame):
        """
        This is called from upstream every time new stimulus frame is generated
        Receives a frame bitmap and paint it
        """
        for this_frame, canvas in zip(frame, self.canvas):
            canvas.frame = this_frame
            canvas.repaint(0, 0, canvas.width(), canvas.height()) # just to be explicit... prob. doesn't matter

    def toggle_calibration_frame(self, state):
        """ As we open/close the calibration panel (under ui),
        toggle the calibration frame around the paint area """
        for canvas in self.canvas:
            canvas.show_calibration_frame = state
        self.update()

class PaintCanvas(QWidget):
    """
    A rectangular container for the drawImage paint region.
    The reason why we want this container (rather than directly drawing images onto the StimulusWindow)
    is because the execution time of repaint() scales with the number of pixels, even if these pixels are
    not changing. We can achieve the equivalent effect by specifying the update region as a rect
    when calling repaint(), but for the panorama case, we will still have empty areas between the screens
    and not updating these pixels will have meaningful impacts on the duration of repaint() call
    """
    def __init__(self,
                 parent,
                 invert=False,
                 rotation=0.0,
                 screen_name=None,
                 screen_color=(255, 0, 0)):

        super().__init__(parent)


        # fixed parameter, should be passed at construction
        self.invert = invert
        self.rotation = rotation
        self.screen_name = screen_name
        self.screen_color = screen_color

        # dynamically updated ones
        self.frame = None
        self.show_calibration_frame = False
        self.paint_area_rect = None # we need to keep track of this pre-transform
        self.paint_area_offset = (0,0) # there should be nice mathematical way to derive this, but doing it dumb way

    def paintEvent(self, event):
        """
        This is what is called if there is any need for repaint - paint event is emitted when the window is resized
        and update() or repaint() method of a QWidget is called.
        QPainter can only be used within painEvent() method of QWidget.
        """
        qp = QPainter()
        qp.begin(self)
        qp.setRenderHint(QPainter.SmoothPixmapTransform) # not sure if I want this
        self.paint_frame(qp)
        qp.end()

    def paint_frame(self, qp:QPainter):
        """
        Draw the stimulus bitmap, filling the entire widget
        """
        # apply transform if necessary (for panorama case)
        qp.setPen(Qt.NoPen)
        qp.setBrush(Qt.NoBrush)

        transform = QTransform()
        transform.translate(*self.paint_area_offset)
        transform.rotate(self.rotation)
        if self.invert:
            transform.scale(1.0, -1.0)

        qp.setTransform(transform)
        rect = QRect(*self.paint_area_rect)

        if self.frame is not None:
            qp.drawImage(rect, array2qimage(self.frame))

        """ Draw frame around the paint area (for calibration) """
        if self.show_calibration_frame:
            thick_pen = QPen(QColor(255, 0, 127))
            thick_pen.setWidth(3)
            qp.setPen(thick_pen)
            qp.drawRect(rect)  # frame
            qp.drawLine(QLine(0, rect.height() // 2, rect.width(), rect.height() // 2)) # center line
            qp.drawLine(QLine(rect.width() // 2, 0, rect.width() // 2, rect.height()))

            # draw letter as well
            if self.screen_name is not None:
                font = qp.font()
                font.setPixelSize(min(self.height(), self.width()))
                qp.setFont(font)
                qp.setPen(QPen(QColor(*self.screen_color)))
                qp.drawText(rect, Qt.AlignCenter, self.screen_name)
