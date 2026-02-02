# minizfstim
`minizfstim`, a part of `minizfvr`, is a minimal, stand-alone stimulus presentation app capable of closed-loop stimuli (stand-alone in the sense it doesn't include tracking on its own).
It is written `minizftt` in mind.

## Designing your first stimulus with minizfstim
The main thing you need to do is to (1) build your own class inheriting `StimulusGenerator` and (2) pass it to `StimulusApp`.

The key thing you have to implement in your own subclass is the `draw_frame` method, which is expected to return a list containing one (in the bottom projection case) or three (in the panoramic projection case) numpy arrays representing visual stimuli to be projected. The `draw_frame` method will be called at 60 Hz (by default) from the upstream structure, which you usually do not need to worry about.

## To do
- Explain the object hiearchy (maybe visually)
- On `SceneEngine`
- On GUI
