import numpy as np
from multiprocessing.connection import Client
from time import time
from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
)


class SenderWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        n_attempts = 0
        self.conn = 0
        while n_attempts < 10:
            try:
                self.conn = Client(('localhost', 6000))
                print('Connection established!')
                break
            except:
                # In the real software, connection should be established by clicking the button or something
                print('Connection attempt {0} refused -- make sure you run the listener first'.format(n_attempts))
                n_attempts += 1


        # do some window stuff
        self.setWindowTitle("Receiver")  # window title
        self.setGeometry(50, 50, 200, 100)  # default window position and size (x, y, w, h)

        self.main_label = QLabel()
        self.setCentralWidget(self.main_label)

        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.last_t = time()

    def update(self):
        data = np.random.randint(255)
        self.conn.send(data)
        self.main_label.setText(str(data))

        # time stamp, so it is clear that the two processes are running asynchronously
        new_t = time()
        dt = new_t - self.last_t
        self.last_t = new_t
        self.setWindowTitle("Sender dt = {0} ms".format(int(dt*1000)))  # window title

    def closeEvent(self, a0, QCloseEvent=None):
        if self.conn:
            self.conn.close()



if __name__ == "__main__":
    app = QApplication([])
    win = SenderWindow()
    win.show()
    app.exec_()