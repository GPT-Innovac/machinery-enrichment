#!/usr/bin/env python3
"""
Simple script to start the machinery enrichment dashboard
"""
import os
import sys
from pathlib import Path

# Add the web_dashboard directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "web_dashboard"))

# Import and run the Flask app
from app import app

if __name__ == '__main__':
    print("🚀 Starting DACH Machinery Intelligence Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:8080")
    print("🔄 Loading enrichment data...")
    
    try:
        app.run(debug=True, host='127.0.0.1', port=8080, use_reloader=False)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped.")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        print("💡 Make sure you're in the virtual environment and have run the enrichment pipeline first.")
