# Using a named pipe to solve inter-process communication
The difficult thing about video-based closed loop experiment is that the camera acquisition is running at a different rate as the stimulus generation.
Stytra handles this by spawning asynchronous processes using python's `multiprocessing` module, specifically using queues.
I don't really know how to do this (or how exactly this is done in stytra) -- let's face it: if I did, I would have a higher paying software engineering job.
[The alternative solution I found](https://stackoverflow.com/questions/6920858/interprocess-communication-in-python?rq=1) uses Client/Listener functions in the `multiprocessing` module.
This is nice, because I can just make separate applications for tail tracking and stimulus presentation. The tail tracking GUI can simply keep sending tail data to a localhost port, and the other side can just listen to the port and do its own thing. This makes things very modular, as the tail tracking side does not constrain the stimulus presentation side at all.

## What's in here
To understand how Client/Listener work, I created the bare minimum PyQt GUI. The sender keeps generating random integer between 0 and 255 at 2 Hz, and send it to the pipe.
The receiver gets this number from the pipe, and changes the color of the circle on the GUI. To demonstrate that the receiver is running much faster, the luminance of the circle is updated at 100 Hz. 