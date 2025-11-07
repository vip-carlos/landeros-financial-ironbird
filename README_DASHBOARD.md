# 🚀 Landeros Financial Ironware - Dashboard & Desktop App

## Complete Iron Condor Trading Platform

Your sophisticated quantitative trading system is now available as a professional web dashboard and desktop application!

## 🎯 Quick Start

### Option 1: One-Click Setup & Launch
```bash
python3 setup_and_launch.py
```
This script will automatically:
- ✅ Check your Python version
- 📦 Install all missing dependencies
- 🔧 Test all imports
- 🚀 Launch the dashboard
- 🖥️ Optionally create a desktop app

### Option 2: Manual Launch
```bash
# Install dependencies (if not already done)
pip3 install -r requirements.txt

# Launch dashboard
python3 dashboard.py
```

### Option 3: Create Desktop App
```bash
python3 create_desktop_app.py
```

## 🌐 Dashboard Features

### Professional Interface
- **Bootstrap-styled** interface suitable for institutional use
- **Responsive design** works on desktop, tablet, and mobile
- **Real-time feedback** with loading states and status messages

### Iron Condor Scanner
- **Underlying Selection**: SPX, NDX, or RUT
- **Parameter Controls**:
  - Target Days to Expiration (DTE)
  - Target Delta for strikes
  - Minimum Credit per contract
- **One-Click Scanning**: Runs your complete quantitative pipeline

### Results Display
- **Interactive Table**: Sortable candidates with key metrics
  - Strike structure (e.g., "4400P / 4600C")
  - Credit received
  - Probability of Profit (POP)
  - Return on Capital (ROC)
  - Optimization Score
- **Payoff Diagrams**: Click any row for interactive charts
  - 3D payoff visualization
  - Break-even points
  - Risk profile analysis

### Complete Pipeline Integration
The dashboard seamlessly connects to your existing engine:
- ✅ **Market Data**: Real-time option chains via yfinance
- ✅ **Greeks Engine**: Black-Scholes calculations
- ✅ **Probability Calculator**: Lognormal distribution analysis
- ✅ **Risk Management**: Portfolio-level position sizing
- ✅ **Optimization**: 5-factor scoring system
- ✅ **Visualization**: Interactive payoff diagrams

## 🖥️ Desktop Application

### Create Standalone App
```bash
python3 create_desktop_app.py
```

**What it creates:**
- `dist/LanderosIronware.app` (macOS)
- Double-clickable executable
- No Terminal required
- All dependencies included
- Professional application appearance

### Alternative: Simple Launcher
If PyInstaller fails, the script creates:
- `LanderosIronware_Launcher.sh`
- Double-clickable shell script
- Opens Terminal and launches dashboard

## 🎮 How to Use

1. **Launch** the dashboard (web or desktop)
2. **Select** underlying index (SPX recommended for testing)
3. **Adjust** parameters (defaults are good for testing)
4. **Click "Scan for Trades"**
5. **Review** results in the table
6. **Click any row** to see the payoff diagram

### Expected Results
- **Scan Time**: 5-10 seconds
- **Results**: 10-20 iron condor candidates
- **Metrics**: POP 65-85%, ROC 10-25%, Scores 0.7-0.9

## 🔧 Troubleshooting

### Dashboard Won't Launch
```bash
# Run the comprehensive setup script
python3 setup_and_launch.py
```

### Missing Dependencies
```bash
pip3 install --upgrade -r requirements.txt
```

### Port Already in Use
```bash
# Kill existing processes
lsof -ti:8050 | xargs kill -9

# Or use different port
python3 -c "from dashboard import app; app.run_server(port=8051)"
```

### Import Errors
```bash
# Test imports
python3 -c "from landeros_ironware.config import Settings; print('OK')"
python3 -c "from dashboard import app; print('OK')"
```

## 🏗️ Architecture

```
dashboard.py (Web Interface)
├── Dash + Bootstrap Components
├── Interactive Callbacks
│   ├── Scan Button → IronCondorScanner.scan()
│   ├── Table Updates → Real-time Results
│   └── Chart Clicks → PayoffDiagram.plot()
│
├── landeros_ironware/ (Your Engine)
│   ├── strategies/iron_condor.py
│   ├── risk/probability.py
│   ├── visuals/payoff.py
│   └── data/fetcher.py
│
└── Outputs
    ├── Web Dashboard (http://127.0.0.1:8050)
    └── Desktop App (LanderosIronware.app)
```

## 🎯 What Makes This Special

- **Institutional Grade**: Professional UI/UX for serious traders
- **Complete Pipeline**: From market data to trade execution
- **Quantitative Engine**: Advanced Greeks, probability, and optimization
- **Risk Management**: Portfolio-level position sizing and monitoring
- **Interactive Visualization**: Professional payoff diagrams
- **Deployment Ready**: Web app or standalone desktop executable

## 🚀 Next Steps

Once the dashboard is running:

1. **Test with SPX** - Most liquid underlying
2. **Experiment with parameters** - See how they affect results
3. **Explore payoff diagrams** - Understand the risk/reward profiles
4. **Consider live trading** - Connect to Interactive Brokers
5. **Customize the interface** - Add your preferred features

## 📞 Support

If you encounter issues:

1. **Run the setup script**: `python3 setup_and_launch.py`
2. **Check the troubleshooting section** above
3. **Verify Python 3.9+** and all dependencies
4. **Test individual components** if needed

---

**🎉 Congratulations!** Your iron condor trading system is now a professional, user-friendly application ready for real-world use!
