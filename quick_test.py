#!/usr/bin/env python3
"""Quick test for imports"""

try:
    from landeros_ironware.config import Settings
    print("✅ Settings OK")
except Exception as e:
    print(f"❌ Settings failed: {e}")

try:
    from landeros_ironware.strategies import IronCondorScanner, IronCondorPosition
    print("✅ Strategies OK")
except Exception as e:
    print(f"❌ Strategies failed: {e}")

try:
    from landeros_ironware.risk import PortfolioManager, ProbabilityCalculator
    print("✅ Risk OK")
except Exception as e:
    print(f"❌ Risk failed: {e}")

try:
    from landeros_ironware.visuals import PayoffDiagram
    print("✅ Visuals OK")
except Exception as e:
    print(f"❌ Visuals failed: {e}")

try:
    from dashboard import app
    print("✅ Dashboard OK")
except Exception as e:
    print(f"❌ Dashboard failed: {e}")

print("Test complete!")
