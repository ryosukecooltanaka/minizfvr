from multiprocessing.connection import Client, Listener
import zmq
from PyQt5.QtCore import QObject, pyqtSignal

class Receiver(QObject):
    """
    This class wraps the named pipe Client (i.e. the receiving end of the pipe)
    We also inherit QObject so it can let the upstream know when connection is lost
    I ended up not cutting out Sender into an object, because I could not figure out
    how objects behave in multiprocess
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


def wait_trigger_from_sidewinder(duration, port: int):
    """
    If the 'wait trigger' is checked, we call this function
    and wait until we get a trigger from a microscope (running sidewinder).
    Once it gets a trigger, we then send back the duration of the stimulus.
    Sidewinder's triggering protocol is written specifically to
    interface with stytra, so this function also inherits redundant
    features from stytra.
    """
    # TODO: implement different triggering protocols per microscope and make it selectable through config

    # first, create a context
    ctx = zmq.Context()

    # next, create a socket
    with ctx.socket(zmq.REP) as socket:
        # configure socket
        socket.setsockopt(zmq.LINGER, 0) # prevent indefinite hanging
        socket.bind("tcp://*:{}".format(port))
        socket.setsockopt(zmq.RCVTIMEO, -1)

        # Now, trigger is first sent by the scope, so we create a poller and wait
        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)
        print('Waiting for a trigger')
        if poller.poll(5000): # wait to see if there is any message with a timeout in milliseconds
            _ = socket.recv_json() # this totally doesn't need to be json, but it is for legacy reason
            print('Received a trigger, sending back the stimulus duration')
            socket.send_json(duration)
            success = True
        else:
            print('Timeout reached. Aborting stimulus initiation')
            success = False
    ctx.term()
    ctx.destroy()
    return success




