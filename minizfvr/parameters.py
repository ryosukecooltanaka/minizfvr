import json
import os

"""
A parent class for implementing parameter object for both minizftt and minizfstim
implementing loading/saving behaviors
"""

class BaseParams:
    """
    Implement methods to read/write parameters from json
    """
    def load_config_from_json(self, config_path, verbose=False, force=False):
        if os.path.isfile(config_path):
            print('Loading parameters from from ', config_path)
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
                self.read_param_from_dict(config_dict, verbose=verbose, force=force)

    def save_config_into_json(self, config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=4)

    def read_param_from_dict(self, param_dict, verbose=False, force=False):
        for key in param_dict.keys():
            if hasattr(self, key) or force:  # so we don't inject weird attributes
                setattr(self, key, param_dict[key])
                if verbose:
                    print('loaded', key, '=', param_dict[key])
            else:
                if verbose:
                    print(key, 'is not a valid parameter name!')