import json

import os

def load_codex_gpts():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, '..', '..')
    jsonl_path = os.path.join(project_root, 'generated_configs', 'reliakit_codex_gpts.jsonl')
    """Load GPT configurations from JSONL file"""
    with open(jsonl_path, "r") as f:
        return [json.loads(line) for line in f if line.strip()]