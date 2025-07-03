from reliakit.memory_db import Base, engine
from pathlib import Path
import os

def init_db():
    # Ensure utils directory exists
    utils_dir = Path(__file__).parent / "utils"
    utils_dir.mkdir(exist_ok=True)
    
    # Create all tables
    Base.metadata.create_all(engine)
    print(f"Database initialized at {utils_dir/'memory.db'}")

if __name__ == '__main__':
    init_db()