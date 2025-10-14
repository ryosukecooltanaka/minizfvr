import numpy as np
import sys
import time

from PyQt5.QtCore import QTimer, QRect, QPoint
from PyQt5.QtGui import QPainter, QBrush, QPen, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel
)

from qimage2ndarray import array2qimage
from parameters import StimParamObject
from panels import StimulusControlPanel

class StimulusApp:
    """
    In each script specifying the experiment, we import this app object, and hand a stimulus generator object
    The constructor of this object will kickstart the GUI
    """
    def __init__(self, stimulus_generator, is_panorama=False):
        app = QApplication([])
        # Instantiate the main GUI window
        # You need to pass a stimulus generator object, which should have an update method that returns bitmap
        # to be painted.
        win = StimulusControlWindow(stimulus_generator, is_panorama)
        # show the window
        win.show()
        # start the application (exit the interpreter once the app closes)
        sys.exit(app.exec_())


class StimulusControlWindow(QMainWindow):
    """
    Things to implement
    - start/stop push button
    - check box / line edit to specify if/where to save things
    - push button to establish connection with the tail tracker
    - rect specification and calibration


    - potentially some plots for debugging purpose? (optional)
    - parameters -- probably no need to dynamically update this?
    """

    def __init__(self, stimulus_generator, is_panorama):
        """
        The main window constructor. Called once at the beginning.
        """

        # Call the parental (QMainWindow) constructor
        super().__init__()
        self.setWindowTitle('Stimulus Control')
        self.setGeometry(100, 100, 200, 400)

        # Stimulus generator object
        # This should have a 'update' method, which takes timestamp, tail info, calibration parameters as inputs
        # and return bitmap (ndarray) as an output. Otherwise it can be anything
        self.stimulus_generator = stimulus_generator

        # Create a parameter object & load config
        self.param = StimParamObject(self) # this is a hybrid of a dataclass and QObject -- it can emit signals
        self.param.load_config_from_json()
        self.param.is_panorama = is_panorama

        # create a stimulus window, pass null parent, and parameter reference
        self.stimulus_window = StimulusWindow(None, param=self.param)
        self.stimulus_window.show()

        # make sure the stimulus window paint area is updated appropriately as we change parameters
        self.param.paramChanged.connect(self.stimulus_window.repaint)

        # prepare UI panels
        self.ui = StimulusControlPanel(self.param) # pass reference to parameters
        self.setCentralWidget(self.ui)

        # define ui callback
        self.ui.start_button.clicked.connect(self.toggle_run_state)
        self.ui.reset_button.clicked.connect(self.reset_stimulus)

        # stimulus update timer
        self.timer = QTimer()
        self.timer.setInterval(1000 // 60) # aim 60 Hz
        self.timer.timeout.connect(self.stimulus_update)

        # flags and timestamps
        self.stimulus_running = False
        self.t0 = 0

    def toggle_run_state(self):
        if not self.stimulus_running:
            self.stimulus_running = True
            self.timer.start()
            self.t0 = time.time()
            self.ui.start_button.setText('Stop')
        else:
            self.stimulus_running = False
            self.timer.stop()
            self.ui.start_button.setText('Start')

    def reset_stimulus(self):
        self.stimulus_window.show()

    def stimulus_update(self):
        """
        Called every timer update
        """
        # get current time stamp
        t = time.time() - self.t0

        # give the time stamp to the stimulus generator object, get the frame bitmap
        stim_frame = self.stimulus_generator.update(t)

        # if the shape of the bitmap has changed, we call parameter refresh, in case if we need to change the rect
        if (self.param.bitmap_h, self.param.bitmap_w) != stim_frame.shape[:2]: # can be 3d!
            self.param.bitmap_h, self.param.bitmap_w = stim_frame.shape[:2]
            self.ui.calibration_panel.refresh_param()

        # pass the frame bitmap to the StimulusWindow, and paint
        self.stimulus_window.receive_and_paint_new_frame(stim_frame)

    def closeEvent(self, event):
        self.stimulus_window.close()
        self.param.save_config_into_json()


class StimulusWindow(QWidget):
    """
    The second window on which we present stimuli to be viewed by the animals
    """
    def __init__(self, *args, param, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Stimulus Window')
        self.setGeometry(500, 500, 500, 500)
        self.setStyleSheet("background-color: black;")

        # todo: get rid of the title bar and implement sneaky minimize/maximize buttons (lower priority)
        # https://www.pythonguis.com/tutorials/custom-title-bar-pyqt6/
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # prepare attributes to store painting area rects
        self.rect = None # for single window
        self.prect = None # for panorama
        self.param = param # reference to parent parameters (= it is synchronized -- we are not copying anything)

        # ndarray of stimulus
        self.frame = None

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


        if self.frame is not None:
            qp.setBrush(QColor(*np.random.randint(0,255,3).astype(int)))
            qp.drawImage(QRect(self.param.x, self.param.y, self.param.w, self.param.h),
                         array2qimage(self.frame))
        qp.end()

    def receive_and_paint_new_frame(self, frame):
        """
        This is called from upstream every time new stimulus frame is generated
        Receives a frame bitmap and paint it
        """
        self.frame = frame
        self.repaint()

