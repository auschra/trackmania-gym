import subprocess
import time
import logging

def get_window_id(name):
    result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', name],
                            capture_output=True, text=True, check=True)
    window_ids = result.stdout.strip().split('\n')
    for window_id in window_ids:
        result = subprocess.run(['xdotool', 'getwindowname', window_id],
                                capture_output=True, text=True, check=True)
        if result.stdout.strip() == name:
            logging.debug(f"Detected window {name}, id={window_id}")
            return window_id
    return None

def focus_window(window_id):
    try:
        subprocess.run(["wmctrl", "-i", "-a", window_id], check=True)
        time.sleep(0.1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to focus window {window_id}: {e}")
