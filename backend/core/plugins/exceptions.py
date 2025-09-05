"""
Plugin system exceptions

Defines custom exceptions for the plugin system to provide
clear error handling and debugging information.
"""


class PluginError(Exception):
    """Base exception for all plugin-related errors"""
    
    def __init__(self, message: str, plugin_name: str = None, cause: Exception = None):
        self.plugin_name = plugin_name
        self.cause = cause
        
        if plugin_name:
            message = f"[{plugin_name}] {message}"
        
        if cause:
            message = f"{message} (caused by: {cause})"
        
        super().__init__(message)


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load"""
    pass


class PluginDependencyError(PluginError):
    """Raised when plugin dependencies cannot be resolved"""
    
    def __init__(self, message: str, plugin_name: str = None, 
                 missing_dependencies: list = None, cause: Exception = None):
        self.missing_dependencies = missing_dependencies or []
        super().__init__(message, plugin_name, cause)


class PluginConfigError(PluginError):
    """Raised when plugin configuration is invalid"""
    
    def __init__(self, message: str, plugin_name: str = None, 
                 config_key: str = None, cause: Exception = None):
        self.config_key = config_key
        super().__init__(message, plugin_name, cause)


class PluginInitializationError(PluginError):
    """Raised when plugin initialization fails"""
    pass


class PluginStartupError(PluginError):
    """Raised when plugin startup fails"""
    pass


class PluginShutdownError(PluginError):
    """Raised when plugin shutdown fails"""
    pass


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found"""
    pass


class PluginAlreadyLoadedError(PluginError):
    """Raised when attempting to load an already loaded plugin"""
    pass


class PluginVersionConflictError(PluginError):
    """Raised when plugin version conflicts occur"""
    
    def __init__(self, message: str, plugin_name: str = None,
                 required_version: str = None, available_version: str = None,
                 cause: Exception = None):
        self.required_version = required_version
        self.available_version = available_version
        super().__init__(message, plugin_name, cause)


class PluginHotReloadError(PluginError):
    """Raised when hot-reload fails"""
    pass


class ServiceResolutionError(PluginError):
    """Raised when service dependency injection fails"""
    
    def __init__(self, message: str, service_type: str = None, cause: Exception = None):
        self.service_type = service_type
        super().__init__(message, cause=cause)
