# test_fallback.py
from reliakit.model_arbiter import ModelArbiter
from pathlib import Path
import os

# Ensure the database path exists for testing
# This assumes test_fallback.py is at the ReliaKit/ root.
db_dir = Path(__file__).resolve().parent / "reliakit" / "utils"
db_dir.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

# Initialize the database (this will also seed if empty)
# This is a simplified call for testing. In a full system, init_memory_db.py handles this.
from reliakit.memory_db import MemoryDB
MemoryDB(db_path=db_dir / "memory.db")

print("Initializing ModelArbiter and running test query...")
arbiter = ModelArbiter()
response = arbiter.run_query(agent_name="EchoLens", prompt="Write a Python function to reverse a linked list.")
print("\n--- Test Response ---")
print(response)
print("--- End Test Response ---")

# Optional: Verify log entry
# db = MemoryDB(db_path=db_dir / "memory.db")
# last_log = db.get_all_llm_logs()[-1] if db.get_all_llm_logs() else None
# if last_log:
#     print(f"\nLast log entry: Model: {last_log['model_used']}, Status: {last_log['status']}")