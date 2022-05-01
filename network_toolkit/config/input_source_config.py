# -*- coding: UTF-8 -*-
import logging
from dataclasses import dataclass
from pathlib import Path
from ruamel.yaml import YAML

import network_toolkit.config as config

# Global variables
yaml = YAML(typ='safe')
yaml.indent(mapping=2, sequence=4)


@dataclass(frozen=True)
class PrimeConfiguration:
    username: str
    password: str
    address: str
    group: str


def _open_and_read_config_file():
    path_to_config_yml = Path.cwd() / "configuration/global_config.yml"

    with open(path_to_config_yml, mode="r", encoding="utf-8") as config_yml:
        config_file = (yaml.load(config_yml))

    if config.GLOBAL_CONFIG.input_source == "prime":
        input_config = config_file["prime_config"]

    return input_config


def _create_input_config(input_config):
    opt_config = []
    if config.GLOBAL_CONFIG.input_source == "prime":
        opt_config = PrimeConfiguration(input_config["username"],
                                        input_config["password"],
                                        input_config["address"],
                                        input_config["group"], )
        logging.debug("Prime config got successfully loaded and parsed.")
        logging.debug(input_config)
    return opt_config


def _check_values_set(config_list):
    if config_list.username is None or config_list.password is None or config_list.address is None:
        logging.critical("Prime Config: Username, password and address must be set in 'global_config.yml'.")
        quit()


def load_input_config():
    try:
        input_config = _open_and_read_config_file()
    except IOError:
        logging.error(f"Config File not found/accessible @ {Path.cwd() / 'configuration/global_config.yml'}")
        quit()

    input_config_obj = _create_input_config(input_config)
    _check_values_set(input_config_obj)
    return input_config_obj
