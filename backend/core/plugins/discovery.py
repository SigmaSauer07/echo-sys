"""
Plugin Discovery System

Automatically discovers and loads plugins from specified directories
with support for plugin manifests and dependency resolution.
"""

import os
import json
import yaml
import importlib
import importlib.util
import logging
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from dataclasses import dataclass
from .interfaces import IPlugin, PluginMetadata, PluginType
from .exceptions import PluginLoadError, PluginDependencyError

logger = logging.getLogger("alsaniamcp.plugins.discovery")


@dataclass
class PluginManifest:
    """Plugin manifest data"""
    name: str
    version: str
    type: PluginType
    description: str = ""
    author: str = ""
    license: str = ""
    dependencies: List[str] = None
    entry_point: str = ""
    configuration_schema: Dict[str, Any] = None
    hot_reload: bool = True
    priority: int = 100
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.configuration_schema is None:
            self.configuration_schema = {}


class PluginDiscovery:
    """Plugin discovery and loading system"""
    
    def __init__(self):
        self._discovered_plugins: Dict[str, PluginManifest] = {}
        self._plugin_paths: Dict[str, Path] = {}
        self._loaded_modules: Dict[str, Any] = {}
    
    async def discover_plugins(self, discovery_paths: List[str]) -> Dict[str, PluginManifest]:
        """Discover plugins in specified directories"""
        self._discovered_plugins.clear()
        self._plugin_paths.clear()
        
        for path_str in discovery_paths:
            path = Path(path_str)
            if path.exists() and path.is_dir():
                await self._scan_directory(path)
            else:
                logger.warning(f"Plugin discovery path does not exist: {path_str}")
        
        logger.info(f"Discovered {len(self._discovered_plugins)} plugins")
        return self._discovered_plugins.copy()
    
    async def _scan_directory(self, directory: Path) -> None:
        """Scan a directory for plugins"""
        logger.debug(f"Scanning directory for plugins: {directory}")
        
        # Look for plugin directories (containing plugin.yaml/json)
        for item in directory.iterdir():
            if item.is_dir():
                await self._scan_plugin_directory(item)
            elif item.is_file() and item.suffix.lower() == '.py':
                await self._scan_plugin_file(item)
    
    async def _scan_plugin_directory(self, plugin_dir: Path) -> None:
        """Scan a plugin directory for manifest and entry point"""
        manifest_files = [
            plugin_dir / "plugin.yaml",
            plugin_dir / "plugin.yml", 
            plugin_dir / "plugin.json",
            plugin_dir / "manifest.yaml",
            plugin_dir / "manifest.yml",
            plugin_dir / "manifest.json"
        ]
        
        manifest_file = None
        for file in manifest_files:
            if file.exists():
                manifest_file = file
                break
        
        if not manifest_file:
            logger.debug(f"No manifest found in plugin directory: {plugin_dir}")
            return
        
        try:
            manifest = await self._load_manifest(manifest_file)
            if manifest:
                # Resolve entry point path
                if manifest.entry_point:
                    entry_path = plugin_dir / manifest.entry_point.replace('.', '/').replace(':', '/') + '.py'
                    if not entry_path.exists():
                        # Try alternative paths
                        alt_paths = [
                            plugin_dir / f"{manifest.name}.py",
                            plugin_dir / "main.py",
                            plugin_dir / "__init__.py"
                        ]
                        for alt_path in alt_paths:
                            if alt_path.exists():
                                entry_path = alt_path
                                break
                else:
                    # Default entry points
                    default_files = [
                        plugin_dir / f"{manifest.name}.py",
                        plugin_dir / "main.py",
                        plugin_dir / "__init__.py"
                    ]
                    entry_path = None
                    for file in default_files:
                        if file.exists():
                            entry_path = file
                            break
                
                if entry_path and entry_path.exists():
                    self._discovered_plugins[manifest.name] = manifest
                    self._plugin_paths[manifest.name] = entry_path
                    logger.debug(f"Discovered plugin: {manifest.name} at {entry_path}")
                else:
                    logger.warning(f"Entry point not found for plugin: {manifest.name}")
                    
        except Exception as e:
            logger.error(f"Error scanning plugin directory {plugin_dir}: {e}")
    
    async def _scan_plugin_file(self, plugin_file: Path) -> None:
        """Scan a single Python file for plugin"""
        try:
            # Try to extract plugin info from file
            manifest = await self._extract_manifest_from_file(plugin_file)
            if manifest:
                self._discovered_plugins[manifest.name] = manifest
                self._plugin_paths[manifest.name] = plugin_file
                logger.debug(f"Discovered plugin: {manifest.name} at {plugin_file}")
                
        except Exception as e:
            logger.debug(f"Could not extract plugin info from {plugin_file}: {e}")
    
    async def _load_manifest(self, manifest_file: Path) -> Optional[PluginManifest]:
        """Load plugin manifest from file"""
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                if manifest_file.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
            
            # Convert type string to enum
            plugin_type = PluginType(data.get('type', 'extension'))
            
            manifest = PluginManifest(
                name=data['name'],
                version=data.get('version', '1.0.0'),
                type=plugin_type,
                description=data.get('description', ''),
                author=data.get('author', ''),
                license=data.get('license', ''),
                dependencies=data.get('dependencies', []),
                entry_point=data.get('entry_point', ''),
                configuration_schema=data.get('configuration', {}).get('schema', {}),
                hot_reload=data.get('hot_reload', True),
                priority=data.get('priority', 100)
            )
            
            return manifest
            
        except Exception as e:
            logger.error(f"Error loading manifest from {manifest_file}: {e}")
            return None
    
    async def _extract_manifest_from_file(self, plugin_file: Path) -> Optional[PluginManifest]:
        """Extract plugin manifest from Python file docstring or comments"""
        try:
            with open(plugin_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for plugin metadata in docstring or comments
            # This is a simplified implementation - could be enhanced
            lines = content.split('\n')
            
            # Try to find plugin class
            plugin_class_name = None
            for line in lines:
                if 'class ' in line and ('Plugin' in line or 'Agent' in line):
                    parts = line.split()
                    if len(parts) >= 2:
                        plugin_class_name = parts[1].split('(')[0]
                        break
            
            if plugin_class_name:
                # Create basic manifest
                manifest = PluginManifest(
                    name=plugin_file.stem,
                    version="1.0.0",
                    type=PluginType.EXTENSION,
                    entry_point=f"{plugin_file.stem}:{plugin_class_name}"
                )
                return manifest
                
        except Exception as e:
            logger.debug(f"Could not extract manifest from {plugin_file}: {e}")
        
        return None
    
    async def load_plugin(self, plugin_name: str) -> Type[IPlugin]:
        """Load a discovered plugin"""
        if plugin_name not in self._discovered_plugins:
            raise PluginLoadError(f"Plugin not discovered: {plugin_name}")
        
        if plugin_name in self._loaded_modules:
            # Return cached module
            return self._get_plugin_class_from_module(
                self._loaded_modules[plugin_name],
                self._discovered_plugins[plugin_name]
            )
        
        manifest = self._discovered_plugins[plugin_name]
        plugin_path = self._plugin_paths[plugin_name]
        
        try:
            # Load the module
            module = await self._load_module(plugin_name, plugin_path)
            self._loaded_modules[plugin_name] = module
            
            # Get the plugin class
            plugin_class = self._get_plugin_class_from_module(module, manifest)
            
            logger.info(f"Loaded plugin: {plugin_name}")
            return plugin_class
            
        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin {plugin_name}", plugin_name, e)
    
    async def _load_module(self, plugin_name: str, plugin_path: Path) -> Any:
        """Load a Python module from file"""
        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not create module spec for {plugin_name}")
            
            # Create and execute module
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            return module
            
        except Exception as e:
            raise PluginLoadError(f"Failed to load module for plugin {plugin_name}", plugin_name, e)
    
    def _get_plugin_class_from_module(self, module: Any, manifest: PluginManifest) -> Type[IPlugin]:
        """Extract plugin class from loaded module"""
        # Parse entry point
        if ':' in manifest.entry_point:
            module_path, class_name = manifest.entry_point.split(':', 1)
        else:
            # Try to find plugin class automatically
            class_name = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, IPlugin) and 
                    attr != IPlugin):
                    class_name = attr_name
                    break
        
        if not class_name:
            raise PluginLoadError(f"Could not find plugin class in module for {manifest.name}")
        
        if not hasattr(module, class_name):
            raise PluginLoadError(f"Plugin class {class_name} not found in module for {manifest.name}")
        
        plugin_class = getattr(module, class_name)
        
        # Verify it's a valid plugin class
        if not (isinstance(plugin_class, type) and issubclass(plugin_class, IPlugin)):
            raise PluginLoadError(f"Class {class_name} is not a valid plugin class for {manifest.name}")
        
        return plugin_class
    
    def get_discovered_plugins(self) -> Dict[str, PluginManifest]:
        """Get all discovered plugins"""
        return self._discovered_plugins.copy()
    
    def get_plugin_manifest(self, plugin_name: str) -> Optional[PluginManifest]:
        """Get manifest for a specific plugin"""
        return self._discovered_plugins.get(plugin_name)
    
    def resolve_dependencies(self, plugin_names: List[str]) -> List[str]:
        """Resolve plugin dependencies and return load order"""
        # Simple topological sort for dependency resolution
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(plugin_name: str):
            if plugin_name in temp_visited:
                raise PluginDependencyError(f"Circular dependency detected involving {plugin_name}")
            
            if plugin_name in visited:
                return
            
            if plugin_name not in self._discovered_plugins:
                raise PluginDependencyError(f"Dependency not found: {plugin_name}")
            
            temp_visited.add(plugin_name)
            
            # Visit dependencies first
            manifest = self._discovered_plugins[plugin_name]
            for dep in manifest.dependencies:
                visit(dep)
            
            temp_visited.remove(plugin_name)
            visited.add(plugin_name)
            result.append(plugin_name)
        
        # Visit all requested plugins
        for plugin_name in plugin_names:
            if plugin_name not in visited:
                visit(plugin_name)
        
        return result
    
    async def reload_plugin(self, plugin_name: str) -> Type[IPlugin]:
        """Reload a plugin module"""
        if plugin_name not in self._loaded_modules:
            return await self.load_plugin(plugin_name)
        
        # Remove from cache and reload
        del self._loaded_modules[plugin_name]
        
        # Also remove from sys.modules if present
        import sys
        modules_to_remove = [name for name in sys.modules if name.startswith(plugin_name)]
        for module_name in modules_to_remove:
            del sys.modules[module_name]
        
        return await self.load_plugin(plugin_name)
