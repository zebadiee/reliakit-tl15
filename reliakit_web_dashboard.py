import os
from flask import Flask, render_template_string, jsonify
from pathlib import Path
import sqlite3
from datetime import datetime
import json # For handling potential JSON data in memory entries

app = Flask(__name__)

# Determine the base directory for the project.
# This assumes the script is run from a location where its parent
# is the 'reliakit' directory, and 'utils' is a sibling.
# Adjust if the directory structure is different.
# Path(__file__).resolve() gives the absolute path to the current file.
# .parent gives the directory containing the current file (e.g., 'reliakit').
base_dir = Path(__file__).resolve().parent.parent # Assuming reliakit_web_dashboard.py is in reliakit/

# Construct the path to the database
DB_PATH = base_dir / "utils" / "memory.db"

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ReliaKit Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #1a202c; /* Dark background */
            color: #e2e8f0; /* Light text */
        }
        .container {
            max-width: 1200px;
        }
        .card {
            background-color: #2d3748; /* Darker card background */
            border-radius: 0.75rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header-gradient {
            background-image: linear-gradient(to right, #6366f1, #8b5cf6); /* Purple gradient */
        }
        .scroll-area {
            max-height: 500px;
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: #6366f1 #2d3748;
        }
        .scroll-area::-webkit-scrollbar {
            width: 8px;
        }
        .scroll-area::-webkit-scrollbar-track {
            background: #2d3748;
            border-radius: 10px;
        }
        .scroll-area::-webkit-scrollbar-thumb {
            background-color: #6366f1;
            border-radius: 10px;
            border: 2px solid #2d3748;
        }
    </style>
</head>
<body class="p-8">
    <div class="container mx-auto">
        <header class="header-gradient text-white p-6 rounded-xl shadow-lg mb-8">
            <h1 class="text-4xl font-bold text-center">ReliaKit Autonomous Dashboard</h1>
            <p class="text-xl text-center mt-2 opacity-90">Real-time System Monitoring & Insights</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <div class="card p-6">
                <h2 class="text-2xl font-semibold mb-4 text-purple-300">System Status</h2>
                <div id="system-status">
                    <p>Database: <span id="db-status" class="font-bold text-green-400">Connected</span></p>
                    <p>Last Refresh: <span id="last-refresh" class="font-bold">Loading...</span></p>
                    <p>Total Memories: <span id="total-memories" class="font-bold">Loading...</span></p>
                </div>
            </div>

            <div class="card p-6">
                <h2 class="text-2xl font-semibold mb-4 text-purple-300">Recent LLM Logs</h2>
                <div id="llm-log-summary">
                    <p>Last Model Used: <span id="last-model" class="font-bold">Loading...</span></p>
                    <p>Last Prompt: <span id="last-prompt" class="font-bold text-sm">Loading...</span></p>
                    <p>Last Response: <span id="last-response" class="font-bold text-sm">Loading...</span></p>
                </div>
            </div>

            <div class="card p-6">
                <h2 class="text-2xl font-semibold mb-4 text-purple-300">Agent Activity</h2>
                <div id="agent-activity">
                    <p>Active Agents: <span id="active-agents" class="font-bold">Loading...</span></p>
                    <p>Recent Executions: <span id="recent-executions" class="font-bold">Loading...</span></p>
                </div>
            </div>
        </div>

        <div class="card p-6 mb-8">
            <h2 class="text-2xl font-semibold mb-4 text-purple-300">Memory Snapshots</h2>
            <div id="memory-snapshots" class="scroll-area bg-gray-700 p-4 rounded-lg">
                <p class="text-center text-gray-400">Loading memory snapshots...</p>
            </div>
        </div>

        <div class="card p-6">
            <h2 class="text-2xl font-semibold mb-4 text-purple-300">Raw Data (Last 10 Logs)</h2>
            <div id="raw-data" class="scroll-area bg-gray-700 p-4 rounded-lg text-sm font-mono whitespace-pre-wrap">
                <p class="text-center text-gray-400">Loading raw data...</p>
            </div>
        </div>
    </div>

    <script>
        async function fetchData() {
            try {
                const response = await fetch('/memory');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error("Failed to fetch data:", error);
                document.getElementById('db-status').textContent = 'Disconnected';
                document.getElementById('db-status').classList.remove('text-green-400');
                document.getElementById('db-status').classList.add('text-red-400');
                document.getElementById('memory-snapshots').innerHTML = '<p class="text-center text-red-400">Error loading data: ' + error.message + '</p>';
                document.getElementById('raw-data').innerHTML = '<p class="text-center text-red-400">Error loading data: ' + error.message + '</p>';
            }
        }

        function updateDashboard(data) {
            document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();
            document.getElementById('total-memories').textContent = data.total_entries;

            // LLM Log Summary
            if (data.last_llm_log) {
                document.getElementById('last-model').textContent = data.last_llm_log.model;
                document.getElementById('last-prompt').textContent = data.last_llm_log.prompt.substring(0, 100) + (data.last_llm_log.prompt.length > 100 ? '...' : '');
                document.getElementById('last-response').textContent = data.last_llm_log.response.substring(0, 100) + (data.last_llm_log.response.length > 100 ? '...' : '');
            } else {
                document.getElementById('last-model').textContent = 'N/A';
                document.getElementById('last-prompt').textContent = 'No LLM logs yet.';
                document.getElementById('last-response').textContent = 'No LLM logs yet.';
            }

            // Memory Snapshots (llm_log entries)
            const snapshotsDiv = document.getElementById('memory-snapshots');
            snapshotsDiv.innerHTML = ''; // Clear previous content
            if (data.llm_logs && data.llm_logs.length > 0) {
                data.llm_logs.forEach(log => {
                    const logElement = document.createElement('div');
                    logElement.className = 'bg-gray-800 p-3 rounded-md mb-2 last:mb-0';
                    logElement.innerHTML = `
                        <p class="text-purple-400 font-semibold">${log.timestamp} - ${log.model}</p>
                        <p class="text-gray-300"><strong>Prompt:</strong> ${log.prompt}</p>
                        <p class="text-gray-400"><strong>Response:</strong> ${log.response}</p>
                    `;
                    snapshotsDiv.appendChild(logElement);
                });
            } else {
                snapshotsDiv.innerHTML = '<p class="text-center text-gray-400">No LLM logs recorded yet.</p>';
            }

            // Raw Data
            const rawDataDiv = document.getElementById('raw-data');
            rawDataDiv.textContent = JSON.stringify(data.llm_logs, null, 2);

            // Placeholder for Agent Activity - needs actual agent data
            document.getElementById('active-agents').textContent = 'N/A (TODO)';
            document.getElementById('recent-executions').textContent = 'N/A (TODO)';
        }

        // Initial fetch and set up auto-refresh
        fetchData();
        setInterval(fetchData, 5000); // Refresh every 5 seconds
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serves the main dashboard HTML page."""
    return render_template_string(DASHBOARD_HTML)

@app.route('/memory')
def get_memory_data():
    """
    API endpoint to fetch recent LLM log entries from the database.
    Returns data as JSON.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        cursor = conn.cursor()

        # Get all LLM logs, ordered by timestamp descending
        cursor.execute("SELECT id, prompt, response, model, timestamp FROM llm_log ORDER BY timestamp DESC")
        llm_logs = [dict(row) for row in cursor.fetchall()]

        # Get total entries
        cursor.execute("SELECT COUNT(*) FROM llm_log")
        total_entries = cursor.fetchone()[0]

        # Get last LLM log for summary
        last_llm_log = llm_logs[0] if llm_logs else None

        return jsonify({
            "total_entries": total_entries,
            "llm_logs": llm_logs,
            "last_llm_log": last_llm_log
        })
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        print(f"Server error: {e}")
        return jsonify({"error": "Server error", "details": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Ensure the database path exists before starting the app
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # You might want to call init_db() here if you're running this standalone
    # from reliakit.memory_db import init_db
    # init_db() # Ensure table is created

    print(f"ReliaKit Web Dashboard starting on http://127.0.0.1:5000")
    print(f"Database path: {DB_PATH}")
    app.run(debug=True, host='0.0.0.0', port=5001) # Host on 0.0.0.0 for LAN access