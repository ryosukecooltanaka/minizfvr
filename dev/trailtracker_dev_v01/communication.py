from multiprocessing.connection import Client, Listener

"""
To make sure that the sender and receiver share the same protocol,
in the working version of the package, define the sender and receiver in the
same file and import them into tracker/stim app.

"""


class Sender():
    def __init__(self, port=6000):
        self.port = port
        self.listener = Listener(('localhost', self.port))
        self.conn = None

    def initialize_connection(self):
        print('I am the sender object. Now I will attempt to establish a connection')
        connected = False
        try:
            self.conn = self.listener.accept()
            print('connected to listener through localhost port={}'.format(self.port))
            connected = True
        except:
            print('Connection attempt refused -- make sure there is a client')

        return connected

    def send(self, msg):
        if self.conn is not None:
            try:
                self.conn.send(msg)
            except:
                print('connection closed?')


    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.listener.close()

