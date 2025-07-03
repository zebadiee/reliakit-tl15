# reliakit/codex_base_ui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
import json
from reliakit.memory_db import MemoryDB # Import MemoryDB
# from reliakit.model_arbiter import ModelArbiter # Uncomment when ModelArbiter is ready
import subprocess # For running agents

class CodexBaseUI:
    def __init__(self, root, db_path: Path):
        self.root = root
        self.root.title("ReliaKit Autonomous Dashboard")
        self.db_path = db_path
        self.memory_db = MemoryDB(db_path=self.db_path) # Initialize MemoryDB
        self.available_agents = self._load_available_agents() # Load agents from JSONL

        self._create_notebook()
        self._create_main_tab()
        self._create_memory_tab()
        self._create_visualization_tabs()

        # Start auto-refresh for memory viewer
        self._auto_refresh_memory()

    def _load_available_agents(self) -> list:
        """Loads available agent names from new_agents.jsonl."""
        config_path = Path(__file__).resolve().parent.parent / "generated_configs" / "new_agents.jsonl"
        agents = []
        if config_path.exists():
            with open(config_path, 'r') as f:
                for line in f:
                    try:
                        agent_data = json.loads(line.strip())
                        if 'name' in agent_data:
                            agents.append(agent_data['name'])
                    except json.JSONDecodeError:
                        print(f"Error decoding agent JSON: {line.strip()}")
        if not agents:
            print("No agent configurations found or loaded. Using dummy agents.")
            agents = ["CodeHealer", "FusionForge", "LoopGuardian", "QuanaSage"] # Fallback dummy agents
        return agents

    def _create_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

    def _create_main_tab(self):
        tab_main = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_main, text="Main Dashboard")

        # Agent Execution Controls
        frame_controls = ttk.LabelFrame(tab_main, text="Agent Executor", padding="10")
        frame_controls.pack(fill="x", pady=5)

        ttk.Label(frame_controls, text="Select Agent:").pack(side="left", padx=5)
        self.agent_var = tk.StringVar()
        self.agent_dropdown = ttk.Combobox(frame_controls, textvariable=self.agent_var, values=self.available_agents)
        if self.available_agents:
            self.agent_dropdown.set(self.available_agents[0]) # Set default to first agent
        self.agent_dropdown.pack(side="left", padx=5, expand=True, fill="x")

        ttk.Label(frame_controls, text="Input:").pack(side="left", padx=5)
        self.input_entry = ttk.Entry(frame_controls, width=40)
        self.input_entry.pack(side="left", padx=5, expand=True, fill="x")

        run_button = ttk.Button(frame_controls, text="Run Agent", command=self._run_agent)
        run_button.pack(side="left", padx=5)

        # Output Log (for agent execution feedback)
        self.output_log = scrolledtext.ScrolledText(tab_main, wrap=tk.WORD, height=15, state='disabled')
        self.output_log.pack(fill="both", expand=True, pady=10)

        # Auto-heal button
        auto_heal_frame = ttk.LabelFrame(tab_main, text="Self-Healing", padding="10")
        auto_heal_frame.pack(fill="x", pady=5)
        ttk.Button(auto_heal_frame, text="Auto-Heal Failed Agents", command=self._auto_heal_agents).pack(pady=5)

    def _run_agent(self):
        agent = self.agent_var.get()
        input_text = self.input_entry.get()
        self._log_output(f"Attempting to run agent '{agent}' with input: '{input_text}'...")

        if not agent or not input_text:
            self._log_output("Error: Agent name and input cannot be empty.", "red")
            return

        try:
            # Use subprocess to call gui_launcher.py with --execute flag
            # This simulates the agent execution and logs to the DB
            command = [
                "python3",
                str(Path(__file__).resolve().parent.parent / "gui_launcher.py"),
                "--execute", agent,
                "--input", input_text
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                self._log_output(f"Agent '{agent}' execution command successful.", "green")
                self._log_output(result.stdout)
            else:
                self._log_output(f"Agent '{agent}' execution command failed (Exit Code: {result.returncode}).", "red")
                self._log_output("STDOUT:\n" + result.stdout, "red")
                self._log_output("STDERR:\n" + result.stderr, "red")
            
            # Refresh memory viewer after execution attempt
            self._load_memory_snapshots()

        except FileNotFoundError:
            self._log_output(f"Error: Python or gui_launcher.py not found. Check your PATH and script location.", "red")
        except Exception as e:
            self._log_output(f"An unexpected error occurred during agent execution: {e}", "red")

    def _auto_heal_agents(self):
        self._log_output("Initiating auto-healing process...", "blue")
        # Placeholder for auto-healing logic
        # In a real scenario, this would query the DB for "FAILURE" status logs,
        # and attempt to re-run or apply corrective actions.
        failed_logs = [log for log in self.memory_db.get_all_llm_logs() if log.get('status') == 'ERROR'] # Assuming 'ERROR' for failed
        
        if not failed_logs:
            self._log_output("No failed agent executions found to heal.", "green")
            return

        self._log_output(f"Found {len(failed_logs)} failed agent executions. Attempting to re-run...", "blue")
        for i, log in enumerate(failed_logs):
            self._log_output(f"Re-running failed agent: {log['agent_name']} (Prompt: {log['prompt'][:50]}...)", "orange")
            # Simulate re-running the agent
            command = [
                "python3",
                str(Path(__file__).resolve().parent.parent / "gui_launcher.py"),
                "--execute", log['agent_name'],
                "--input", log['prompt']
            ]
            subprocess.run(command, capture_output=True, text=True, check=False) # Run without capturing output here for simplicity
            self._log_output(f"Re-run attempt {i+1} for {log['agent_name']} completed. Check memory tab for new status.", "blue")
        
        self._log_output("Auto-healing process finished. Refreshing memory view.", "green")
        self._load_memory_snapshots() # Refresh after healing attempts

    def _log_output(self, message, color="white"):
        self.output_log.config(state='normal')
        self.output_log.insert(tk.END, message + "\n", color)
        self.output_log.see(tk.END)
        self.output_log.config(state='disabled')
        self.output_log.tag_config("red", foreground="red")
        self.output_log.tag_config("green", foreground="green")
        self.output_log.tag_config("blue", foreground="blue")
        self.output_log.tag_config("orange", foreground="orange")

    def _create_memory_tab(self):
        self.tab_memory = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_memory, text="Memory Viewer")

        self.memory_text = scrolledtext.ScrolledText(self.tab_memory, wrap=tk.WORD, height=20, state='disabled')
        self.memory_text.pack(fill="both", expand=True, pady=5)

        self._load_memory_snapshots()

    def _load_memory_snapshots(self):
        self.memory_text.config(state='normal')
        self.memory_text.delete(1.0, tk.END)
        
        logs = self.memory_db.get_all_llm_logs()
        if not logs:
            self.memory_text.insert(tk.END, "No memory snapshots found yet.\n")
        else:
            for log in logs:
                timestamp = log.get('timestamp', 'N/A')
                agent_name = log.get('agent_name', 'N/A')
                model_used = log.get('model_used', 'N/A')
                prompt = log.get('prompt', 'N/A')
                response = log.get('response', 'N/A')
                status = log.get('status', 'N/A')

                self.memory_text.insert(tk.END, f"[{timestamp}] Agent: {agent_name}, Model: {model_used}\n")
                self.memory_text.insert(tk.END, f"  Prompt: {prompt}\n")
                self.memory_text.insert(tk.END, f"  Response: {response}\n")
                self.memory_text.insert(tk.END, f"  Status: {status}\n\n")
        
        self.memory_text.config(state='disabled')
        self.memory_text.see(tk.END)

    def _auto_refresh_memory(self):
        self._load_memory_snapshots()
        self.root.after(5000, self._auto_refresh_memory) # Refresh every 5 seconds

    def _create_visualization_tabs(self):
        # Memory Glyphs Tab
        tab_glyphs = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_glyphs, text="Memory Glyphs")
        ttk.Label(tab_glyphs, text="Memory Glyphs Visualization (TODO: Implement rendering logic)").pack(pady=20)

        # Agent Graph Tab
        tab_graph = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_graph, text="Agent Graph")
        ttk.Label(tab_graph, text="Agent Relationship Graph (TODO: Implement rendering logic)").pack(pady=20)

        # Time Tunnel Tab
        tab_timeline = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_timeline, text="Time Tunnel")
        ttk.Label(tab_timeline, text="Execution Timeline (TODO: Implement rendering logic)").pack(pady=20)

        # Token Economy Tab
        tab_tokens = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_tokens, text="Token Economy")
        ttk.Label(tab_tokens, text="Real-time Token Usage Meters (TODO: Implement rendering logic)").pack(pady=20)