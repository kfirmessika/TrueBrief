"""
Utility functions for the TrueBrief engine, like file I/O.
"""
import json
import os
import logging

def load_json_file(filepath, default_data=None):
    """
    Safely load a JSON file, creating it with default data if it doesn't exist.
    """
    # This allows us to pass in a default dict {} or list []
    if default_data is None:
        default_data = {}

    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    if not os.path.exists(filepath):
        # Save the default data to the new file
        save_json_file(filepath, default_data)
        return default_data

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.warning(f"Could not decode JSON from {filepath}. Returning default data.")
        return default_data

def save_json_file(filepath, data):
    """Safely save data to a JSON file."""
    # Create directory if path contains a directory
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

