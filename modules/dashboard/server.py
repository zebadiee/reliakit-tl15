# File: modules/dashboard/server.py
from flask import Flask, render_template, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = '/app/reliakit/memory.db' # The absolute path to the DB inside the container

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
    cursor = db.execute('SELECT * FROM llm_log ORDER BY timestamp DESC LIMIT 50')
    actions = cursor.fetchall()
    return render_template('index.html', actions=actions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
