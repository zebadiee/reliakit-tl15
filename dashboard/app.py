# File: dashboard/app.py
from flask import Flask, render_template, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = '/app/memory_data/memory.db' # The absolute path to the DB inside the container

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # The check_same_thread=False is important because Flask can handle
        # requests in different threads than the one that created the connection.
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row # Allows accessing columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
    # Corrected table name to 'llm_log'
    cursor = db.execute('SELECT * FROM llm_log ORDER BY timestamp DESC LIMIT 50')
    actions = cursor.fetchall()
    return render_template('index.html', actions=actions)

if __name__ == '__main__':
    # Binds to 0.0.0.0 to be accessible outside the container
    app.run(host='0.0.0.0', port=5000, debug=True)
