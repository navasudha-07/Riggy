import sys
import os

# Add correct site-packages path for Microsoft Store Python
site_packages = r'C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages'
if site_packages not in sys.path:
    sys.path.insert(0, site_packages)

# Set working directory to script location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Now run main
exec(open("main.py", encoding="utf-8").read())
