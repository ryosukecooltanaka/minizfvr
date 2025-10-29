from multiprocessing.connection import Client, Listener
from PyQt5.QtCore import QObject, pyqtSignal

"""
To make sure that the sender and receiver share the same protocol,
in the working version of the package, define the sender and receiver in the
same file and import them into tracker/stim app.

"""

class Receiver(QObject):
    """
    This class wraps the named pipe Client (i.e. the receiving end of the pipe)
    We also inherit QObject so it can let the upstream know when connection is lost
    """

    connectionStateChanged = pyqtSignal(bool) # True for connection opened, false for lost

    def __init__(self, port=6000):
        super().__init__()
        self.port = port
        self.conn = None
        self.connected = False

    def open_connection(self):
        """
        To open a client connected to the port needs to be first opened from the sender side.
        We call this method at the start-up once, and also from the connect button
        """
        if not self.connected:
            try:
                self.conn = Client(('localhost', self.port))
                print('Client opened at localhost port', self.port)
                self.connected = True
                self.connectionStateChanged.emit(True)

            except ConnectionRefusedError:
                print('Connection refused at localhost port ',self.port, 'Make sure to open the port by setting up a listener first')
                self.connected = False

    def read_data(self):
        """
        If there is any data, flush everything, return as a list
        """
        if self.connected:
            try:
                if self.conn.poll():
                    msg = []
                    while self.conn.poll():
                        msg.append(self.conn.recv())
                    return msg
                else:
                    return
            except (EOFError, ConnectionError) as e:
                print('[Receiver] Connection lost!')
                self.connected = False
                self.connectionStateChanged.emit(False)

        else:
            return

    def close(self):
        self.connected = False
        if self.conn is not None:
            self.conn.close()

