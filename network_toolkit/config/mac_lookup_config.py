# -*- coding: UTF-8 -*-
import logging
from dataclasses import dataclass
from pathlib import Path
from ruamel.yaml import YAML

# Global variables
yaml = YAML(typ='safe')
yaml.indent(mapping=2, sequence=4)


@dataclass(frozen=True)
class MacLookupConfiguration:
    api_token_macvendors: str


def _open_and_read_config_file():
    path_to_config_yml = Path.cwd() / "configuration/global_config.yml"

    with open(path_to_config_yml, mode="r", encoding="utf-8") as config_yml:
        config_file = (yaml.load(config_yml))
        input_config = config_file["mac_address_lookup"]

    return input_config


def _create_input_config(input_config):
    mac_lookup_config = MacLookupConfiguration(input_config["api_token_macvendors"])
    logging.debug("Mac Address Lookup config got successfully loaded and parsed.")
    logging.debug(input_config)
    return mac_lookup_config


def _check_values_set(config_list):
    if config_list.api_token_macvendors is None:
        logging.critical("Mac Address Lookup config: API Token must be set in 'global_config.yml'.\n"
                         "To obtain a token you have to register @ https://macvendors.com/register")
        quit()


def load_mac_lookup_config():
    try:
        input_config = _open_and_read_config_file()
    except IOError:
        logging.error(f"Config File not found/accessible @ {Path.cwd() / 'configuration/global_config.yml'}")
        quit()

    input_config_obj = _create_input_config(input_config)
    _check_values_set(input_config_obj)
    return input_config_obj
