"""

minizfvr app development version 0

2025/09/16 Ryosuke Tanaka

Some key things to get done here
- Make an app with two windows, one for humans to see, the other for fish to see
- Implement frame loading from camera, tail tracking algorithm, some sort of data logging
- Worry about multiprocessing later
- Split things into different files in the end

"""

import numpy as np
import sys
import pyqtgraph as pg
import PySpin

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

class HumanWindow(QMainWindow):
    """
    Main GUI window for humans to see.
    Displays fish image, tail trace, and other controls.
    """
    
    def __init__(self):
        """ 
        The main window constructor. Called once at the beginning.
        """
        
        # Call the parental (QMainWindow) constructor
        super().__init__()
        
        # set window title and size 
        self.setWindowTitle("minizfvr test v0")  # window title
        self.setGeometry(50, 50, 400,600)  # default window position and size (x, y, w, h)
        
        # The main window needs to have a single, central widget (which is just a empty container).
        # Widgets like buttons will be arranged inside the container later.
        container = QWidget()
        self.setCentralWidget(container)
        
        # Create other widgets 
        self.stimulus_window = StimulusWindow()
        self.camera_display = pg.GraphicsLayoutWidget() # sort of a container
        self.angle_display = pg.GraphicsLayoutWidget() # a container
        self.control_panel = ControlPanel()

        # Prepare camera view + tail axis
        # register viewbox > image to the camera display
        self.display_area = pg.ViewBox(invertY=True, lockAspect=True) # this graphics item implements easy scaling
        self.camera_display.addItem(self.display_area) # add ViewBox to GraphicLayoutWidget
        self.image_item = pg.ImageItem()
        self.display_area.addItem(self.image_item) # add ImageItem to ViewBox
        self.tail_standard = pg.LineSegmentROI([(10,10),(100,100)])
        self.tail_standard.setPen(dict(color=(5, 40, 200), width=3))
        self.display_area.addItem(self.tail_standard)

        # Prepare tail angle plot
        self.angle_plot = pg.PlotItem()
        self.angle_display.addItem(self.angle_plot)
        self.angle_line = pg.PlotDataItem()
        self.angle_plot.addItem(self.angle_line)

        # Create vertical box layout. From top, we will show camera image, tail plot, and controls
        # Control box will require layouts of its own, but let's worry about that later
        layout = QVBoxLayout()
        layout.addWidget(self.camera_display)
        layout.addWidget(self.angle_display)
        layout.addWidget(self.control_panel)
        container.setLayout(layout)
        
        # show the stimulus window
        self.stimulus_window.show()

        # initialize camera
        self.system = []
        self.camera = []
        self.initialize_camera()
        
        # Define timer for GUI
        self.timer = QTimer()
        self.timer.setInterval(50) # millisecond
        self.timer.timeout.connect(self.fetch_and_show_image) # define callback
        self.timer.start()
        
        
    def initialize_camera(self):
        self.system = PySpin.System.GetInstance()
        self.camera = self.system.GetCameras()[0]
        self.camera.Init()
        self.camera.BeginAcquisition()
        
    def fetch_and_show_image(self):
        fetched_image = self.camera.GetNextImage()
        if not fetched_image.IsIncomplete():
            converted_image = np.array(fetched_image.GetData(), dtype='uint8').reshape((fetched_image.GetHeight(), fetched_image.GetWidth()))
            fetched_image.Release()
        self.image_item.setImage(converted_image)
        self.angle_line.setData(np.arange(converted_image.shape[1]), np.mean(converted_image, axis=0))
        
        
        
class StimulusWindow(QWidget):
    def __init__(self):
        super().__init__()

        
class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()  
        layout = QHBoxLayout()
        for i in range(4):
            layout.addWidget(QLabel('dummy'))
        self.setLayout(layout)
        
def main():
    """ 
    This is what is called upon when you execute the file. 
    """
    
    # Prepare the PyQt Application
    app = QApplication([])
    
    # Instantiate the main GUI window
    win = HumanWindow()
        
    # show the window
    win.show()

    # Execute the app -- Kickstart the event loop!
    # app.exec_() will return 0 when successfully completed, and some other
    # error codes when not. This will handed to sys.exit(), which shuts down
    # the python interpreter (and shows the error code, if any).
    sys.exit(app.exec_())


# This file is meant to be run as a script rather than being imported as a module.
# When run as a script, the following lines will be executed, and main() will be called.
if __name__ == '__main__':
    main()
