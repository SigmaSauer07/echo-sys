"""
Configuration Management System

Provides centralized configuration management with support for
multiple sources, validation, and change notifications.
"""

import os
import json
import yaml
import logging
from typing import Any, Dict, List, Optional, Callable, Union
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from .events import EventBus, publish_event, SystemEventTypes

logger = logging.getLogger("alsaniamcp.plugins.config")


@dataclass
class ConfigSource:
    """Configuration source descriptor"""
    name: str
    path: str
    format: str  # json, yaml, env
    priority: int = 100  # Higher priority overrides lower
    watch: bool = True
    last_modified: Optional[datetime] = None


class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._config: Dict[str, Any] = {}
        self._sources: List[ConfigSource] = []
        self._watchers: List[Callable[[str, Any, Any], None]] = []
        self._event_bus = event_bus
        self._file_watchers: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
        # Default configuration
        self._defaults = {
            'plugins': {
                'discovery_paths': ['./plugins', './backend/plugins'],
                'auto_load': True,
                'hot_reload': True
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'system': {
                'health_check_interval': 30,
                'max_concurrent_operations': 10
            }
        }
        
        self._config.update(self._defaults)
    
    def add_source(self, name: str, path: str, format: str = "auto",
                   priority: int = 100, watch: bool = True) -> None:
        """Add a configuration source"""
        if format == "auto":
            format = self._detect_format(path)
        
        source = ConfigSource(
            name=name,
            path=path,
            format=format,
            priority=priority,
            watch=watch
        )
        
        self._sources.append(source)
        self._sources.sort(key=lambda s: s.priority)
        
        logger.debug(f"Added config source: {name} ({path})")
    
    def _detect_format(self, path: str) -> str:
        """Auto-detect configuration format from file extension"""
        ext = Path(path).suffix.lower()
        if ext in ['.json']:
            return 'json'
        elif ext in ['.yaml', '.yml']:
            return 'yaml'
        elif ext in ['.env']:
            return 'env'
        else:
            return 'json'  # Default
    
    async def load_all(self) -> None:
        """Load configuration from all sources"""
        async with self._lock:
            # Start with defaults
            new_config = self._defaults.copy()
            
            # Load from sources in priority order
            for source in self._sources:
                try:
                    source_config = await self._load_source(source)
                    if source_config:
                        new_config = self._merge_config(new_config, source_config)
                        logger.debug(f"Loaded config from source: {source.name}")
                except Exception as e:
                    logger.error(f"Failed to load config from {source.name}: {e}")
            
            # Load environment variables
            env_config = self._load_environment()
            if env_config:
                new_config = self._merge_config(new_config, env_config)
            
            # Update configuration
            old_config = self._config.copy()
            self._config = new_config
            
            # Notify watchers of changes
            await self._notify_changes(old_config, new_config)
            
            # Start file watchers
            await self._start_file_watchers()
    
    async def _load_source(self, source: ConfigSource) -> Optional[Dict[str, Any]]:
        """Load configuration from a single source"""
        path = Path(source.path)
        
        if not path.exists():
            logger.warning(f"Config file not found: {source.path}")
            return None
        
        # Update last modified time
        source.last_modified = datetime.fromtimestamp(path.stat().st_mtime)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if source.format == 'json':
                    return json.load(f)
                elif source.format == 'yaml':
                    return yaml.safe_load(f)
                elif source.format == 'env':
                    return self._parse_env_file(f.read())
                else:
                    logger.error(f"Unsupported config format: {source.format}")
                    return None
        except Exception as e:
            logger.error(f"Error reading config file {source.path}: {e}")
            return None
    
    def _parse_env_file(self, content: str) -> Dict[str, Any]:
        """Parse environment file content"""
        config = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Convert nested keys (e.g., PLUGIN_AGENT_TIMEOUT -> plugin.agent.timeout)
                    nested_key = key.lower().replace('_', '.')
                    self._set_nested_value(config, nested_key, value)
        return config
    
    def _load_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}
        prefix = "ALSANIAMCP_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and convert to nested key
                config_key = key[len(prefix):].lower().replace('_', '.')
                self._set_nested_value(config, config_key, value)
        
        return config
    
    def _set_nested_value(self, config: Dict[str, Any], key: str, value: str) -> None:
        """Set a nested configuration value"""
        keys = key.split('.')
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Try to convert value to appropriate type
        current[keys[-1]] = self._convert_value(value)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type"""
        # Boolean values
        if value.lower() in ('true', 'yes', '1'):
            return True
        elif value.lower() in ('false', 'no', '0'):
            return False
        
        # Numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # JSON values
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # String value
        return value
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    async def _start_file_watchers(self) -> None:
        """Start file watchers for configuration sources"""
        for source in self._sources:
            if source.watch and source.path not in self._file_watchers:
                task = asyncio.create_task(self._watch_file(source))
                self._file_watchers[source.path] = task
    
    async def _watch_file(self, source: ConfigSource) -> None:
        """Watch a configuration file for changes"""
        path = Path(source.path)
        last_mtime = source.last_modified
        
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                
                if path.exists():
                    current_mtime = datetime.fromtimestamp(path.stat().st_mtime)
                    if last_mtime is None or current_mtime > last_mtime:
                        logger.info(f"Config file changed: {source.path}")
                        await self.reload_source(source.name)
                        last_mtime = current_mtime
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error watching config file {source.path}: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def reload_source(self, source_name: str) -> None:
        """Reload configuration from a specific source"""
        source = next((s for s in self._sources if s.name == source_name), None)
        if not source:
            logger.warning(f"Config source not found: {source_name}")
            return
        
        try:
            old_config = self._config.copy()
            await self.load_all()  # Reload all sources to maintain priority order
            
            logger.info(f"Reloaded config from source: {source_name}")
            
        except Exception as e:
            logger.error(f"Failed to reload config from {source_name}: {e}")
    
    async def _notify_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> None:
        """Notify watchers of configuration changes"""
        changes = self._find_changes(old_config, new_config)
        
        for key, (old_value, new_value) in changes.items():
            # Notify registered watchers
            for watcher in self._watchers:
                try:
                    watcher(key, old_value, new_value)
                except Exception as e:
                    logger.error(f"Error in config watcher: {e}")
            
            # Publish event
            if self._event_bus:
                await publish_event(
                    SystemEventTypes.CONFIG_CHANGED,
                    data={
                        'key': key,
                        'old_value': old_value,
                        'new_value': new_value
                    },
                    source="config_manager"
                )
    
    def _find_changes(self, old: Dict[str, Any], new: Dict[str, Any], prefix: str = "") -> Dict[str, tuple]:
        """Find changes between two configuration dictionaries"""
        changes = {}
        
        # Check for changed/added values
        for key, value in new.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if key not in old:
                changes[full_key] = (None, value)
            elif isinstance(value, dict) and isinstance(old[key], dict):
                changes.update(self._find_changes(old[key], value, full_key))
            elif old[key] != value:
                changes[full_key] = (old[key], value)
        
        # Check for removed values
        for key in old:
            if key not in new:
                full_key = f"{prefix}.{key}" if prefix else key
                changes[full_key] = (old[key], None)
        
        return changes
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        current = self._config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        keys = key.split('.')
        current = self._config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        old_value = current.get(keys[-1])
        current[keys[-1]] = value
        
        # Notify watchers
        for watcher in self._watchers:
            try:
                watcher(key, old_value, value)
            except Exception as e:
                logger.error(f"Error in config watcher: {e}")
    
    def watch(self, callback: Callable[[str, Any, Any], None]) -> None:
        """Watch for configuration changes"""
        self._watchers.append(callback)
    
    def unwatch(self, callback: Callable[[str, Any, Any], None]) -> bool:
        """Stop watching for configuration changes"""
        if callback in self._watchers:
            self._watchers.remove(callback)
            return True
        return False
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self._config.copy()
    
    async def shutdown(self) -> None:
        """Shutdown configuration manager"""
        # Cancel file watchers
        for task in self._file_watchers.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._file_watchers:
            await asyncio.gather(*self._file_watchers.values(), return_exceptions=True)
        
        self._file_watchers.clear()
        logger.info("Configuration manager shutdown complete")
