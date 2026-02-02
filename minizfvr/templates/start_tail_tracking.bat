:: This is a template for a batch file to run minizftt (on Windows)
:: Note that a shortcut to a batch file is needed to run the batch file

color 5e

call "<your anaconda installation location>\miniconda3\Scripts\activate.bat"

call activate minizfvr

python -m minizfvr.minizftt.main

pause
