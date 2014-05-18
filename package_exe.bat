rem Must be run from a bacon venv (bacon on path)
del /s /q dist
del /s /q res
python ..\pyinstaller\pyinstaller.py GoodnightMrPresident.spec