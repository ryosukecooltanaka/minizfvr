import numpy as np
import pyqtgraph as pg
from parameters import TailTrackerParams
from utils import TypeForcedEdit, bistateButton

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtWidgets import (
    QWidget,
    QCheckBox,
    QGridLayout,
    QLabel,
    QSlider,
    QPushButton,
    QSizePolicy
)


class CameraPanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the camera view
    It holds image from camera + tail standard + tracked tail
    """

    def __init__(self, *args, base_x, base_y, tip_x, tip_y, **kwargs):
        super().__init__()
        # This is the "GraphicsItem" that is added to the widget
        self.display_area = pg.ViewBox(invertY=True, lockAspect=True)  # this graphics item implements easy scaling

        # Objects to be added to the View Box
        self.fish_image_item = pg.ImageItem(axisOrder='row-major')
        self.tail_standard = pg.LineSegmentROI([(base_x, base_y), (tip_x, tip_y)])
        self.tail_standard.setPen(dict(color=(5, 40, 200), width=3))
        self.tail_standard.translatable = False # prevent inadvertently adding weird offsets
        self.tail_tracked = pg.PlotCurveItem()
        self.tail_tracked.setPen(dict(color=(245, 30, 200), width=3))

        # connect everything
        self.addItem(self.display_area)
        self.display_area.addItem(self.fish_image_item)
        self.display_area.addItem(self.tail_standard)
        self.display_area.addItem(self.tail_tracked)

        # Some other flags
        self.level_adjust_flag = True # we do one-shot level adjust at start-up & parameter change

    def set_image(self, image):
        """ Image update method """
        if image is not None:
            self.fish_image_item.setImage(image, autoLevels=self.level_adjust_flag)
            if self.level_adjust_flag:
                self.level_adjust_flag = False

    def get_base_tip_position(self, factor=1.0):
        """
        Return the current base and tip position of the tail standard (in image coordinate)
        with factors, in case we are viewing the raw image while we operate on scaled images
        """
        base_x = self.tail_standard.getLocalHandlePositions(0)[1].x() * factor
        base_y = self.tail_standard.getLocalHandlePositions(0)[1].y() * factor
        tip_x = self.tail_standard.getLocalHandlePositions(1)[1].x() * factor
        tip_y = self.tail_standard.getLocalHandlePositions(1)[1].y() * factor
        return (base_x, base_y), (tip_x, tip_y)

    def refresh_gui(self, f):
        """
        Refresh GUI (mostly the tail standard) -- This method is triggered by parameter change events.
        When switching between showing raw and scaled images,  keep the tail standard in the same relative position.
        Also flag frame contrast adjustment.
        """
        base, tip = self.get_base_tip_position()
        for h, pos in zip(self.tail_standard.handles, (base, tip)):
            newPos = QPointF(*[val * f for val in pos])
            h['item'].setPos(newPos) # copied over from pyqtgraph source code -- not sure why we need item/pos
            h['pos']= newPos
        self.level_adjust_flag = True

    def update_tracked_tail(self, segments, factor=1.0):
        self.tail_tracked.setData(segments[0, :]*factor, segments[1, :]*factor)

class AnglePanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the tail angle plot
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        # Prepare tail angle plot item & data
        self.angle_plot = pg.PlotItem()
        self.angle_plot_data = pg.PlotDataItem()
        self.angle_plot_data.setPen(dict(color=(225, 30, 200), width=1))
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

        # Prepare widgets that control the parameters
        # preprocessing parameters
        self.connect_button = bistateButton('Connect', t2='Connected', c1='#FFF', c2='#E6C') # attempt connection to the stimulus window
        self.show_raw_checkbox = QCheckBox('show raw') # if checked, show un-processed image
        self.color_invert_checkbox = QCheckBox('invert') # if checked, invert image color (when fish is darker than the background)
        self.image_scale_box = TypeForcedEdit(float) # subclassed to only allow specific numeric types
        self.filter_size_slider = QSlider(Qt.Horizontal)
        self.clip_threshold_slider = QSlider(Qt.Horizontal)
        self.arrange_widget()

    def arrange_widget(self):
        """
        Separating out arranging for visibility
        """
        # some necessary initialization of individual widgets
        self.filter_size_slider.setMinimum(1)
        self.filter_size_slider.setMaximum(10)
        self.filter_size_slider.setSingleStep(1)
        self.filter_size_slider.setTickInterval(1)
        self.filter_size_slider.setTickPosition(QSlider.TicksBelow)

        self.clip_threshold_slider.setMinimum(0)
        self.clip_threshold_slider.setMaximum(255)
        self.clip_threshold_slider.setTickInterval(32)
        self.clip_threshold_slider.setTickPosition(QSlider.TicksBelow)

        # arrange preprocessing control widget into a grid layout
        grid = QGridLayout()
        self.connect_button.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.connect_button.setMinimumWidth(100)
        grid.addWidget(self.connect_button,        0, 0, 2, 1)
        grid.addWidget(self.show_raw_checkbox,     0, 1, 1, 1) # row, col, rowspan, colspan
        grid.addWidget(self.color_invert_checkbox, 1, 1, 1, 1)
        grid.addWidget(QLabel("Image Scale"),      0, 2, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.image_scale_box,       1, 2, 1, 1)
        grid.addWidget(QLabel("Filter Size"),      0, 3, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.filter_size_slider,    1, 3, 1, 1)
        grid.addWidget(QLabel("Clip Threshold"),   0, 4, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.clip_threshold_slider, 1, 4, 1, 1)

        # Cosmetic size adjustment
        self.connect_button.setStyleSheet('font: bold 14px;')
        self.image_scale_box.setMaximumWidth(50)
        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(4, 2)

        self.setLayout(grid)

    def refresh_gui(self, p:TailTrackerParams):
        """
        Given the TailTrackerParam object, set the values of the widgets
        """
        # Put the parameter received into the GUI
        self.show_raw_checkbox.setChecked(p.show_raw)
        self.color_invert_checkbox.setChecked(p.color_invert)
        self.image_scale_box.setValue(p.image_scale)
        self.filter_size_slider.setValue(p.filter_size)
        self.clip_threshold_slider.setValue(p.clip_threshold)

    def return_current_value(self):
        return self.show_raw_checkbox.isChecked(),\
               self.color_invert_checkbox.isChecked(),\
               self.image_scale_box.value(),\
               self.filter_size_slider.value(),\
               self.clip_threshold_slider.value()
