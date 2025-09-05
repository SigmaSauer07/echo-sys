"""
Centralized Import Management System

Provides standardized import handling with error recovery,
dependency validation, and absolute import enforcement.
"""

import sys
import importlib
import importlib.util
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path
import traceback

logger = logging.getLogger("alsaniamcp.imports")


class ImportError(Exception):
    """Custom import error with enhanced information"""
    
    def __init__(self, module_name: str, error: Exception, suggestions: List[str] = None):
        self.module_name = module_name
        self.original_error = error
        self.suggestions = suggestions or []
        
        message = f"Failed to import '{module_name}': {error}"
        if self.suggestions:
            message += f"\nSuggestions: {', '.join(self.suggestions)}"
        
        super().__init__(message)


class ImportManager:
    """Centralized import management with error handling and recovery"""
    
    def __init__(self):
        self._import_cache: Dict[str, Any] = {}
        self._failed_imports: Dict[str, ImportError] = {}
        self._import_aliases: Dict[str, str] = {}
        self._optional_imports: Dict[str, Any] = {}
        
        # Setup absolute import paths
        self._setup_import_paths()
        
        # Common import aliases
        self._setup_aliases()
    
    def _setup_import_paths(self) -> None:
        """Setup absolute import paths for the project"""
        # Get project root
        project_root = Path(__file__).parent.parent.parent
        backend_root = project_root / "backend"
        
        # Add to Python path if not already present
        paths_to_add = [
            str(project_root),
            str(backend_root),
            str(backend_root / "core"),
            str(project_root / "echo_core"),
            str(project_root / "snapshot_manager")
        ]
        
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)
                logger.debug(f"Added to Python path: {path}")
    
    def _setup_aliases(self) -> None:
        """Setup common import aliases for backward compatibility"""
        self._import_aliases.update({
            # Legacy imports
            'auth.api_keys': 'backend.core.auth',
            'core.persistence': 'backend.core.persistence',
            'core.agents': 'backend.core.agents',
            'core.snapshots': 'backend.core.snapshots',
            'core.embeddings': 'backend.core.embeddings',
            'core.openai_compat': 'backend.core.openai_compat',
            
            # Agent imports
            'agents.scribe.scribe_agent': 'backend.agents.scribe.agent',
            'agents.sentinel.sentinel': 'backend.agents.sentinel.agent',
            'agents.cypher.cypher_agent': 'backend.agents.cypher.agent',
            
            # Memory imports
            'memory.storage': 'backend.core.memory.storage',
            'memory.vector_store': 'backend.core.memory.vector_store',
            
            # Config imports
            'config.config': 'backend.core.config.config'
        })
    
    def safe_import(self, module_name: str, 
                   fallback: Any = None,
                   required: bool = True,
                   alias: Optional[str] = None) -> Any:
        """
        Safely import a module with error handling and fallback options
        
        Args:
            module_name: Name of module to import
            fallback: Fallback value if import fails
            required: Whether import is required (raises error if True)
            alias: Alternative module name to try
            
        Returns:
            Imported module or fallback value
        """
        # Check cache first
        cache_key = alias or module_name
        if cache_key in self._import_cache:
            return self._import_cache[cache_key]
        
        # Check if we've already failed to import this
        if cache_key in self._failed_imports and required:
            raise self._failed_imports[cache_key]
        
        # Try to resolve alias
        actual_module_name = self._import_aliases.get(module_name, module_name)
        if alias:
            actual_module_name = self._import_aliases.get(alias, alias)
        
        try:
            # Attempt import
            module = importlib.import_module(actual_module_name)
            self._import_cache[cache_key] = module
            logger.debug(f"Successfully imported: {actual_module_name}")
            return module
            
        except ImportError as e:
            # Try alternative module names
            alternatives = self._get_import_alternatives(module_name)
            
            for alt_name in alternatives:
                try:
                    module = importlib.import_module(alt_name)
                    self._import_cache[cache_key] = module
                    logger.info(f"Imported alternative: {alt_name} for {module_name}")
                    return module
                except ImportError:
                    continue
            
            # Handle import failure
            import_error = ImportError(
                module_name=actual_module_name,
                error=e,
                suggestions=alternatives
            )
            
            self._failed_imports[cache_key] = import_error
            
            if required:
                logger.error(f"Required import failed: {actual_module_name}")
                raise import_error
            else:
                logger.warning(f"Optional import failed: {actual_module_name}, using fallback")
                self._optional_imports[cache_key] = fallback
                return fallback
    
    def safe_import_from(self, module_name: str, 
                        item_names: Union[str, List[str]],
                        fallback: Any = None,
                        required: bool = True) -> Union[Any, Dict[str, Any]]:
        """
        Safely import specific items from a module
        
        Args:
            module_name: Name of module to import from
            item_names: Name(s) of items to import
            fallback: Fallback value if import fails
            required: Whether import is required
            
        Returns:
            Imported item(s) or fallback value
        """
        try:
            module = self.safe_import(module_name, required=required)
            if module is None:
                return fallback
            
            if isinstance(item_names, str):
                # Single item
                if hasattr(module, item_names):
                    return getattr(module, item_names)
                else:
                    if required:
                        raise AttributeError(f"Module '{module_name}' has no attribute '{item_names}'")
                    return fallback
            else:
                # Multiple items
                result = {}
                for item_name in item_names:
                    if hasattr(module, item_name):
                        result[item_name] = getattr(module, item_name)
                    elif required:
                        raise AttributeError(f"Module '{module_name}' has no attribute '{item_name}'")
                    else:
                        result[item_name] = fallback
                return result
                
        except Exception as e:
            if required:
                raise ImportError(module_name, e)
            return fallback
    
    def _get_import_alternatives(self, module_name: str) -> List[str]:
        """Get alternative module names to try"""
        alternatives = []
        
        # Common patterns
        if module_name.startswith('core.'):
            alternatives.append(f"backend.{module_name}")
            alternatives.append(f"backend.core.{module_name[5:]}")
        
        if module_name.startswith('agents.'):
            alternatives.append(f"backend.{module_name}")
        
        if module_name.startswith('memory.'):
            alternatives.append(f"backend.core.{module_name}")
        
        if module_name.startswith('config.'):
            alternatives.append(f"backend.core.{module_name}")
        
        # Try without prefixes
        if '.' in module_name:
            parts = module_name.split('.')
            alternatives.append(parts[-1])  # Just the last part
        
        return alternatives
    
    def register_alias(self, alias: str, actual_module: str) -> None:
        """Register a module alias for backward compatibility"""
        self._import_aliases[alias] = actual_module
        logger.debug(f"Registered alias: {alias} -> {actual_module}")
    
    def preload_modules(self, module_names: List[str]) -> Dict[str, bool]:
        """Preload a list of modules and return success status"""
        results = {}
        
        for module_name in module_names:
            try:
                self.safe_import(module_name, required=False)
                results[module_name] = True
            except Exception as e:
                logger.warning(f"Failed to preload {module_name}: {e}")
                results[module_name] = False
        
        return results
    
    def get_import_status(self) -> Dict[str, Any]:
        """Get status of all imports"""
        return {
            'cached_imports': len(self._import_cache),
            'failed_imports': len(self._failed_imports),
            'optional_imports': len(self._optional_imports),
            'registered_aliases': len(self._import_aliases),
            'failed_modules': list(self._failed_imports.keys())
        }
    
    def clear_cache(self) -> None:
        """Clear import cache"""
        self._import_cache.clear()
        self._failed_imports.clear()
        self._optional_imports.clear()
        logger.info("Import cache cleared")


