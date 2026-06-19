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
    def __init__(self, data_array, timestamp_buffer, index_buffer, param):
        super().__init__()

        self.saving = False
        self.infinite_mode = False

        self.save_file = ''

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
            self.initialize_saving()
        else:
            # close handle, shrink dataset
            print('[Saver] Finished saving...')
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

        # x, y, theta is for each fish, t is for everyone
        ops_dict = dict(shape=(0,0), maxshape=(None,None), dtype=np.float64,  chunks=True)
        for dname in ('x', 'y', 'theta'):
            self.save_file.create_dataset(dname, **ops_dict)
        self.save_file.create_dataset('t', shape=(0,), maxshape=(None,), dtype=np.float64,  chunks=True)
        self.save_file.create_dataset('mm_per_px', data=(self.param.mm_per_px,))
        

        # wait until tracking of the all fish is completed
        while not (max(self.index_buffer)%self.param.n_fish_to_track)==0:
            pass

        self.t0 = max(self.timestamp_buffer)
        self.i0 = max(self.index_buffer)
        self.i_last_saved = self.i0.copy()
        self.n_frame_saved = 0
        self.timer.start()
            

    def finalize_saving(self):
        self.timer.stop()
        self.save_file.close()
        pass

    def save_data(self):
        # continuously save data (timer callback)

        # wait until tracking of all fish is completed
        # because I don't want to deal with staggered data
        while True:
            latest_frame_index = max(self.index_buffer) # this is counted from the app start
            if latest_frame_index % self.param.n_fish_to_track == 0:
                break
        
    
        ## TO DO 
        # Because it is painful to deal with reshaping online
        # Save everything in 1D and reshape it when finalizing
        

        # first, roll data (oldest to newest)
        head_index = np.argmax(self.index_buffer) # position of the latest index in the buffer
        rolled_data = np.roll(self.data_array, -head_index-1, axis=1)
        rolled_timestamp = np.roll(self.timestamp_buffer, -head_index-1)
        to_be_saved = np.roll(self.index_buffer, -head_index-1) > self.i_last_saved

        

        # recalculate sizes
        n_sample_latest = latest_frame_index - self.i0
        n_frame_latest = n_sample_latest // self.param.n_fish_to_track # this should divide cleanly

        print(head_index, n_sample_latest, n_frame_latest)

        for dname in ('x', 'y', 'theta'):
            self.save_file[dname].resize((n_frame_latest,self.param.n_fish_to_track))
        self.save_file['t'].resize((n_frame_latest,))
        
        save_range = slice(self.n_frame_saved, n_frame_latest)
        n_frame_to_be_saved = n_frame_latest - self.n_frame_saved
        data_shape = (n_frame_to_be_saved, self.param.n_fish_to_track)

        self.save_file['x'][save_range, :] = np.reshape(rolled_data[0, to_be_saved], data_shape) * self.param.mm_per_px
        self.save_file['y'][save_range, :] = np.reshape(rolled_data[1, to_be_saved], data_shape) * self.param.mm_per_px
        self.save_file['theta'][save_range, :] = np.reshape(rolled_data[2, to_be_saved], data_shape)

        # timestamp
        self.save_file['t'][save_range] = rolled_timestamp[-n_frame_to_be_saved*self.param.n_fish_to_track::self.param.n_fish_to_track] - self.t0
        
        self.n_frame_saved = n_frame_latest # counting from recording start, divided by fish number
        self.i_last_saved = latest_frame_index # counting from app start, counting fish individually

        if not self.infinite_mode and (max(self.timestamp_buffer)-self.t0) > self.param.save_duration:
            self.toggle_save_state(False)


                