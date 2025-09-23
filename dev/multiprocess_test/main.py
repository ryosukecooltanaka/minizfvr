import multiprocessing as mp
import time
from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QGraphicsEllipseItem,
    QApplication,
    QMainWindow,
    QPushButton
)
from queue import Empty
from PyQt5.QtGui import QBrush, QColor
import numpy as np

class MPTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        mp.set_start_method('spawn')

        # do some window stuff
        self.setWindowTitle("MP test")  # window title

        self.button = QPushButton('kill')
        self.button.clicked.connect(self.kill_blocking_process)
        self.setCentralWidget(self.button)

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.hello_every_second)
        self.timer.start()

        self.thing = TestClass()
        self.stop_flag = False


        self.q1 = mp.Queue(maxsize=100)
        self.q2 = mp.Queue(maxsize=100)
        self.blocking_process = mp.Process(target=self.thing.hoge, args=(self.q1,))
        print('start while loop')
        self.blocking_process.start()


    def hello_every_second(self):

        messages = []
        while not self.q1.empty():
            try:
                messages.append(self.q1.get(block=False))
            except Empty:
                continue
        print('Hello', messages)

    def kill_blocking_process(self):
        print('kill the while process!')
        self.thing.kill_event.set()
        self.blocking_process.terminate()



class TestClass():
    def __init__(self):
        self.kill_event = mp.Event()

    def hoge(self, q1):
        i = 0
        while not self.kill_event.is_set():
            time.sleep(0.2)
            q1.put(i)
            i+=1
        print('exited the while loop')

if __name__ == "__main__":
    app = QApplication([])
    win = MPTestWindow()
    win.show()
    app.exec_()