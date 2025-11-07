"""
Landeros Financial Ironware - Desktop App Builder

This script uses PyInstaller to bundle the Dash dashboard (`dashboard.py`)
and the entire `landeros_ironware` engine into a standalone
macOS desktop application (.app).

To run:
    1. Make sure PyInstaller is installed:
       pip install pyinstaller
    2. (Optional) Create an icon file at 'assets/icon.icns'
    3. Run this script from the terminal:
       python3 create_desktop_app.py

This will create a `dist` folder containing `LanderosIronware.app`.
"""

import PyInstaller.__main__
import os
from pathlib import Path

# --- Configuration ---
APP_NAME = "LanderosIronware"
ENTRY_POINT = "dashboard.py"
ICON_FILE = "assets/icon.icns"

# --- Add our entire engine package ---
# This copies the 'landeros_ironware' folder into the app
# Format is 'source:destination'
data_to_add = [
    f"landeros_ironware{os.pathsep}landeros_ironware",
]

# --- Fix hidden imports ---
# PyInstaller can't find these libraries automatically
# because they are loaded dynamically.
hidden_imports = [
    'pandas',
    'numpy',
    'scipy',
    'scipy.stats',
    'plotly',
    'dash',
    'dash_bootstrap_components',
    'yfinance',
    'py-vollib',
    'miaban',
    'statsmodels',
    'sklearn',
    'colorlog',
    'requests',
    'pytz',
    'tables',  # For pandas HDF5
    'pyarrow', # For pandas Parquet
]

# --- Build the PyInstaller command ---
pyinstaller_args = [
    ENTRY_POINT,
    f"--name={APP_NAME}",
    "--onefile",    # Create a single executable file
    "--windowed",   # No terminal window on launch (macOS/Windows)
]

# Add the icon if it exists
if Path(ICON_FILE).exists():
    pyinstaller_args.append(f"--icon={ICON_FILE}")
else:
    print(f"Warning: Icon file not found at {ICON_FILE}. Using default icon.")
    print("For a custom icon, create a .icns file and place it there.")

# Add our package data
for data in data_to_add:
    pyinstaller_args.append(f"--add-data={data}")

# Add all hidden imports
for imp in hidden_imports:
    pyinstaller_args.append(f"--hidden-import={imp}")

# --- Run the Build ---
if __name__ == "__main__":
    print("Starting PyInstaller build...")
    print(f"Command: pyinstaller {' '.join(pyinstaller_args)}")
    
    try:
        PyInstaller.__main__.run(pyinstaller_args)
        print("\n" + "="*50)
        print("✅ BUILD SUCCESSFUL!")
        print(f"Your app is located in: dist/{APP_NAME}.app")
        print("\nYou can now drag this file to your Applications folder.")
        print(f"To run from terminal: open dist/{APP_NAME}.app")
        print("="*50)
    except Exception as e:
        print("\n" + "!"*50)
        print(f"❌ BUILD FAILED: {e}")
        print("Please check the logs above for errors.")
        print("!"*50)
