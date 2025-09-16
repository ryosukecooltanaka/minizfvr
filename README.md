# minizfvr (minimal virtual reality for zebrafish)
A stab at a portable software for a tail-based 3D VR

The strategy is to first figure out all the peripheral processes (interfacing with camera API, tail tracking algorithms etc.), and then learn multiprocessing, finally combining everything into a single GUI with 2 windows (one for captured image, one for stimulus)

The goal is to keep this maximally simple even if it is dumb s.t. any motivated individual can read it through and understand what is going on under the hood 


## Note on environments
Currently things are running with
- `python=3.10.6`
- `numpy=2.0.2`
- `scipy=1.13.1`
- `matplotlib=3.8.4`

But getting things working on jupyter is somehow very finicky. In new kernels it throws AsyncIO related errors and the kernel crashes.
The current working environment was created with `python=3.10.6`, `matplotlib=3.6.0`, `numpy=1.24`, `ipykernel=6.30.1` but AsyncIO didn't stop unitl when I installed `scipy=1.9.1`. It continues to work after updating `numpy`, `scipy`, `matplotlib`, but newly created environments with these packages still fails (some now-unnecessary dependencies are secretly necessary for AsyncIO?).

