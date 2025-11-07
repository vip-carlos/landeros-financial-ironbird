#!/usr/bin/env python3
"""
Quick test to verify imports work after fixing circular import issue.
"""

def test_imports():
    print("🔍 Testing Landeros Ironware imports...")

    try:
        print("Testing Settings...")
        from landeros_ironware.config import Settings
        print("✅ Settings OK")

        print("Testing IronCondorScanner...")
        from landeros_ironware.strategies import IronCondorScanner
        print("✅ IronCondorScanner OK")

        print("Testing IronCondorPosition...")
        from landeros_ironware.strategies.iron_condor import IronCondorPosition
        print("✅ IronCondorPosition OK")

        print("Testing PortfolioManager...")
        from landeros_ironware.risk import PortfolioManager
        print("✅ PortfolioManager OK")

        print("Testing ProbabilityCalculator...")
        from landeros_ironware.risk import ProbabilityCalculator
        print("✅ ProbabilityCalculator OK")

        print("Testing PayoffDiagram...")
        from landeros_ironware.visuals import PayoffDiagram
        print("✅ PayoffDiagram OK")

        print("\n🎉 ALL IMPORTS SUCCESSFUL!")
        print("🚀 Ready to launch dashboard!")

        return True

    except Exception as e:
        print(f"\n❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n💡 Next: Run 'python3 dashboard.py' to launch the dashboard!")
    else:
        print("\n🔧 Check the error above and fix any remaining issues.")
