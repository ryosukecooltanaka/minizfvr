# minizfvr (minimal virtual reality for zebrafish)
A stab at a portable software for a tail-based 3D VR

The strategy is to first figure out all the peripheral processes (interfacing with camera API, tail tracking algorithms etc.), and then learn multiprocessing, finally combining everything into a single GUI with 2 windows (one for captured image, one for stimulus)

The goal is to keep this maximally simple even if it is dumb s.t. any motivated individual can read it through and understand what is going on under the hood 
