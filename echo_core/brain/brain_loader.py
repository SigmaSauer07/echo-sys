# Echo Core Brain Loader
import importlib
import os

MODULES = [
    "planner",
    "goal_memory",
    "decomposer",
    "persona_switch",
    "brainlet_local",
    "chaos_sandbox",
    "self_edit"
]

loaded_modules = {}

for mod in MODULES:
    try:
        loaded_modules[mod] = importlib.import_module(f"echo_core.brain.modules.{mod}")
        print(f"Loaded module: {mod}")
    except ImportError:
        print(f"Failed to load module: {mod}")
