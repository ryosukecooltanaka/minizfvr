# minizfvr: minimal virtual reality for zebrafish 
![icon](./minizfvr/assets/icon.svg)

A stab at a portable software for a tail-based 3D VR

The goal is to keep this maximally simple even if it is dumb s.t. 
any motivated individual can read it through and understand 
what is going on under the hood.

## What this is
The package contains two separate applications, `minizftt` and `minizfstim`.

`minizftt` does tail tracking.

`minizfstim` does stimulus presentations.

The two applications talk to each other through named pipes. 
They can be used with other applications, as long as 
you implement compatible communication protocols on the other end.

## Installation
- Create a conda environment using the `environment.yml` file.
  - Note that camera APIs probably need to be separately installed for each manufacturer. 
- Clone the repository to local.
- Install the local repo as an editable (-e) package by running `python -m pip -e <path to repo>`

## Configuration
The both applications will generate config files under the home directory on their 
respective first run (`minizftt_config.json` and `minizfstim_config.json`).
Edit these files to configure correct cameras, video paths etc.

## Quick Start

### minizftt
- Enter the conda environment.
- Running `python -m minizfvr.minizftt.main` will start the app.

### minizfstim
- The `minizfstim` package is not intended to be run as a main script.
- Instead, you are supposed to write a `__main__` python script that defines a custom `StimulusGenerator` and pass that to `StimApp`
- See scripts under `examples` for details (run them like `python -m minizfvr.example.test_stimulus`).
