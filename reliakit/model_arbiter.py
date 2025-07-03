# reliakit/model_arbiter.py
import subprocess
from pathlib import Path
from reliakit.memory_db import MemoryDB
import os # For accessing environment variables

class ModelArbiter:
    def __init__(self):
        # Determine the database path relative to the project root
        # Assuming model_arbiter.py is in reliakit/
        db_path = Path(__file__).resolve().parent / "utils" / "memory.db"
        self.memory_db = MemoryDB(db_path=db_path)
        self.primary_model = "gemini"
        self.fallback_model = "ollama:gemma:2b"

    def run_query(self, agent_name: str, prompt: str) -> str:
        response = ""
        model_used = "N/A"
        status = "ERROR"

        try:
            # Attempt with primary model (Gemini CLI)
            model_used = self.primary_model
            gemini_command = ["npx", "@google/gemini-cli"]
            gemini_process = subprocess.Popen(
                gemini_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            response, error_output = gemini_process.communicate(input=prompt)
            
            print(f"Attempting query with primary model ({model_used})...")
            gemini_result = subprocess.run(
                gemini_command,
                capture_output=True,
                text=True,
                timeout=15, # Timeout after 15 seconds
                check=False # Do not raise CalledProcessError for non-zero exit codes yet
            )

            response = gemini_result.stdout.strip()
            error_output = gemini_result.stderr.strip()

            if not response or "quota" in error_output.lower() or "rate_limit" in error_output.lower() or "error" in error_output.lower():
                raise ValueError(f"Gemini failed: {error_output if error_output else 'Empty response or unknown error.'}")
            
            status = "SUCCESS"
            print(f"Primary model ({model_used}) succeeded.")

        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"Primary model ({model_used}) failed: {e}. Falling back to {self.fallback_model}...")
            # Attempt with fallback model (Ollama)
            model_used = self.fallback_model
            ollama_command = ["ollama", "run", "gemma:2b", prompt]
            try:
                ollama_result = subprocess.run(
                    ollama_command,
                    capture_output=True,
                    text=True,
                    check=True, # Raise CalledProcessError for non-zero exit codes
                    timeout=30 # Allow a longer timeout for Ollama
                )
                response = ollama_result.stdout.strip()
                if not response:
                    raise ValueError("Ollama failed: Empty response.")
                
                status = "FALLBACK"
                print(f"Fallback model ({model_used}) succeeded.")

            except (subprocess.CalledProcessError, FileNotFoundError, ValueError, subprocess.TimeoutExpired) as e_fallback:
                print(f"Fallback model ({model_used}) also failed: {e_fallback}")
                response = "LLM ERROR: Both primary and fallback models failed to provide a valid response."
                status = "ERROR"
        finally:
            self.memory_db.insert_log(
                agent_name=agent_name,
                model_used=model_used,
                prompt=prompt,
                response=response,
                status=status
            )
            return response