import time
import numpy as np
import h5py
import os
from pathlib import Path
from PyQt5.QtCore import Qt
from parameters import StimParamObject
from stimulus_generator import stimulusGenerator
from utils import sync_buffer_to_file

# todo: saving datapoint by datapoint is slow -- do chuncked saving

class Saver:
    """
    The saver object will handle saving of tail tracking as well as stimulus data.
    """

    def __init__(self, buffer_size=100):

        # flag defining whether we should save tail/stim data
        self.save_tail_flag = False
        self.save_stim_flag = False

        # attributes to store file handles for saving
        self.tail_file = None
        self.stim_file = None

        # attributes to store buffer (we buffer incoming stream of data into lists, and save only once in a while
        # because saving every loop is probably slow
        self.buffer_size = buffer_size
        self.tail_buffer = {} # dict of arrays
        self.stim_buffer = {}

        # indices for saving
        self.tail_index = 0
        self.stim_index = 0

    def toggle_states(self, new_state, is_tail: bool):
        """
        Save state checkbox callback. checkStateChanged() signal returns tri-state enum arguments (0 for unchecked,
        1 for partially checked, 2 for checked (which is equal to Qt.Checked). Also takes the second argument
        specifying which flag to change, as it is stupid to implement a separate method for this.
        """
        if is_tail:
            self.save_tail_flag = (new_state == Qt.Checked)
        else:
            self.save_stim_flag = (new_state == Qt.Checked)

    def initialize(self, param: StimParamObject, sgen: stimulusGenerator):
        """
        This will be called every time you start stimulus
        If necessary, create a directory for this fish, create a directory for this run,
        open h5 files for tail and stimulus
        """

        ## Skip the whole thing if we are not saving anything
        if (not self.save_tail_flag) and (not self.save_stim_flag):
            return

        ## Check if directories exist, and if not, make them
        base_path = Path(param.save_path)

        fish_name = time.strftime('%y%m%d_f{:03}').format(param.animal_id)
        run_name = time.strftime('%Y%m%d_%H%M%S')

        fish_path = base_path / fish_name
        run_path = fish_path / run_name

        for p in (fish_path, run_path):
            if not p.exists():
                p.mkdir()

        ## Prepare tail save file
        if self.save_tail_flag:
            # we expect this to be at most 300 Hz
            expected_frame_count = int(sgen.duration * 300)
            # open h5 file (file works like a dict)
            self.tail_file = h5py.File(run_path / 'tail_log.h5', 'w')
            # create dataset (works like a numpy array)
            self.tail_file.create_dataset('t', (expected_frame_count,), dtype=float)
            self.tail_file.create_dataset('tail_angle', (expected_frame_count,), dtype=float)
            # we buffer data into a dictionary of arrays, so that we reduce the overhead for writing
            self.tail_buffer['t'] =  np.zeros(self.buffer_size, dtype=float)
            self.tail_buffer['tail_angle'] = np.zeros(self.buffer_size, dtype=float)
            self.tail_index = 0

        ## Prepare stimulus save file
        if self.save_stim_flag:
            # We need to specify the size of the dataset
            # Our actual frame rate would be slightly higher than 60 Hz due to rounding
            expected_frame_count = int(sgen.duration * 65)
            # open a handle for the file
            self.stim_file = h5py.File(run_path / 'stimulus_log.h5', 'w')
            # create dataset corresponding to what we want to save
            self.stim_file.create_dataset('t',  (expected_frame_count, ), dtype=float)
            # We expect stimulus generator to be storing the names of attributes to be logged as a list of str
            # and we look at this list to create datasets appropriately
            for var in sgen.variables_to_save:
                self.stim_file.create_dataset(var, (expected_frame_count, ), dtype=type(getattr(sgen, var)))
            # We create corresponding memory buffers (incl. t)
            for var in self.stim_file.keys():
                self.stim_buffer[var] = np.zeros(self.buffer_size, dtype=self.stim_file[var].dtype)
            self.stim_index = 0

        ## save parameter
        param.save_config_into_json(run_path / 'config.json')

        print('Initialized saving files for {} run {}'.format(fish_name, run_name))

    def finalize(self):
        """
        Called when the stimulus presentation is finished
        Save the remaining content of the buffers into the files, adjust the length of the dataset, and close the files
        """
        if self.save_tail_flag:
            # save the remaining buffer content
            sync_buffer_to_file(self.tail_file, self.tail_buffer, self.tail_index, self.buffer_size)
            self.shrink_dataset(self.tail_file, self.tail_index)
            self.tail_file.close()

        if self.save_stim_flag:
            # save the remaining buffer content
            sync_buffer_to_file(self.stim_file, self.stim_buffer, self.stim_index, self.buffer_size)
            self.shrink_dataset(self.stim_file, self.stim_index)
            self.stim_file.close()

    def shrink_dataset(self, file_handle, desired_length):
        """
        We do not know the exact data length beforehand, so dataset is longer than necessary
        This method will curtail the dataset to the desired number
        This assumes that the dataset in a single file is always 1D array sampled at the same frequency
        """
        keys = file_handle.keys()
        for key in keys:
            data = file_handle[key][:]
            del file_handle[key]
            file_handle.create_dataset(key, (desired_length, ), data=data[:desired_length])

    def save_tail_data(self, t, tail_angle):
        """
        Load the tail data into the buffer, and save if necessary
        """

        self.tail_buffer['t'][self.tail_index % self.buffer_size] = t
        self.tail_buffer['tail_angle'][self.tail_index% self.buffer_size] = tail_angle

        # increment the index
        self.tail_index += 1

        # if we just filled the buffer to the brim, move that to the file
        if (self.tail_index % self.buffer_size)==0:
            sync_buffer_to_file(self.tail_file, self.tail_buffer, self.tail_index, self.buffer_size)

    def save_stim_data(self, t, sgen: stimulusGenerator):
        """
        Load the latest stimulus state into the buffer, and save if necessary
        """
        self.stim_buffer['t'][self.stim_index % self.buffer_size] = t
        for var in sgen.variables_to_save:
            self.stim_buffer[var][self.stim_index % self.buffer_size] = getattr(sgen, var)

        # increment the index
        self.stim_index += 1

        # if we just filled the buffer to the brim, move that to the file
        if (self.stim_index % self.buffer_size) == 0:
            sync_buffer_to_file(self.stim_file, self.stim_buffer, self.stim_index, self.buffer_size)



