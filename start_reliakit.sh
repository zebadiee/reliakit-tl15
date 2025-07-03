#!/bin/bash

# start_reliakit.sh
# This script orchestrates the launch of ReliaKit components:
# 1. Seeds the memory database (if not already seeded)
# 2. Starts the background autonomous reflection loop (tk_meta_loop.py)
# 3. Launches the Flask web dashboard (reliakit_web_dashboard.py)
# 4. Launches the main Tkinter GUI (gui_launcher.py)

# Set PYTHONPATH to include the ReliaKit directory and its subdirectories
# This allows Python to find modules like 'reliakit.codex_base_ui'
export PYTHONPATH=/Users/dadhoosband/Desktop/ReliaKit:$PYTHONPATH

echo "🚀 Starting ReliaKit Autonomous Evolution System..."

# --- 1. Initialize and Seed Memory Database ---
echo "🌱 Initializing and seeding memory database..."
# Run init_memory_db.py which ensures table creation and calls seed_database
# This script is at the ReliaKit/ root level.
python3 init_memory_db.py
echo "✅ Database initialization and seeding complete."

# --- 2. Start Autonomous Reflection Loop (tk_meta_loop.py) ---
# This script is assumed to handle auto-reflection, agent triggering, etc.
# Run in background using '&'
echo "🔄 Starting autonomous reflection loop..."
# tk_meta_loop.py is located in the reliakit/ subdirectory
nohup python3 reliakit/tk_meta_loop.py --auto > reliakit_meta_loop.log 2>&1 &
TK_META_LOOP_PID=$!
echo "✅ Autonomous reflection loop started (PID: $TK_META_LOOP_PID)."

# --- 3. Launch Flask Web Dashboard ---
echo "🌐 Starting Flask Web Dashboard..."
# reliakit_web_dashboard.py is located in the reliakit/ subdirectory
# Using port 5001 to avoid conflict with Control Center.
nohup python3 reliakit/reliakit_web_dashboard.py > reliakit_web_dashboard.log 2>&1 &
FLASK_PID=$!
echo "✅ Flask Web Dashboard started on http://127.0.0.1:5001 (PID: $FLASK_PID)"
echo "   Access it from your LAN by replacing 127.0.0.1 with your machine's IP address and using port 5001."
echo "   If running via Docker, it will be accessible on the mapped port (e.g., http://localhost:5001)."


# --- 4. Launch GUI ---
echo "🖥️ Launching ReliaKit GUI..."
# gui_launcher.py is located at the ReliaKit/ root level
# The GUI should be launched last, as it's the primary interactive component.
# It will keep the terminal busy until closed.
python3 gui_launcher.py

echo "ReliaKit GUI closed."

# --- Cleanup background processes on GUI exit ---
echo "Killing background processes..."
# Check if PIDs exist before killing
if [ -n "$TK_META_LOOP_PID" ] && kill -0 "$TK_META_LOOP_PID" 2>/dev/null; then
    kill "$TK_META_LOOP_PID"
fi
if [ -n "$FLASK_PID" ] && kill -0 "$FLASK_PID" 2>/dev/null; then
    kill "$FLASK_PID"
fi
echo "🛑 ReliaKit system shut down."