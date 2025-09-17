"""

minizfvr app development version 0

2025/09/16 Ryosuke Tanaka

Some key things to get done here
- Make an app with two windows, one for humans to see, the other for fish to see
- Implement frame loading from camera, tail tracking algorithm, some sort of data logging
- Worry about multiprocessing later
- Split things into different files in the end
- some degree of oop is inevitable...

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
        self.camera_panel = CameraPanel()
        self.angle_panel = AnglePanel()
        self.control_panel = ControlPanel()

        # Create vertical box layout. From top, we will show camera image, tail plot, and controls
        # Control box will require layouts of its own, but let's worry about that later
        layout = QVBoxLayout()
        layout.addWidget(self.camera_panel)
        layout.addWidget(self.angle_panel)
        layout.addWidget(self.control_panel)
        container.setLayout(layout)
        
        # show the stimulus window
        self.stimulus_window.show()

        # initialize camera
        self.camera = Camera()
        
        # Define timer for GUI
        self.timer = QTimer()
        self.timer.setInterval(50) # millisecond
        self.timer.timeout.connect(self.fetch_and_show_image) # define callback
        self.timer.start()

    def fetch_and_show_image(self):
        img = self.camera.fetch_image()
        self.camera_panel.set_image(img)
        self.angle_panel.set_data(np.arange(img.shape[1]), np.mean(img, axis=0))

    def closeEvent(self, event):
        """
        This will be called when the main window is closed.
        Release resources for graceful exit.
        """
        self.timer.stop()
        self.stimulus_window.close()
        self.camera.close()
        
        
        
class StimulusWindow(QWidget):
    def __init__(self):
        super().__init__()


class CameraPanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the camera view
    It holds image from camera + tail standard + tracked tail
    """
    def __init__(self):
        super().__init__()
        # This is the "GraphicsItem" that is added to the widget
        self.display_area = pg.ViewBox(invertY=True, lockAspect=True)  # this graphics item implements easy scaling
        self.fish_image_item = pg.ImageItem()
        self.tail_standard = pg.LineSegmentROI([(10, 10), (100, 100)])
        self.tail_standard.setPen(dict(color=(5, 40, 200), width=3))

        # connect everything
        self.addItem(self.display_area)
        self.display_area.addItem(self.fish_image_item)
        self.display_area.addItem(self.tail_standard)

    def set_image(self, image):
        """ Image update method """
        self.fish_image_item.setImage(image)


class AnglePanel(pg.GraphicsLayoutWidget):
    """
    This is the panel (widget) for the tail angle plot
    """
    def __init__(self):
        super().__init__()
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

class Camera():
    def __init__(self):
        self.system = PySpin.System.GetInstance()
        self.camera = self.system.GetCameras()[0]
        self.camera.Init()
        self.camera.BeginAcquisition()

    def fetch_image(self):
        fetched_image = self.camera.GetNextImage()
        if not fetched_image.IsIncomplete():
            converted_image = np.array(fetched_image.GetData(), dtype='uint8').reshape(
                (fetched_image.GetHeight(), fetched_image.GetWidth()))
        fetched_image.Release()
        return converted_image

    def close(self):
        """
        Called from main window close event.
        """
        self.camera.EndAcquisition()
        self.camera.DeInit()
        del self.camera # this is required for system release
        self.system.ReleaseInstance()



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
