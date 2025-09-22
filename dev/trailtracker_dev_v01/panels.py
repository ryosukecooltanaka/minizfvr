import numpy as np
import pyqtgraph as pg
import sys


from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QLabel,
    QSizePolicy,
    QInputDialog
)


class CameraPanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the camera view
    It holds image from camera + tail standard + tracked tail
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This is the "GraphicsItem" that is added to the widget
        self.display_area = pg.ViewBox(invertY=True, lockAspect=True)  # this graphics item implements easy scaling

        # Objects to be added to the View Box
        self.fish_image_item = pg.ImageItem(axisOrder='row-major')
        self.tail_standard = pg.LineSegmentROI([(10, 10), (100, 100)])
        self.tail_standard.setPen(dict(color=(5, 40, 200), width=3))
        self.tail_tracked = pg.PlotCurveItem()
        self.tail_tracked.setPen(dict(color=(245, 30, 200), width=3))

        # connect everything
        self.addItem(self.display_area)
        self.display_area.addItem(self.fish_image_item)
        self.display_area.addItem(self.tail_standard)
        self.display_area.addItem(self.tail_tracked)

        # Some other flags
        self.init_frame_frag = True

    def set_image(self, image):
        """ Image update method """
        self.fish_image_item.setImage(image, autoLevels=self.init_frame_frag)
        if self.init_frame_frag:
            self.init_frame_frag = False

    def get_base_tip_position(self):
        """
        Return the current base and tip position of the tail standard (in image coordinate)
        """
        base_x = self.tail_standard.getLocalHandlePositions(0)[1].x()
        base_y = self.tail_standard.getLocalHandlePositions(0)[1].y()
        tip_x = self.tail_standard.getLocalHandlePositions(1)[1].x()
        tip_y = self.tail_standard.getLocalHandlePositions(1)[1].y()
        return (base_x, base_y), (tip_x, tip_y)

    def update_tracked_tail(self, segments):
        self.tail_tracked.setData(segments[0, :], segments[1, :])



class AnglePanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the tail angle plot
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepare tail angle plot item & data
        self.angle_plot = pg.PlotItem()
        self.angle_plot_data = pg.PlotDataItem()
        # connect everything
        self.addItem(self.angle_plot)
        self.angle_plot.addItem(self.angle_plot_data)

    def set_data(self, x, y):
        """ Data update method """
        self.angle_plot_data.setData(x, y)


class ControlPanel(QWidget):
    """
    Hosts buttons, check boxes and such for experiment control
    """

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        for i in range(4):
            layout.addWidget(QLabel('dummy'))
        self.setLayout(layout)