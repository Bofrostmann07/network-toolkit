# -*- coding: UTF-8 -*-
import getpass
import logging
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

# Global variables
yaml = YAML(typ='safe')
yaml.indent(mapping=2, sequence=4)


@dataclass(frozen=True)
class GlobalConfiguration:
    ssh_username: str
    ssh_password: str
    path_to_csv_file: str
    ssh_port: int
    ssh_timeout: int
    number_of_worker_threads: int
    debug_mode: bool
    skip_ssh_reachability_check: bool
    skip_ssh_authentication_check: bool


def _open_and_read_config_file():
    path_to_config_yml = Path.cwd() / "configuration/global_config.yml"

    with open(path_to_config_yml, mode="r", encoding="utf-8") as config_yml:
        config_file = (yaml.load(config_yml))

    global_config = config_file["global_config"]
    global_config = _check_if_username_is_set_in_config_file(global_config)
    global_config = _check_if_password_is_set_in_config_file(global_config)
    return global_config


def _check_if_username_is_set_in_config_file(global_config):
    if global_config["ssh_username"] is None:
        logging.error("No username is set. Edit 'global_config.yml' or enter it now.")
        username = input("Username: ")
        while username == "":
            logging.error("Username cant be empty.")
            username = input("Username: ")
        global_config["ssh_username"] = username
    return global_config


def _check_if_password_is_set_in_config_file(global_config):
    if global_config["ssh_password"] is None:
        logging.error("No password is set. Edit 'global_config.yml' or enter it now.")
        password = getpass.getpass("Password: ")
        while password == "":
            logging.error("Password cant be empty.")
            password = getpass.getpass("Password: ")
        global_config["ssh_password"] = password
    return global_config


def _create_global_config(config_value):
    global_config = GlobalConfiguration(config_value["ssh_username"],
                                        config_value["ssh_password"],
                                        config_value["path_to_csv_file"],
                                        config_value["ssh_port"],
                                        config_value["ssh_timeout"],
                                        config_value["number_of_worker_threads"],
                                        config_value["debug_mode"],
                                        config_value["skip_ssh_reachability_check"],
                                        config_value["skip_ssh_authentication_check"])
    logging.debug("'global_config.yml' got successfully loaded and parsed.")
    logging.debug(global_config)
    return global_config


def load_config():
    try:
        config_list = _open_and_read_config_file()
    except IOError:
        logging.error(f"Config File not found/accessible @ {Path.cwd() / 'configuration/global_config.yml'}")
        quit()

    config = _create_global_config(config_list)
    return config
def load_config(tool_name):
    """Load the config file for the given tool_name"""
    path_to_global_config_yml = Path.cwd() / "configuration/global_config.yml"
    path_to_tool_config_yml = Path.cwd() / "configuration/tool_config.yml"

    if tool_name == "global":
        config_file_path = path_to_global_config_yml
    else:
        config_file_path = path_to_tool_config_yml

    try:
        config_list = read_config_file(config_file_path, tool_name)
        config = select_class_to_create_config(tool_name, config_list)
        return config
    except IOError:
        logging.error(f"Config File not found/accessible @ {config_file_path}")
        quit()


GLOBAL_CONFIG = None
