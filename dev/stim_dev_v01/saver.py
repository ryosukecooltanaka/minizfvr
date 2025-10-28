import time
import h5py
import os
from pathlib import Path
from PyQt5.QtCore import Qt
from parameters import StimParamObject
from stimulus_generator import stimulusGenerator

# todo: saving datapoint by datapoint is slow -- do chuncked saving

class Saver:
    """
    The saver object will handle saving of tail tracking as well as stimulus data.
    """

    def __init__(self):

        # flag defining whether we should save tail/stim data
        self.save_tail_flag = False
        self.save_stim_flag = False

        # attributes to store file handles for saving
        self.tail_file = None
        self.stim_file = None

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
            self.tail_file = h5py.File(run_path / 'tail_log.h5', 'w')
            self.tail_file.create_dataset('t', (expected_frame_count,), dtype=float)
            self.tail_file.create_dataset('tail_angle', (expected_frame_count,), dtype=float)
            self.tail_index = 0

        ## Prepare stimulus save file
        if self.save_stim_flag:
            # We need to specify the size of the dataset
            # Our actual frame rate would be slightly higher than 60 Hz due to rounding
            expected_frame_count = int(sgen.duration * 65)
            # open a handle for the file
            self.stim_file = h5py.File(run_path / 'stimulus_log.h5', 'w')
            # create dataset corresponding to the stimulus dict (and timestamps)
            self.stim_file.create_dataset('t',  (expected_frame_count, ), dtype=float)
            for var in sgen.variables_to_save:
                self.stim_file.create_dataset(var, (expected_frame_count, ), dtype=type(getattr(sgen, var)))
            self.stim_index = 0

        ## save parameter
        param.save_config_into_json(run_path / 'config.json')

        print('Initialized saving files for {} run {}'.format(fish_name, run_name))

    def finalize(self):
        """
        Called when the stimulus presentation is finished
        """
        if self.save_tail_flag:
            self.shrink_dataset(self.tail_file, self.tail_index)
            self.tail_file.close()
        if self.save_stim_flag:
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
        Save the tail data
        """
        self.tail_file['t'][self.tail_index] = t
        self.tail_file['tail_angle'][self.tail_index] = tail_angle
        self.tail_index += 1

    def save_stim_data(self, t, sgen: stimulusGenerator):
        """
        Save the latest stimulus state
        """
        self.stim_file['t'][self.stim_index] = t
        for var in sgen.variables_to_save:
            self.stim_file[var][self.stim_index] = getattr(sgen, var)
        self.stim_index += 1



