from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import h5py
import time
import numpy as np

class Saver(QObject):
    """
    A minimal saver object to allow stand-alone saving of
    free swimming tracking data. Whne you click the save button,
    we create a h5 file (or maybe even csv) under the default
    folder (like the same place as the config file) until you click
    the stop.
    """
    def __init__(self, data_array, index_buffer, param):
        super().__init__()

        self.saving = False
        self.infinite_mode = False

        self.save_file = ''

        # Handle to the shared memory array
        self.data_array = data_array # 4 x N array for x, y, theta, and timestamp
        self.index_buffer = index_buffer # N array for data index (uint32)

        # copy of the parent parameter object (mostly for reading the log path)
        self.param = param

        # timestamp and index of the first datapoint to be saved
        self.i0 : np.uint32 = 0
        self.t0 = 0

        self.i_last_saved: np.uint32 = 0

        # we save every second or so
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.save_data)  # define callback

    def toggle_save_state(self, new_state):
        print('new saving state = ', new_state)
        if new_state:
            # create file, prepare dataset
            self.initialize_saving()
        else:
            # close handle, shrink dataset
            self.finalize_saving()

    def initialize_saving(self):
        """
        Called when starting the save
        Prepare a h5 file under the log directory, create dataset
        """

        file_name = time.strftime('minizffs_log_%Y%m%d_%H%M%S.h5')
        save_path = Path(self.param.log_path) / file_name

        self.save_file = h5py.File(save_path, 'w')
        self.infinite_mode = (self.param.save_duration<=0)

        ops_dict = dict(shape=(0,), maxshape=(None,), dtype=np.float64,  chunks=True)
        for dname in ('x', 'y', 'theta', 't'):
            self.save_file.create_dataset(dname, **ops_dict)
        
        self.t0 = max(self.data_array[3, :])
        self.i0 = max(self.index_buffer)
        self.i_last_saved = self.i0.copy()
        self.timer.start()
            

    def finalize_saving(self):
        self.timer.stop()
        self.save_file.close()
        pass

    def save_data(self):
        # continuously save data (timer callback)
        
        # first, roll data (oldest to newest)
        head_index = np.argmax(self.index_buffer) # position of the latest index in the buffer
        latest_frame_index = max(self.index_buffer) # the content of buffer changes online so I declare this here
        rolled_data = np.roll(self.data_array, -head_index-1, axis=1)
        to_be_saved = np.roll(self.index_buffer, -head_index-1) > self.i_last_saved

        print(np.sum(to_be_saved), self.i_last_saved, latest_frame_index)

        for dname in ('x', 'y', 'theta', 't'):
            self.save_file[dname].resize((latest_frame_index-self.i0,))
        save_range = slice(self.i_last_saved-self.i0, latest_frame_index-self.i0)
        self.save_file['x'][save_range] = rolled_data[0, to_be_saved]
        self.save_file['y'][save_range] = rolled_data[1, to_be_saved]
        self.save_file['theta'][save_range] = rolled_data[2, to_be_saved]
        self.save_file['t'][save_range] = rolled_data[3, to_be_saved] - self.t0
        
        self.i_last_saved = latest_frame_index

        if not self.infinite_mode and (max(self.data_array[3, :])-self.t0) > self.param.save_duration:
            self.toggle_save_state(False)


                