"""
Retry utility with exponential backoff for external API calls.
"""
import time
import functools
from logger.logging import get_logger
import asyncio

logger = get_logger(__name__)

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, fallback_value=None):
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds. Actual delay will be base_delay * (2 ^ attempt).
        fallback_value: Value to return if all retries fail, preventing exceptions from crashing the pipeline.
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_retries:
                            logger.error(f"Function '{func.__name__}' failed after {max_retries} retries. Error: {e}")
                            if fallback_value is not None:
                                return fallback_value
                            return {"error": True, "message": str(e)}
                        
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for '{func.__name__}': {e}. Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_retries:
                            logger.error(f"Function '{func.__name__}' failed after {max_retries} retries. Error: {e}")
                            if fallback_value is not None:
                                return fallback_value
                            return {"error": True, "message": str(e)}
                        
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for '{func.__name__}': {e}. Retrying in {delay} seconds...")
                        time.sleep(delay)
            return sync_wrapper
    return decorator
