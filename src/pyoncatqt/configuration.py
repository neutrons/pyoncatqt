"""Module to load the the settings from the configuration file"""

import os
from configparser import ConfigParser

# configuration settings file path
CONFIG_PATH_FILE = "src/pyoncatqt/configuration.ini"


def get_data(section: str, name: str = None) -> dict | str | bool | None:
    """retrieves the configuration data for a variable with name"""
    # default file path location
    config_file_path = CONFIG_PATH_FILE
    if os.path.exists(config_file_path):
        config = ConfigParser()
        # parse the file
        config.read(config_file_path)
        try:
            if name:
                value = config[section][name]
                # in case of boolean string value cast it to bool
                if value in ("True", "False"):
                    return value == "True"
                # in case of None
                if value == "None":
                    return None
                return value
            return config[section]
        except KeyError:
            # requested section/field do not exist
            return None
    return None