# Global import manager instance
_import_manager: Optional[ImportManager] = None


def get_import_manager() -> ImportManager:
    """Get the global import manager instance"""
    global _import_manager
    if _import_manager is None:
        _import_manager = ImportManager()
    return _import_manager


# Convenience functions
def safe_import(module_name: str, **kwargs) -> Any:
    """Convenience function for safe module import"""
    return get_import_manager().safe_import(module_name, **kwargs)


def safe_import_from(module_name: str, item_names: Union[str, List[str]], **kwargs) -> Any:
    """Convenience function for safe from-import"""
    return get_import_manager().safe_import_from(module_name, item_names, **kwargs)


def register_import_alias(alias: str, actual_module: str) -> None:
    """Convenience function to register import alias"""
    get_import_manager().register_alias(alias, actual_module)


# Common imports with fallbacks
def import_fastapi():
    """Import FastAPI with fallback"""
    return safe_import('fastapi', required=True)


def import_uvicorn():
    """Import Uvicorn with fallback"""
    return safe_import('uvicorn', required=True)


def import_psycopg2():
    """Import psycopg2 with fallback to psycopg2-binary"""
    try:
        return safe_import('psycopg2', required=True)
    except ImportError:
        return safe_import('psycopg2-binary', required=True)


def import_qdrant():
    """Import Qdrant client with fallback"""
    return safe_import('qdrant_client', required=False)


def import_redis():
    """Import Redis with fallback"""
    return safe_import('redis', required=False)


# Initialize import manager on module load
get_import_manager()
