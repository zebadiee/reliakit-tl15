# init_memory_db.py
from reliakit.memory_db import MemoryDB # Correctly import the MemoryDB class
from memory_seeder import seed_database # Import the seeding function
from pathlib import Path

def init_db():
    """
    Initializes the ReliaKit memory database and seeds it.
    This function creates the database file and the necessary tables if they don't exist.
    It also calls the seeding function.
    """
    # Determine the database path relative to the project root
    # Assuming init_memory_db.py is at the ReliaKit/ level
    db_path = Path(__file__).resolve().parent / "reliakit" / "utils" / "memory.db"
    
    print(f"🛠 Initializing database at: {db_path}")
    # Instantiating MemoryDB will ensure the database file and the 'llm_log' table are created
    MemoryDB(db_path=db_path) 
    print("✅ Database structure ensured.")
    
    # Call the seeding function to add initial data if the database is empty
    seed_database(db_path=db_path)
    print("✅ Database seeding complete.")

if __name__ == '__main__':
    init_db()
    print("✅ ReliaKit memory database initialized successfully.")
