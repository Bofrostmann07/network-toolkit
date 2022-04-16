# -*- coding: UTF-8 -*-
from ruamel.yaml import YAML
from dataclasses import dataclass
import logging
import getpass
from pathlib import Path

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


@dataclass(frozen=True)
class ToolConfiguration:
    input_file: str
    output_needs_parse: bool
    parse_pattern: str
    path_raw_output: str
    path_results: str


def select_config_file(tool_name):
    path_to_global_config_yml = Path.cwd() / "configuration/global_config.yml"
    path_to_tool_config_yml = Path.cwd() / "configuration/tool_config.yml"
    if tool_name == "global":
        path_to_config_yml = path_to_global_config_yml
    else:
        path_to_config_yml = path_to_tool_config_yml
    return path_to_config_yml


def check_if_config_yml_exists(path_to_config):
    try:
        with open(path_to_config, mode="r", encoding="utf-8"):
            logging.debug("Config File found.")
    except IOError:
        logging.error(f"Config File not found/accessible @ {path_to_config}")
        quit()


def open_and_read_config_file(path_to_config, tool_name):
    with open(path_to_config) as config_yml:
        config_file = (yaml.load(config_yml))
    if tool_name == "global":
        config_data = build_global_config(config_file)
    else:
        config_data = config_file[tool_name]
    return config_data


def build_global_config(config_file):
    user_config = config_file["user_config"]
    default_config = config_file["default_config"]
    user_config = check_if_username_is_set_in_config_file(user_config)
    user_config = check_if_password_is_set_in_config_file(user_config)
    combined_config = combine_user_config_and_default_config(user_config, default_config)
    return combined_config


def check_if_username_is_set_in_config_file(user_config):
    if user_config["ssh_username"] is None:
        logging.error("No username is set. Edit 'global_config.yml' or enter it now.")
        username = input("Username: ")
        while username == "":
            logging.error("Username cant be empty.")
            username = input("Username: ")
        user_config["ssh_username"] = username
    return user_config


def check_if_password_is_set_in_config_file(user_config):
    if user_config["ssh_password"] is None:
        logging.error("No password is set. Edit 'global_config.yml' or enter it now.")
        password = getpass.getpass("Password: ")
        while password == "":
            logging.error("Password cant be empty.")
            password = getpass.getpass("Password: ")
        user_config["ssh_password"] = password
    return user_config


def combine_user_config_and_default_config(user_config, default_config):
    combined_config = default_config
    for key, value in user_config.items():
        if value is not None:
            combined_config[key] = value
    return combined_config


def select_class_to_create_config(tool_name, config_value):
    if tool_name == "global":
        config_obj = create_global_config(config_value)
    else:
        config_obj = create_interface_eth_config(config_value)
    return config_obj


def create_global_config(config_value):
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


def create_interface_eth_config(config_values):
    tool_config = ToolConfiguration(config_values["input_file"],
                                    config_values["output_needs_parse"],
                                    config_values["parse_pattern"],
                                    config_values["path_raw_output"],
                                    config_values["path_results"])
    logging.debug("'tool_config.yml' got successfully loaded and parsed.")
    logging.debug(tool_config)
    return tool_config


def wrapper_load_config(tool_name):
    path_to_config = select_config_file(tool_name)
    check_if_config_yml_exists(path_to_config)
    config_list = open_and_read_config_file(path_to_config, tool_name)
    config = select_class_to_create_config(tool_name, config_list)
    return config
