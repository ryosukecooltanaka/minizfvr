from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import h5py
import time
import numpy as np
from .fsutils import solve_fish_correspondence

class Saver(QObject):
    """
    A minimal saver object to allow stand-alone saving of
    free swimming tracking data. Whne you click the save button,
    we create a h5 file (or maybe even csv) under the default
    folder (like the same place as the config file) until you click
    the stop.
    """

    saveStateChanged = pyqtSignal(bool)

    def __init__(self, data_array, timestamp_buffer, index_buffer, param):
        super().__init__()

        self.saving = False
        self.infinite_mode = False

        self.temp_file = ''

        # Handle to the shared memory array
        self.data_array = data_array # 3 x N array for x, y, theta, and timestamp
        self.timestamp_buffer = timestamp_buffer # N float64
        self.index_buffer = index_buffer # N array for data index (int32)

        # copy of the parent parameter object (mostly for reading the log path)
        self.param = param

        # timestamp and index of the first datapoint to be saved
        self.i0 : np.int32 = 0
        self.t0 = 0

        self.i_last_saved: np.int32 = 0
        self.n_frame_saved = 0

        # we save every second or so
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.save_data)  # define callback

    def toggle_save_state(self, new_state):
        if new_state:
            # create file, prepare dataset
            print('[Saver] Start saving...')
            self.saveStateChanged.emit(True)
            self.initialize_saving()
        else:
            # close handle, shrink dataset
            print('[Saver] Finished saving...')
            self.saveStateChanged.emit(False)
            self.finalize_saving()

    def initialize_saving(self):
        """
        Called when starting the save
        Prepare a h5 file under the log directory, create dataset
        """

        self.save_file_name = time.strftime('minizffs_log_%Y%m%d_%H%M%S.h5')
        self.temp_file_path = Path(self.param.log_path) / 'minizffs_log_tempfile.h5'

        # due to the reshaping requirement, this is just a temp file
        self.temp_file = h5py.File(self.temp_file_path, 'w')
        self.infinite_mode = (self.param.save_duration<=0)

        # x, y, theta is for each fish, t is for everyone
        ops_dict = dict(shape=(0,), maxshape=(None,), dtype=np.float64,  chunks=True)
        for dname in ('x', 'y', 'theta', 't'):
            self.temp_file.create_dataset(dname, **ops_dict)
        self.temp_file.create_dataset('mm_per_px', data=(self.param.mm_per_px,))
        
        self.t0 = max(self.timestamp_buffer)
        self.i0 = max(self.index_buffer)
        self.i_last_saved = self.i0.copy()
        self.timer.start()

    def finalize_saving(self):
        self.timer.stop()

        # close temp file
        self.temp_file.close()
        
        print('[Saver] Reshaping the content of the saved temp file...')
        # re-open temp file in a read mode, and copy the data into memory
        with h5py.File(self.temp_file_path, 'r') as f:
            x = f['x'][:]
            y = f['y'][:]
            theta = f['theta'][:]
            t = f['t'][:]
        
        # We want to reshape our data into 2d array (de-multiplex time and fish)
        # But we might have started and ended the saving in the middle of the frame
        # So we cut these sticking-out bits off before reshaping
        n_sample_saved = len(x)
        n_ignore_at_start = np.sum(t[:self.param.n_fish_to_track]==t[0])
        n_ignore_at_end = np.sum(t[-self.param.n_fish_to_track:]==t[-1])
        # This should cleanly divide
        n_frame = (n_sample_saved - n_ignore_at_start - n_ignore_at_start) // self.param.n_fish_to_track
        # Finally reshaping
        to_save = slice(n_ignore_at_start, -n_ignore_at_end)
        x = np.reshape(x[to_save], (n_frame, self.param.n_fish_to_track))
        y = np.reshape(y[to_save], (n_frame, self.param.n_fish_to_track))
        theta = np.reshape(theta[to_save], (n_frame, self.param.n_fish_to_track))
        t = t[n_ignore_at_start:-n_ignore_at_end:self.param.n_fish_to_track]

        # maybe do this?
        x, y, theta = solve_fish_correspondence(x,y,theta,t)

        # Save everything in the real save file
        with h5py.File(Path(self.param.log_path) / self.save_file_name, 'w') as f:
            f.create_dataset('x', data=x)
            f.create_dataset('y', data=y)
            f.create_dataset('theta', data=theta)
            f.create_dataset('t', data=t)

    def save_data(self):
        # Continuously save data (timer callback)
        # My strategy here is to just forget about multi-fish thing and
        # save everything as 1d arrray, and then when finalizing the save
        # reshape it into 2d because it is painful to deal with waiting 
        # for all fish data to come in at each call etc.

        # first, roll data (oldest to newest)
        head_index = np.argmax(self.index_buffer) # position of the latest index in the buffer
        latest_frame_index = max(self.index_buffer) # it is important I declare this here because this can change due to mp
        rolled_data = np.roll(self.data_array, -head_index-1, axis=1)
        rolled_timestamp = np.roll(self.timestamp_buffer, -head_index-1)
        to_be_saved = np.roll(self.index_buffer, -head_index-1) > self.i_last_saved
        
        # expand the dataset according up to the current data size
        for dname in ('x', 'y', 'theta', 't'):
            self.temp_file[dname].resize((latest_frame_index-self.i0, ))
        
        save_range = slice(self.i_last_saved-self.i0, latest_frame_index-self.i0)
        self.temp_file['x'][save_range] = rolled_data[0, to_be_saved] * self.param.mm_per_px
        self.temp_file['y'][save_range] = rolled_data[1, to_be_saved] * self.param.mm_per_px
        self.temp_file['theta'][save_range] = rolled_data[2, to_be_saved]
        self.temp_file['t'][save_range] = rolled_timestamp[to_be_saved] - self.t0

        self.i_last_saved = latest_frame_index # counting from app start, counting fish individually

        if not self.infinite_mode and (max(self.timestamp_buffer)-self.t0) > self.param.save_duration:
            self.toggle_save_state(False)


                