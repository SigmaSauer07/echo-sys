"""
Unit tests for the import management system

Tests the centralized import management, error handling,
and fallback mechanisms.
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from backend.core.imports import (
    ImportManager, ImportError as CustomImportError,
    safe_import, safe_import_from, get_import_manager,
    import_fastapi, import_uvicorn, import_psycopg2
)


class TestImportManager:
    """Test the ImportManager class"""
    
    @pytest.fixture
    def import_manager(self):
        """Create a fresh import manager for testing"""
        return ImportManager()
    
    def test_import_manager_initialization(self, import_manager):
        """Test import manager initialization"""
        assert import_manager._import_cache == {}
        assert import_manager._failed_imports == {}
        assert len(import_manager._import_aliases) > 0
        
        # Check that common aliases are registered
        assert 'core.auth' in import_manager._import_aliases
        assert 'agents.scribe.scribe_agent' in import_manager._import_aliases
    
    def test_safe_import_success(self, import_manager):
        """Test successful module import"""
        # Import a standard library module
        json_module = import_manager.safe_import('json')
        assert json_module is not None
        assert hasattr(json_module, 'loads')
        
        # Should be cached
        cached_module = import_manager.safe_import('json')
        assert cached_module is json_module
    
    def test_safe_import_failure_required(self, import_manager):
        """Test import failure with required=True"""
        with pytest.raises(CustomImportError) as exc_info:
            import_manager.safe_import('nonexistent_module_12345', required=True)
        
        assert 'nonexistent_module_12345' in str(exc_info.value)
        assert 'nonexistent_module_12345' in import_manager._failed_imports
    
    def test_safe_import_failure_optional(self, import_manager):
        """Test import failure with required=False"""
        fallback_value = "fallback"
        result = import_manager.safe_import(
            'nonexistent_module_12345', 
            fallback=fallback_value, 
            required=False
        )
        
        assert result == fallback_value
        assert 'nonexistent_module_12345' in import_manager._optional_imports
    
    def test_safe_import_with_alias(self, import_manager):
        """Test import with alias resolution"""
        # Register a test alias
        import_manager.register_alias('test_alias', 'json')
        
        # Import using alias
        result = import_manager.safe_import('test_alias')
        assert result is not None
        assert hasattr(result, 'loads')
    
    def test_safe_import_from_success(self, import_manager):
        """Test successful from-import"""
        # Import single item
        loads_func = import_manager.safe_import_from('json', 'loads')
        assert callable(loads_func)
        
        # Import multiple items
        items = import_manager.safe_import_from('json', ['loads', 'dumps'])
        assert 'loads' in items
        assert 'dumps' in items
        assert callable(items['loads'])
        assert callable(items['dumps'])
    
    def test_safe_import_from_missing_attribute(self, import_manager):
        """Test from-import with missing attribute"""
        with pytest.raises(AttributeError):
            import_manager.safe_import_from('json', 'nonexistent_function', required=True)
        
        # With fallback
        result = import_manager.safe_import_from(
            'json', 'nonexistent_function', 
            fallback='fallback', required=False
        )
        assert result == 'fallback'
    
    def test_import_alternatives(self, import_manager):
        """Test import alternative resolution"""
        alternatives = import_manager._get_import_alternatives('core.auth')
        
        assert 'backend.core.auth' in alternatives
        assert 'backend.core.auth' in alternatives
    
    def test_register_alias(self, import_manager):
        """Test alias registration"""
        import_manager.register_alias('my_alias', 'json')
        assert import_manager._import_aliases['my_alias'] == 'json'
    
    def test_preload_modules(self, import_manager):
        """Test module preloading"""
        modules = ['json', 'os', 'nonexistent_module_12345']
        results = import_manager.preload_modules(modules)
        
        assert results['json'] is True
        assert results['os'] is True
        assert results['nonexistent_module_12345'] is False
    
    def test_import_status(self, import_manager):
        """Test import status reporting"""
        # Import some modules
        import_manager.safe_import('json')
        import_manager.safe_import('nonexistent_module', required=False, fallback=None)
        
        status = import_manager.get_import_status()
        
        assert status['cached_imports'] >= 1
        assert status['optional_imports'] >= 1
        assert isinstance(status['failed_modules'], list)
    
    def test_clear_cache(self, import_manager):
        """Test cache clearing"""
        # Import and cache a module
        import_manager.safe_import('json')
        assert len(import_manager._import_cache) > 0
        
        # Clear cache
        import_manager.clear_cache()
        assert len(import_manager._import_cache) == 0
        assert len(import_manager._failed_imports) == 0


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_safe_import_function(self):
        """Test safe_import convenience function"""
        result = safe_import('json')
        assert result is not None
        assert hasattr(result, 'loads')
    
    def test_safe_import_from_function(self):
        """Test safe_import_from convenience function"""
        loads_func = safe_import_from('json', 'loads')
        assert callable(loads_func)
    
    def test_get_import_manager_singleton(self):
        """Test import manager singleton"""
        manager1 = get_import_manager()
        manager2 = get_import_manager()
        assert manager1 is manager2
    
    @patch('backend.core.imports.safe_import')
    def test_import_fastapi(self, mock_safe_import):
        """Test FastAPI import helper"""
        mock_fastapi = Mock()
        mock_safe_import.return_value = mock_fastapi
        
        result = import_fastapi()
        
        mock_safe_import.assert_called_once_with('fastapi', required=True)
        assert result is mock_fastapi
    
    @patch('backend.core.imports.safe_import')
    def test_import_uvicorn(self, mock_safe_import):
        """Test Uvicorn import helper"""
        mock_uvicorn = Mock()
        mock_safe_import.return_value = mock_uvicorn
        
        result = import_uvicorn()
        
        mock_safe_import.assert_called_once_with('uvicorn', required=True)
        assert result is mock_uvicorn
    
    @patch('backend.core.imports.safe_import')
    def test_import_psycopg2_success(self, mock_safe_import):
        """Test psycopg2 import success"""
        mock_psycopg2 = Mock()
        mock_safe_import.return_value = mock_psycopg2
        
        result = import_psycopg2()
        
        mock_safe_import.assert_called_once_with('psycopg2', required=True)
        assert result is mock_psycopg2
    
    @patch('backend.core.imports.safe_import')
    def test_import_psycopg2_fallback(self, mock_safe_import):
        """Test psycopg2 import with fallback to psycopg2-binary"""
        mock_psycopg2_binary = Mock()
        
        # First call fails, second succeeds
        mock_safe_import.side_effect = [CustomImportError('psycopg2', ImportError()), mock_psycopg2_binary]
        
        result = import_psycopg2()
        
        assert mock_safe_import.call_count == 2
        assert result is mock_psycopg2_binary


class TestImportErrorHandling:
    """Test import error handling and recovery"""
    
    def test_custom_import_error(self):
        """Test custom ImportError class"""
        original_error = ImportError("Module not found")
        suggestions = ["try installing package", "check spelling"]
        
        error = CustomImportError("test_module", original_error, suggestions)
        
        assert error.module_name == "test_module"
        assert error.original_error is original_error
        assert error.suggestions == suggestions
        assert "test_module" in str(error)
        assert "try installing package" in str(error)
    
    @patch('backend.core.imports.importlib.import_module')
    def test_import_with_module_not_found(self, mock_import):
        """Test handling of ModuleNotFoundError"""
        mock_import.side_effect = ModuleNotFoundError("No module named 'test_module'")
        
        import_manager = ImportManager()
        
        with pytest.raises(CustomImportError):
            import_manager.safe_import('test_module', required=True)
    
    @patch('backend.core.imports.importlib.import_module')
    def test_import_with_generic_error(self, mock_import):
        """Test handling of generic import errors"""
        mock_import.side_effect = Exception("Generic error")
        
        import_manager = ImportManager()
        
        with pytest.raises(CustomImportError):
            import_manager.safe_import('test_module', required=True)
    
    def test_import_recovery_with_alternatives(self):
        """Test import recovery using alternative module names"""
        import_manager = ImportManager()
        
        # This should try alternatives and eventually succeed with 'os'
        with patch.object(import_manager, '_get_import_alternatives', return_value=['os']):
            result = import_manager.safe_import('nonexistent.module')
            assert result is not None
            assert hasattr(result, 'path')  # os module has path attribute


class TestPathManagement:
    """Test Python path management"""
    
    def test_path_setup(self):
        """Test that import paths are properly set up"""
        import_manager = ImportManager()
        
        # Check that backend paths are in sys.path
        backend_paths = [path for path in sys.path if 'backend' in path]
        assert len(backend_paths) > 0
    
    def test_project_root_detection(self):
        """Test project root detection"""
        import_manager = ImportManager()
        
        # The import manager should add project-related paths
        project_paths = [path for path in sys.path if 'alsaniamcp' in path or 'backend' in path]
        assert len(project_paths) > 0
