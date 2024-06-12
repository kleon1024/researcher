import time
from functools import wraps

def retry(max_retries=3, delay=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    print(f"Attempt {retries}/{max_retries} failed with error: {e}")
                    if retries == max_retries:
                        print(f"Maximum retries ({max_retries}) reached. Aborting.")
                        raise e
                    time.sleep(delay)
                    print(f"Retrying in {delay} seconds...")
        return wrapper
    return decorator