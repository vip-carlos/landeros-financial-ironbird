#!/usr/bin/env python3
"""
Landeros Financial Ironware - Complete Setup & Launch Script

This script will:
1. Check all dependencies
2. Install missing packages
3. Launch the dashboard
4. Handle errors gracefully
5. Provide clear feedback

Usage: python3 setup_and_launch.py
"""

import sys
import subprocess
import importlib
import os
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return success status."""
    try:
        print(f"🔄 {description}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - Success")
            return True
        else:
            print(f"❌ {description} - Failed")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Exception: {e}")
        return False

def check_python_version():
    """Check if Python version is compatible."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Need Python 3.9+")
        return False

def check_and_install_dependencies():
    """Check and install required dependencies."""
    print("\n📦 Checking dependencies...")

    required_packages = [
        'numpy', 'scipy', 'pandas', 'matplotlib', 'seaborn', 'plotly',
        'yfinance', 'requests', 'click', 'rich', 'colorlog', 'tqdm',
        'pydantic', 'pyyaml', 'toml', 'dash', 'dash_bootstrap_components',
        'ib_insync'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            importlib.import_module(package.replace('_', '-'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Missing")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n📥 Installing {len(missing_packages)} missing packages...")
        packages_str = ' '.join(missing_packages)
        cmd = f"{sys.executable} -m pip install {packages_str}"
        return run_command(cmd, f"Installing: {packages_str}")
    else:
        print("\n✅ All dependencies installed!")
        return True

def check_project_imports():
    """Test if our project imports work."""
    print("\n🔧 Testing project imports...")

    try:
        from landeros_ironware.config import Settings
        from landeros_ironware.strategies import IronCondorScanner, IronCondor
        from landeros_ironware.visuals import PayoffDiagram
        print("✅ Project imports successful!")
        return True
    except Exception as e:
        print(f"❌ Project import error: {e}")
        return False

def launch_dashboard():
    """Launch the dashboard."""
    print("\n🚀 Launching Landeros Ironware Dashboard...")

    try:
        from dashboard import app
        print("✅ Dashboard loaded successfully!")
        print("🌐 Opening dashboard at: http://127.0.0.1:8050")
        print("📱 Open your web browser to that URL")
        print("🎯 Dashboard features:")
        print("   • Select underlying (SPX/NDX/RUT)")
        print("   • Set DTE, Delta, Min Credit parameters")
        print("   • Click 'Scan for Trades' to find iron condors")
        print("   • Click table rows for payoff diagrams")
        print("\nPress Ctrl+C to stop the server")

        # Launch the server
        app.run_server(debug=False, port=8050, host='127.0.0.1')

    except Exception as e:
        print(f"❌ Dashboard launch failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_desktop_app():
    """Create a desktop application."""
    print("\n🖥️ Creating desktop application...")

    try:
        # Check if pyinstaller is available
        import PyInstaller
        print("✅ PyInstaller available")
    except ImportError:
        print("❌ PyInstaller not available - installing...")
        if not run_command(f"{sys.executable} -m pip install pyinstaller",
                          "Installing PyInstaller"):
            return False

    # Create the desktop app
    cmd = "pyinstaller --onefile --windowed --name LanderosIronware dashboard.py"
    if run_command(cmd, "Creating desktop app"):
        print("✅ Desktop app created!")
        print("📁 Location: dist/LanderosIronware.app")
        print("🎯 Double-click to launch (no Terminal needed)")
        return True
    else:
        print("❌ Desktop app creation failed")
        return False

def main():
    """Main setup and launch function."""
    print("🚀 Landeros Financial Ironware - Complete Setup & Launch")
    print("=" * 60)

    # Change to project directory
    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)
    print(f"📂 Working directory: {project_dir}")

    # Step 1: Check Python version
    if not check_python_version():
        print("\n❌ Please upgrade to Python 3.9 or later")
        sys.exit(1)

    # Step 2: Check and install dependencies
    if not check_and_install_dependencies():
        print("\n❌ Dependency installation failed")
        print("💡 Try: pip3 install --upgrade pip")
        sys.exit(1)

    # Step 3: Check project imports
    if not check_project_imports():
        print("\n❌ Project import issues")
        print("💡 Make sure you're in the correct directory")
        sys.exit(1)

    # Step 4: Ask user what they want to do
    print("\n" + "=" * 60)
    print("🎯 What would you like to do?")
    print("1. Launch web dashboard")
    print("2. Create desktop app")
    print("3. Do both")
    print("=" * 60)

    while True:
        try:
            choice = input("Enter choice (1-3): ").strip()
            if choice in ['1', '2', '3']:
                break
            else:
                print("Please enter 1, 2, or 3")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)

    success = True

    if choice in ['1', '3']:
        print("\n🌐 Launching web dashboard...")
        try:
            launch_dashboard()
        except KeyboardInterrupt:
            print("\n👋 Dashboard stopped by user")
        except Exception as e:
            print(f"\n❌ Dashboard error: {e}")
            success = False

    if choice in ['2', '3']:
        create_desktop_app()

    if success:
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! Landeros Ironware is ready!")
        print("📊 Your complete iron condor trading system is now operational")
        print("🎯 Features: Market scanning, risk analysis, payoff visualization")
        print("=" * 60)
    else:
        print("\n❌ Some issues occurred - check the output above")

if __name__ == "__main__":
    main()
