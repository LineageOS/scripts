1. Use Python 3.2 or higher
2. Run `pip3 install -r requirements.txt`
3. Grab a new token from [here](https://github.com/settings/tokens) - no scopes needed, just a name. Put it in `token`
4. run `python3 app.py` to generate the full lineage.dependencies mapping
5. run `python3 device2kernel.py` to generate kernel -> devices mapping (like cve_tracker/kernels.json)
6. run `python3 devices.py` to generate device -> dependency mapping (like lineageos_updater/device_deps.json)
