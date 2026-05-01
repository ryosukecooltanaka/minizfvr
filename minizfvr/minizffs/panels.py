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

    def __init__(self, *args, roi_x=0, roi_y=0, roi_w=100, roi_h=100, **kwargs):

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
        self.fish_area = pg.RectROI((roi_x, roi_y), (roi_w, roi_h), pen=dict(color=(5, 40, 200), width=3))

        # Thing to plot the tracked fish
        self.tracked_head = pg.ScatterPlotItem(symbol='o', pen=None, brush=(40,200,40), size=8)
        self.tracked_body = pg.PlotCurveItem(pen=dict(color=(40, 200, 200), width=3))
        self.trajectory = pg.PlotCurveItem(pen=dict(color=(20, 100, 20), width=2, style=Qt.DotLine))

        # connect everything
        self.addItem(self.display_area)
        self.display_area.addItem(self.fish_image_item)
        self.display_area.addItem(self.fish_area)
        self.display_area.addItem(self.tracked_head)
        self.display_area.addItem(self.tracked_body)
        self.display_area.addItem(self.trajectory)

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
        pos, size = self.get_area_spec(f)
        self.fish_area.setPos(pos, finish=False) # finish=False suppressses the sigRegionChangeFinished, so we don't go into loop
        self.fish_area.setSize(size, finish=False)
        self.level_adjust_flag = True

    def update_tracked_fish(self, data, scale):
        # data is 4 x N array in the order of x, y, theta, timestamp, where
        # the last column is always the latest
        if not np.isnan(data[0,-1]):
            self.tracked_head.setData((data[0,-1]*scale,), (data[1,-1]*scale,))
            body_x = np.asarray([0, -np.cos(data[2,-1])])*30 + data[0,-1]*scale
            body_y = np.asarray([0, -np.sin(data[2,-1])])*30 + data[1,-1]*scale
            self.tracked_body.setData(body_x, body_y)
        else:
            self.tracked_head.setData([])
            self.tracked_body.setData([])
        self.trajectory.setData(data[0, :]*scale, data[1, :]*scale)

    def switch_colormap(self, k: bool):
        if k:
            self.fish_image_item.setColorMap(pg.ColorMap((0,1), [(0,)*3,(255,)*3]))
        else:
            # in the order of BG, fish bounding box, body, head
            self.fish_image_item.setColorMap(pg.ColorMap((0,0.5,1), [(127,127,127),(255,255,0),(0,0,127)]))


class ControlPanel(QWidget):
    """
    Hosts buttons, check boxes and such for experiment control
    """

    def __init__(self):
        super().__init__()

        # Prepare widgets that control the parameters
        # preprocessing parameters
        self.connect_button = bistateButton('Connect', t2='Connected', c1='#FFF', c2='#E6C') # attempt connection to the stimulus window
        self.save_button = bistateButton('Save', t2='Stop', c1='#FFF', c2='#E6C') # attempt connection to the stimulus window
        
        self.show_raw_checkbox = QCheckBox('show raw') # if checked, show un-processed image
        self.show_bg_checkbox = QCheckBox('show bg') # if checked, show background image

        self.color_invert_checkbox = QCheckBox('invert') # if checked, invert image color (when fish is darker than the background)
        self.image_scale_box = TypeForcedEdit(float) # subclassed to only allow specific numeric types

        self.dilate_size_box = TypeForcedEdit(int)
        self.body_threshold_box = TypeForcedEdit(int)

        self.save_duration_box = TypeForcedEdit(float)

        self.arrange_widget()

    def arrange_widget(self):
        """
        Separating out arranging for visibility
        """

        # arrange preprocessing control widget into a grid layout
        grid = QGridLayout()
        self.save_button.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.connect_button.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.save_button.setMinimumWidth(100)
        grid.addWidget(self.save_button,           0, 0, 2, 1)
        grid.addWidget(self.connect_button,        2, 0, 2, 1)

        grid.addWidget(self.show_raw_checkbox,     0, 1, 1, 1) # row, col, rowspan, colspan
        grid.addWidget(self.show_bg_checkbox,      1, 1, 1, 1) # row, col, rowspan, colspan
        grid.addWidget(self.color_invert_checkbox, 2, 1, 1, 1)

        grid.addWidget(QLabel("Image Scale"),      0, 2, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.image_scale_box,       0, 3, 1, 1)

        grid.addWidget(QLabel("Dilation Scale"),   1, 2, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.dilate_size_box,       1, 3, 1, 1)

        grid.addWidget(QLabel("Body Threshold"),   2, 2, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.body_threshold_box,    2, 3, 1, 1)

        grid.addWidget(QLabel("Save duration"),    3, 2, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.save_duration_box,    3, 3, 1, 1)
        
        # Cosmetic size adjustment
        self.connect_button.setStyleSheet('font: bold 14px;')
        self.save_button.setStyleSheet('font: bold 14px;')

        self.setLayout(grid)

    def refresh_gui(self, p:FreeSwimmingParams):
        """
        Given the TailTrackerParam object, set the values of the widgets
        """
        # Put the parameter received into the GUI
        self.show_raw_checkbox.setChecked(p.show_raw)
        self.show_bg_checkbox.setChecked(p.show_bg)
        self.color_invert_checkbox.setChecked(p.color_invert)
        self.image_scale_box.setValue(p.image_scale)
        self.dilate_size_box.setValue(p.dilate_size)
        self.body_threshold_box.setValue(p.body_threshold)
        self.save_duration_box.setValue(p.save_duration)

    def return_current_value(self):
        return self.show_raw_checkbox.isChecked(),\
               self.show_bg_checkbox.isChecked(),\
               self.color_invert_checkbox.isChecked(),\
               self.image_scale_box.value(),\
               self.dilate_size_box.value(),\
               self.body_threshold_box.value(), \
               self.save_duration_box.value()
