# minizffs

`minizffs`, a part of minizfvr, is a python-based minimal position tracking app for the larval zebrafish, following the same pattern used for `minizftt`.

`minizffs` is stand-alone, in the sense that it does not include stimulus presentation. 
`minizffs` sends the result of tracking through a named pipe, using `multiprocessing.connection`.
`minizffs` is designed with `minizfstim` in mind, but any other app, custom-written or otherwise, can perform closed loop stimulation in so far as it listens to the named pipe.

`Camera` object uses the one implemented under`minizftt`, which assumes that this whole package is `pip install`-ed -- not sure if this is right?