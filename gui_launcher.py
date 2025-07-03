# gui_launcher.py
import tkinter as tk
from reliakit.codex_base_ui import CodexBaseUI
import sys
import argparse
from pathlib import Path
import subprocess # For running agent execution

# Corrected imports for memory_seeder and MemoryDB
from memory_seeder import seed_database
from reliakit.memory_db import MemoryDB

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Seed the memory database")
    parser.add_argument("--execute", type=str, help="Agent name to execute")
    parser.add_argument("--input", type=str, help="Input data for the agent")
    args = parser.parse_args()

    # Determine the database path relative to the project root
    db_path = Path(__file__).resolve().parent / "reliakit" / "utils" / "memory.db"

    if args.seed:
        # Initialize MemoryDB to ensure table exists before seeding
        MemoryDB(db_path=db_path) 
        seed_database(db_path=db_path)
        print("✅ Database seeded.")
        return

    if args.execute:
        print(f"🧠 Executing {args.execute} with input: '{args.input}'")
        # This part simulates the agent's execution and logs it to the DB.
        # In a real scenario, this would trigger the actual agent logic.
        db = MemoryDB(db_path=db_path)
        try:
            # Simulate agent execution and log it
            response_text = f"Agent '{args.execute}' processed input: '{args.input}' successfully."
            db.insert_log( # Changed to insert_log
                agent_name=args.execute,
                model_used="SimulatedModel", # Use a simulated model name for direct execution
                prompt=args.input,
                response=response_text,
                status="SUCCESS"
            )
            print(f"Execution logged: {response_text}")
        except Exception as e:
            error_response = f"Error executing agent '{args.execute}': {e}"
            db.insert_log( # Changed to insert_log
                agent_name=args.execute,
                model_used="SimulatedModel/Error",
                prompt=args.input,
                response=error_response,
                status="ERROR" # Log as ERROR status
            )
            print(f"Execution failed and logged: {error_response}")
        return

    # Launch GUI
    root = tk.Tk()
    app = CodexBaseUI(root, db_path=db_path) # Pass db_path to GUI
    root.mainloop()

if __name__ == "__main__":
    main()