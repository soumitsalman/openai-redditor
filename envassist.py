import os

env_file = ".env"

def load_env(path: str = None):
    if path != None:
        env_file = path

def load_variables():
    if os.path.exists(env_file):
        with open(env_file, 'r') as file:
            for line in file:
                key, val = map(str.strip, line.split('='))
                os.environ[key] = val

load_variables()