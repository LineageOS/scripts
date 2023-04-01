1. Use Python 3.7 or higher
2. Run `pip3 install -r requirements.txt`
3. run `python3 app.py` to generate the full lineage.dependencies mapping
4. run `python3 device2kernel.py` to generate kernel -> devices mapping (like cve_tracker/kernels.json)
5. run `python3 devices.py` to generate device -> dependency mapping (like lineageos_updater/device_deps.json)
