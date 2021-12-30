# -*- coding: UTF-8 -*-
# from strictyaml import Map, Str, YAMLValidationError, load, Int, Bool
from ruamel.yaml import YAML
from dataclasses import dataclass
import logging
import getpass
from time import sleep

logging.basicConfig(
    # filename='test.log',
    # filemode='w',
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=logging.INFO
)

# Global variables
yaml = YAML(typ='safe')
path_to_config_yml = r"C:\Users\Roman\PycharmProjects\cisco-toolkit\config.yml"


@dataclass(frozen=True)
class GeneralConfiguration:
    __slots__ = ["ssh_username", "ssh_password", "path_to_csv_file", "ssh_port", "ssh_timeout",
                 "number_of_worker_threads", "debug_mode"]
    ssh_username: str
    ssh_password: str
    path_to_csv_file: str
    ssh_port: int
    ssh_timeout: int
    number_of_worker_threads: int
    debug_mode: bool


def check_if_config_yml_exists():
    try:
        with open(path_to_config_yml, mode="r", encoding="utf-8"):
            logging.debug("Config File found.")
    except IOError:
        logging.error(f"Config File 'config.yml' not found/accessible @ {path_to_config_yml}")
        sleep(5)
        quit()


# def read_config_yml(path):
#     schema = Map({"ssh_username": Str(), "ssh_password": Str(), "path_to_csv_file": Str(), "ssh_port": Int(),
#     "ssh_timeout": Int(), "number_of_worker_threads": Int(), "debug_mode": Bool})
#     print(load(path).data)
#     #print(person)


def open_and_read_config_file():
    with open(path_to_config_yml) as config_yml:
        list_of_documents = []
        all_documents = (yaml.load_all(config_yml))
        for documents in all_documents:
            list_of_documents.append(documents)
        user_config = list_of_documents[0]
        default_config = list_of_documents[1]
        logging.debug(user_config, default_config)
        return user_config, default_config


def check_if_username_is_set_in_config_file(user_config):
    if user_config["ssh_username"] is None:
        logging.error("No username is set. Edit 'config.yml' or enter it now.")
        username = input("Username: ")
        while username == "":
            logging.error("Username cant be empty.")
            username = input("Username: ")
        user_config["ssh_username"] = username
    return user_config


def check_if_password_is_set_in_config_file(user_config):
    if user_config["ssh_password"] is None:
        logging.error("No password is set. Edit 'config.yml' or enter it now.")
        password = getpass.getpass("Password: ")
        while password == "":
            logging.error("Password cant be empty.")
            password = getpass.getpass("Password: ")
        user_config["ssh_password"] = password
    return user_config


def combine_user_config_and_default_config(user_config, default_config):
    for key, value in user_config.items():
        if value is not None:
            default_config[key] = value
    return default_config


def generate_config_obj_with_combined_config(combined_config):
    general_config_as_obj = GeneralConfiguration(combined_config["ssh_username"],
                                                 combined_config["ssh_password"],
                                                 combined_config["path_to_csv_file"],
                                                 combined_config["ssh_port"],
                                                 combined_config["ssh_timeout"],
                                                 combined_config["number_of_worker_threads"],
                                                 combined_config["debug_mode"])
    logging.debug("'config.yml' got successfully loaded and parsed.")
    logging.debug("General Config:", general_config_as_obj)
    return general_config_as_obj


def wrapper_generate_global_config():
    check_if_config_yml_exists()
    user_config, default_config = open_and_read_config_file()
    user_config = check_if_username_is_set_in_config_file(user_config)
    user_config = check_if_password_is_set_in_config_file(user_config)
    combined_config = combine_user_config_and_default_config(user_config, default_config)
    global_config = generate_config_obj_with_combined_config(combined_config)
    return global_config
