import random
import time
import openai # TODO: remove

def retry_after_random_wait(
    min_wait :int, 
    max_wait: int, 
    max_retries: int,
    errors: tuple
):
    def decorator(func):    
        def wrapper(*args, **kwargs):
            try_counter = 0
            while try_counter < max_retries:
                try:
                    return func(*args, **kwargs)
                except errors as err:
                    try_counter += 1
                    print("Hit error: %s, RETRY number: %d" % (err, try_counter))
                    delay = random.randint(min_wait, max_wait)
                    time.sleep(delay)
                except Exception as e:
                    raise e
            raise Exception("maximum retry of %d reached" % max_retries)            
        return wrapper
    return decorator

def retry_after_func_wait(max_retries: int, errors: tuple, wait_time_func):
    def decorator(func):    
        def wrapper(*args, **kwargs):
            try_counter = 0
            while try_counter < max_retries:
                try:
                    return func(*args, **kwargs)
                except errors as err:
                    try_counter += 1
                    print("Hit error: %s, RETRY number: %d" % (err, try_counter))
                    delay = wait_time_func(err)
                    time.sleep(delay)
                except Exception as e:
                    raise e
            raise Exception("maximum retry of %d reached" % max_retries)            
        return wrapper
    return decorator