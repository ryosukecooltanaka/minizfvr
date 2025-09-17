from multiprocessing.connection import Listener
from time import time
from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QGraphicsEllipseItem,
    QApplication,
    QMainWindow
)
from PyQt5.QtGui import QBrush, QColor

class ReceiverWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # load pipe path from a config file

        self.listener = Listener(('localhost', 6000))
        self.conn = self.listener.accept()

        # do some window stuff
        self.setWindowTitle("Receiver")  # window title

        self.view = QGraphicsView() # View is a widget
        self.scene = QGraphicsScene(0,0,300,300) # Scene is like the world
        self.ellipse = QGraphicsEllipseItem(0,0,300,300)

        self.data = 0
        self.luminance=0

        # connect things
        self.setCentralWidget(self.view)
        self.view.setScene(self.scene) # Scene is set to a view
        self.scene.addItem(self.ellipse) # Item is added to scene

        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.last_t = time()

    def update(self):
        if self.conn.poll():
            msg = self.conn.recv()
            if isinstance(msg, int):
                self.data = msg

        self.luminance = (self.luminance + 1)%255
        self.ellipse.setBrush(QBrush(QColor.fromHsv(self.data, 255, self.luminance)))

        # time stamp, so it is clear that the two processes are running asynchronously
        new_t = time()
        dt = new_t - self.last_t
        self.last_t = new_t
        self.setWindowTitle("Receiver dt = {0} ms".format(int(dt * 1000)))  # window title

    def closeEvent(self, a0, QCloseEvent=None):
        self.conn.close()
        self.listener.close()

if __name__ == "__main__":
    app = QApplication([])
    win = ReceiverWindow()
    win.show()
    app.exec_()