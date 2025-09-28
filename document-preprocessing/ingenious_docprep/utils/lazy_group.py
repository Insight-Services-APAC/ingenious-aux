"""Simple lazy group implementation for CLI."""

import importlib
from typing import Any, Dict, Optional
import typer


class LazyGroup:
    """Simple lazy group for loading CLI commands on demand."""
    
    def __init__(self, name: str = "app"):
        self.name = name
        self.commands: Dict[str, str] = {}
        self._loaded_commands: Dict[str, Any] = {}
    
    def add_command(self, name: str, module_path: str) -> None:
        """Add a command that will be loaded lazily."""
        self.commands[name] = module_path
    
    def get_command(self, name: str) -> Optional[Any]:
        """Get a command by name, loading it if necessary."""
        if name in self._loaded_commands:
            return self._loaded_commands[name]
        
        if name not in self.commands:
            return None
        
        try:
            module_path = self.commands[name]
            module = importlib.import_module(module_path)
            command = getattr(module, 'cli', None) or getattr(module, 'app', None)
            if command:
                self._loaded_commands[name] = command
                return command
        except ImportError:
            pass
        
        return None
    
    def list_commands(self) -> list:
        """List all available commands."""
        return list(self.commands.keys())