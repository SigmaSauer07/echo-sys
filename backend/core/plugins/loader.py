import importlib, pkgutil
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

def load_plugins(app: FastAPI):
    import backend.plugins
    logger.info("Starting plugin loading...")
    for _, module_name, _ in pkgutil.iter_modules(backend.plugins.__path__):
        logger.info(f"Found plugin module: {module_name}")
        if module_name in ['loader', '__pycache__']:
            logger.info(f"Skipping {module_name}")
            continue
        try:
            module = importlib.import_module(f"backend.plugins.{module_name}")
            logger.info(f"Imported module: {module_name}")
            if hasattr(module, "register"):
                logger.info(f"Registering plugin: {module_name}")
                module.register(app)
                logger.info(f"Successfully registered plugin: {module_name}")
            else:
                logger.warning(f"Module {module_name} has no register function")
        except Exception as e:
            logger.error(f"Error loading plugin {module_name}: {e}")
    logger.info("Plugin loading completed")
