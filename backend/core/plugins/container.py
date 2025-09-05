"""
Dependency Injection Container

Provides a service container for managing dependencies and
enabling loose coupling between components.
"""

import inspect
import logging
from typing import Any, Callable, Dict, Type, TypeVar, Union, get_type_hints
from threading import Lock
from .exceptions import ServiceResolutionError

logger = logging.getLogger("alsaniamcp.plugins.container")

T = TypeVar('T')


class ServiceLifetime:
    """Service lifetime management"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceDescriptor:
    """Describes how a service should be created and managed"""
    
    def __init__(self, service_type: Type, implementation: Union[Type, Callable],
                 lifetime: str = ServiceLifetime.TRANSIENT):
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.instance = None


class ServiceContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = Lock()
        self._building = set()  # Track services being built to prevent circular dependencies
        
        # Register self
        self.register_singleton(ServiceContainer, self)
    
    def register_singleton(self, service_type: Type[T], 
                          implementation: Union[Type[T], Callable[[], T]]) -> 'ServiceContainer':
        """Register a singleton service"""
        with self._lock:
            self._services[service_type] = ServiceDescriptor(
                service_type, implementation, ServiceLifetime.SINGLETON
            )
        logger.debug(f"Registered singleton service: {service_type.__name__}")
        return self
    
    def register_transient(self, service_type: Type[T],
                          implementation: Union[Type[T], Callable[[], T]]) -> 'ServiceContainer':
        """Register a transient service"""
        with self._lock:
            self._services[service_type] = ServiceDescriptor(
                service_type, implementation, ServiceLifetime.TRANSIENT
            )
        logger.debug(f"Registered transient service: {service_type.__name__}")
        return self
    
    def register_scoped(self, service_type: Type[T],
                       implementation: Union[Type[T], Callable[[], T]]) -> 'ServiceContainer':
        """Register a scoped service (per request/operation)"""
        with self._lock:
            self._services[service_type] = ServiceDescriptor(
                service_type, implementation, ServiceLifetime.SCOPED
            )
        logger.debug(f"Registered scoped service: {service_type.__name__}")
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'ServiceContainer':
        """Register a specific instance as a singleton"""
        with self._lock:
            self._singletons[service_type] = instance
            self._services[service_type] = ServiceDescriptor(
                service_type, lambda: instance, ServiceLifetime.SINGLETON
            )
        logger.debug(f"Registered instance for service: {service_type.__name__}")
        return self
    
    def register_factory(self, service_type: Type[T], 
                        factory: Callable[[], T]) -> 'ServiceContainer':
        """Register a factory function for creating service instances"""
        with self._lock:
            self._services[service_type] = ServiceDescriptor(
                service_type, factory, ServiceLifetime.TRANSIENT
            )
        logger.debug(f"Registered factory for service: {service_type.__name__}")
        return self
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance"""
        if service_type in self._building:
            raise ServiceResolutionError(
                f"Circular dependency detected while resolving {service_type.__name__}"
            )
        
        try:
            self._building.add(service_type)
            return self._resolve_internal(service_type)
        finally:
            self._building.discard(service_type)
    
    def _resolve_internal(self, service_type: Type[T]) -> T:
        """Internal service resolution logic"""
        # Check if service is registered
        if service_type not in self._services:
            raise ServiceResolutionError(
                f"Service {service_type.__name__} is not registered"
            )
        
        descriptor = self._services[service_type]
        
        # Handle singleton lifetime
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]
            
            instance = self._create_instance(descriptor)
            self._singletons[service_type] = instance
            return instance
        
        # Handle transient and scoped lifetimes
        return self._create_instance(descriptor)
    
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance from a service descriptor"""
        implementation = descriptor.implementation
        
        # If implementation is a callable (factory function)
        if callable(implementation) and not inspect.isclass(implementation):
            try:
                return implementation()
            except Exception as e:
                raise ServiceResolutionError(
                    f"Failed to create instance using factory for {descriptor.service_type.__name__}",
                    cause=e
                )
        
        # If implementation is a class, use dependency injection
        if inspect.isclass(implementation):
            return self._create_instance_with_injection(implementation)
        
        raise ServiceResolutionError(
            f"Invalid implementation type for {descriptor.service_type.__name__}"
        )
    
    def _create_instance_with_injection(self, cls: Type) -> Any:
        """Create an instance with constructor dependency injection"""
        try:
            # Get constructor signature
            signature = inspect.signature(cls.__init__)
            type_hints = get_type_hints(cls.__init__)
            
            # Resolve constructor parameters
            kwargs = {}
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Get parameter type from type hints
                param_type = type_hints.get(param_name)
                if param_type is None:
                    # Try to get type from annotation
                    param_type = param.annotation
                
                if param_type == inspect.Parameter.empty:
                    if param.default == inspect.Parameter.empty:
                        raise ServiceResolutionError(
                            f"Cannot resolve parameter '{param_name}' for {cls.__name__}: "
                            f"no type annotation and no default value"
                        )
                    continue  # Skip parameters with default values
                
                # Resolve the dependency
                try:
                    kwargs[param_name] = self.resolve(param_type)
                except ServiceResolutionError:
                    if param.default != inspect.Parameter.empty:
                        continue  # Use default value
                    raise
            
            # Create instance
            return cls(**kwargs)
            
        except Exception as e:
            raise ServiceResolutionError(
                f"Failed to create instance of {cls.__name__}",
                cause=e
            )
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered"""
        return service_type in self._services
    
    def get_registered_services(self) -> Dict[Type, ServiceDescriptor]:
        """Get all registered services"""
        return self._services.copy()
    
    def clear(self) -> None:
        """Clear all registered services and singletons"""
        with self._lock:
            self._services.clear()
            self._singletons.clear()
            self._building.clear()
            # Re-register self
            self.register_singleton(ServiceContainer, self)
        logger.info("Service container cleared")
    
    def create_scope(self) -> 'ScopedServiceContainer':
        """Create a scoped container for request/operation-specific services"""
        return ScopedServiceContainer(self)


class ScopedServiceContainer:
    """Scoped service container for request/operation-specific services"""
    
    def __init__(self, parent: ServiceContainer):
        self._parent = parent
        self._scoped_instances: Dict[Type, Any] = {}
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance within this scope"""
        if service_type not in self._parent._services:
            return self._parent.resolve(service_type)
        
        descriptor = self._parent._services[service_type]
        
        # Handle scoped services
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]
            
            instance = self._parent._create_instance(descriptor)
            self._scoped_instances[service_type] = instance
            return instance
        
        # Delegate to parent for singleton and transient services
        return self._parent.resolve(service_type)
    
    def dispose(self) -> None:
        """Dispose of scoped instances"""
        for instance in self._scoped_instances.values():
            if hasattr(instance, 'dispose'):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.warning(f"Error disposing scoped instance: {e}")
        
        self._scoped_instances.clear()
