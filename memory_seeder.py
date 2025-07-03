# memory_seeder.py
from reliakit.memory_db import MemoryDB
from pathlib import Path
import json

def seed_database(db_path: Path):
    db = MemoryDB(db_path=db_path)

    if db.has_entries():
        print("🧠 Database already seeded. Skipping.")
        return

    print("🌱 Seeding database with initial entries...")
    db.insert_log(
        agent_name="EchoLens",
        model_used="gemini-pro",
        prompt="Seed prompt: What is ReliaKit?",
        response="ReliaKit is a modular automation framework for resilient AI/DevOps workflows.",
        status="SEED"
    )
    db.insert_log(
        agent_name="LoopGuardian",
        model_used="gemma:2b",
        prompt="Seed prompt: Why use fallback logic?",
        response="Fallback logic ensures LLM continuity and prevents quota exhaustion disruptions.",
        status="SEED"
    )
    print("✅ Seeding complete.")

    config_dir = Path(__file__).resolve().parent / "generated_configs"
    agent_config_path = config_dir / "new_agents.jsonl"

    if not agent_config_path.exists():
        print(f"⚠️ Agent config file not found at {agent_config_path}. Creating dummy.")
        dummy_agents = [
            {"name": "CodeHealer", "description": "Refactors legacy code."},
            {"name": "FusionForge", "description": "Analyzes and merges modules."},
            {"name": "LoopGuardian", "description": "Monitors token usage and ethics."},
            {"name": "QuanaSage", "description": "Manages agent governance and rules."}
        ]
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(agent_config_path, 'w') as f:
            for agent in dummy_agents:
                f.write(json.dumps(agent) + '\n')
        print("✅ Dummy new_agents.jsonl created.")
    else:
        print(f"✅ Agent config file exists at {agent_config_path}.")
