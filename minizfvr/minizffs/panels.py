import numpy as np
import pyqtgraph as pg
from .parameters import FreeSwimmingParams
from ..utils import TypeForcedEdit, bistateButton

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

    def __init__(self, *args, rect_x=0, rect_y=0, rect_w=100, rect_h=100, **kwargs):

        # The reason I am passing the input arguments to the constructor is 
        # so you can load last-used ROI settings from the config file.
        # Maybe this is nice, if you are running experiments on the same rig
        # every day?

        super().__init__()
        # This is the "GraphicsItem" that is added to the widget
        self.display_area = pg.ViewBox(invertY=True, lockAspect=True)  # this graphics item implements easy scaling

        ## Objects to be added to the View Box
        # The thing on which we put the image from the camera
        self.fish_image_item = pg.ImageItem(axisOrder='row-major')
        # ROI within which we look for fish
        self.fish_area = pg.RectROI((rect_x, rect_y), (rect_w, rect_h))
        # Thing to plot the tracked fish
        self.fish_tracked = pg.PlotCurveItem()

        # old stuff to be removed
        self.fish_area.setPen(dict(color=(5, 40, 200), width=3))
        self.fish_tracked.setPen(dict(color=(245, 30, 200), width=3))

        # connect everything
        self.addItem(self.display_area)
        self.display_area.addItem(self.fish_image_item)
        self.display_area.addItem(self.fish_area)
        self.display_area.addItem(self.fish_tracked)

        # Some other flags
        self.level_adjust_flag = True # we do one-shot level adjust at start-up & parameter change

    def set_image(self, image):
        """ Image update method """
        if image is not None:
            self.fish_image_item.setImage(image, autoLevels=self.level_adjust_flag)

            if self.level_adjust_flag:
                self.level_adjust_flag = False

    def get_area_spec(self, factor=1.0):
        """
        Return the current position/size of the rectangular area (in image coordinate)
        with factors, in case we are viewing the raw image while we operate on scaled images
        """
        x, y = self.fish_area.pos()
        w, h = self.fish_area.size()
        return (x*factor, y*factor), (w*factor, h*factor)

    def refresh_gui(self, f):
        """
        Refresh GUI -- This method is triggered by parameter change events.
        When switching between showing raw and scaled images, keep the ROI in the same relative position.
        Also flag frame contrast adjustment.
        """
        pos, size = self.get_area_spec()
        print(pos, size)
        #for h, pos in zip(self.tail_standard.handles, (base, tip)):
        #    newPos = QPointF(*[val * f for val in pos])
        #    h['item'].setPos(newPos) # copied over from pyqtgraph source code -- not sure why we need item/pos
        #    h['pos']= newPos
        self.level_adjust_flag = True

    def update_tracked_tail(self):
        pass

class TracePanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the trace plot
    3 traces per fish (x, y , theta)
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        # Prepare tail angle plot item & data
        self.plot = pg.PlotItem()
        self.plot_datas = [pg.PlotDataItem() for i in range(3)]

        self.plot_datas[0].setPen(dict(color=(225, 30, 200), width=1))
        self.plot_datas[1].setPen(dict(color=(225, 200, 30), width=1))
        self.plot_datas[2].setPen(dict(color=(200, 30, 225), width=1))

        # connect everything
        for pdata in self.plot_datas:
            self.addItem(self.plot)
            self.plot.addItem(pdata)

    def set_data(self, i, t, val):
        """ Data update method """
        self.plot_datas[i].setData(t, val)

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

    def refresh_gui(self, p:FreeSwimmingParams):
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
