# minizftt
`minizftt`, a part of minizfvr, is a python-based minimal tail tracking app for the larval zebrafish.

`minizftt` is stand-alone, in the sense that it does not include stimulus presentation. 
`minizftt` sends the result of tracking through a named pipe, using `multiprocessing.connection`.
`minizftt` is designed with `minizfstim` in mind, but any other app, custom-written or otherwise, can perform closed loop stimulation in so far as it listens to the named pipe.

## multiprocessing
To leverage multi-core CPUs and minimize the lag between frame acquisition and tail tracking, `minizftt` utilizes the `multiprocessing`.
The main GUI application will spawn two child processes: One process would be running frame acquisition with a while loop, and the other would be performing the tail tracking algorithm. 
Several different `multiprocessing` methods are used to pass around information between the processes.
- `shared_memory` is used to pass acquired image frames (from the aquisition process to the tracking processes) as well as tracking results (from the tracking process to the main process for visualization).
- `Queue` is used to pass parameters from the main process to the tracking process, as well as to pass timestamps from the acquisition to the tracking process (which tells the latter when a new image is registered to `shared_memory`).
- `Event` is used many times to raise a flag in one process and read it in another.
- `connection` is used to send out the tracking results to other apps, as already mentioned above.

## Camera API installation guide
Python APIs for cameras require you to download SDKs from manufacturer websites, and manually installing the package (i.e., you cannot install them easily with `conda` or `pip`).
Note that the camera type will be loaded from `minizftt_config.json` automatically created under the home directory.

### FLIR (PointGrey) cameras
1. Install Spinnaker SDK from the Teledyne website (choose the application development option). SpinView GUI app is bundled here, where you can change camera acquisition parameters, such as frame rate, exposure, and ROI. (registration required)
2. Download PySpin matching the python version (minizfvr is written with python 3.10) from the same download page at Teledyne.
3. Unzip the downloaded file, go there on your conda prompt inside the appropriate environment, and run `pip install spinnaker_<...>_.whl`.
