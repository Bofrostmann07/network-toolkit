# -*- coding: UTF-8 -*-
import json
import logging
import signal
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
import re

import network_toolkit.config as config
from inventory import import_switches_from_csv, import_switches_from_prime
from inventory.validator.connection_validator import check_ssh_connection
from ssh_connection import run_show_command

logging.basicConfig(
    # filename='test.log',
    # filemode='w',
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=logging.INFO
)


def is_main():
    return __name__ == "__main__"


@dataclass(frozen=True)
class SearchMaskFlags:
    negative_search: bool
    strip_oobm: bool
    strip_uplink: bool


def fetch_switch_config():
    """Read config via ssh from switches defined in switchlist.csv"""
    if config.GLOBAL_CONFIG.input_source == "csv":
        switch_data = import_switches_from_csv()
    elif config.GLOBAL_CONFIG.input_source == "prime":
        import_switches_from_prime()

    switch_data = check_ssh_connection(switch_data)

    # TODO rewrite code to be more readable but less pythonic, quite sad :(
    # Filter out all switches that are not reachable
    reachable_switches = [x for x in switch_data if x.reachable]
    parsed_config = run_show_command(reachable_switches, "show derived-config | begin interface")
    logging.info("Finished fetching switch config.")
    return parsed_config


def save_parsed_cli_output_as_json(parsed_cli_output):
    """Stores the parsed cli output as json file and returns name of the file"""
    local_time = datetime.now()
    timestamp_url_safe = local_time.strftime("%Y-%m-%dT%H-%M-%S")
    str_file_path = "raw_output/interface_eth_config/" + timestamp_url_safe + ".json"
    file_path = Path.cwd() / str_file_path
    try:
        with open(file_path, "x") as json_file:
            json.dump(parsed_cli_output, json_file, indent=2)
            logging.info(f"Created result file @ {file_path}")
        return file_path
    except Exception:
        logging.error("Could not create result file")


def search_command_user_input():
    file_list = fetch_interface_config_files()

    if not file_list:
        logging.warning("Could not find a 'show run' file. Retrieving now!")
        switch_config = fetch_switch_config()
        config_path = save_parsed_cli_output_as_json(switch_config)
        file_list.append(config_path)

    logging.info(f"Found {len(file_list)} 'Interface Ethernet Config' files. The latest is from {file_list[-1].name.strip('.json')}.")
    print("[ENTER]:     Use latest file\n"
          "get:         Retrieve a new file now\n"
          "dir:         Show a list of all files\n"
          "[filename]:  Use the specified file")

    path_output_file = prompt_to_select_output_file(file_list)

    print(r"""    Usage: "[search mask]" [flags]
    Flags/Options: 
    --n     Turn to negative search mode. Will list all interfaces, which wont fit the search mask.
    --o     Tries to strip off out-of-band-management interfaces
    --u     Tries to strip off uplink interfaces
    Example: "switchport mode access" --n --u""")

    search_mask, search_mask_flags = prompt_for_search_command()
    search_result = search_in_output_file(path_output_file, search_mask, search_mask_flags)
    write_search_result(search_result, path_output_file, search_mask, search_mask_flags)


def fetch_interface_config_files():
    """Reads local directory and returns list of all stored config files"""
    path_raw_output = Path.cwd() / 'raw_output/interface_eth_config'

    try:
        all_files = list(path_raw_output.glob("**/*.json"))
        return all_files
    except FileNotFoundError:
        logging.error(f"Could not find {path_raw_output}")
        quit()


def prompt_to_select_output_file(filtered_file_list):
    file_path = "raw_output/interface_eth_config/"
    while True:
        user_input = input("Command:")
        if user_input == "" or user_input == "latest":
            logging.info(f"Using lastet file '{filtered_file_list[-1]}'")
            return filtered_file_list[-1]
        elif user_input in filtered_file_list:
            output_file_path = file_path + user_input
            absolute_file_path = Path.cwd() / output_file_path
            logging.info(f"Using file '{user_input}'")
            return absolute_file_path
        elif user_input == "get":
            switch_config = fetch_switch_config()
            config_path = save_parsed_cli_output_as_json(switch_config)
            return config_path
        elif user_input == "dir" or user_input == "ls":
            print(f"{[file_path.name for file_path in filtered_file_list]}")
        else:
            logging.warning(f"'{user_input}' was not found in directory.")


# TODO https://regex101.com/r/p50usT/3 RegEx vebessern
def prompt_for_search_command():
    negative_search = False
    strip_oobm = False
    strip_uplink = False

    search_mask = input("Search mask: ")
    mask_pattern = re.compile(r"^[\"'](.*)[\"']((?: |--\w+)*)", re.IGNORECASE)
    match_mask = mask_pattern.search(search_mask)

    if not match_mask:
        logging.warning("Search mask is empty or the quotation marks are missing")
        return prompt_for_search_command()

    if match_mask.group(2).find("--n") != -1:
        negative_search = True
    if match_mask.group(2).find("--o") != -1:
        strip_oobm = True
    if match_mask.group(2).find("--u") != -1:
        strip_uplink = True

    search_mask_flags = SearchMaskFlags(negative_search, strip_oobm, strip_uplink)
    logging.info(f"Mask: '{match_mask.group(1)}'. Set {search_mask_flags}.")
    return match_mask.group(1), search_mask_flags


def search_in_output_file(path_output_file, search_mask, search_mask_flags):
    with open(path_output_file, mode="r", encoding="utf-8") as serial_output_file:
        raw_int_eth_config = json.load(serial_output_file)

    search_result = {}
    uplink_int_pattern = re.compile(r"\d+/(?!0/)\d+/\d+$")
    for switch_ip, switch_config in raw_int_eth_config.items():
        interface_list = []
        for int_name, int_config in switch_config.get("eth_interfaces", {}).items():
            if search_mask_flags.strip_oobm and int_name.endswith(("FastEthernet0", "GigabitEthernet0/0")):
                continue
            if search_mask_flags.strip_uplink and uplink_int_pattern.search(int_name):
                print(int_name)
                continue
            if (search_mask in int_config) != search_mask_flags.negative_search:
                interface_list.append(int_name)
        keyname = switch_ip + " - " + switch_config.get("hostname", "No hostname")
        search_result[keyname] = interface_list
    return search_result


def write_search_result(search_result, path_output_file, search_mask, search_mask_flags):
    path_results = 'results/'
    local_time = datetime.now()
    timestamp_url_safe = (local_time.strftime("%Y-%m-%dT%H-%M-%S"))
    file_path = path_results + timestamp_url_safe + ".json"
    with open(file_path, "x") as json_file:
        json_file.write(f"This result is based on data @ {path_output_file}.\n"
                        f"Search mask: '{search_mask}'. Set {search_mask_flags}\n\n")
        json.dump(search_result, json_file, indent=2)
        json_file.write("\n\nThis result was created by 'https://github.com/Bofrostmann07/network-toolkit'.")
    logging.info(f"Wrote {file_path}. Search is done.")


def menue():
    while True:
        print("\nPlease choose the Tool by number:\n"
              "1 - Interface search\n"
              "2 - Advanced show interface\n"
              "3 - Meraki bulk edit\n"
              "99 - Show Config Values (global_config.yml)")
        tool_number = input("Tool number: ")
        if tool_number == "1":
            print("\033[H\033[J", end="")  # Flush terminal
            logging.info("Tool: 'Interface search' started")
            search_command_user_input()
        elif tool_number == "2":
            print("Tool is not implemented yet.")
        elif tool_number == "3":
            print("Tool will soon be available.")
        elif tool_number == "99":
            print(config.GLOBAL_CONFIG)
        else:
            print(tool_number)
            print("Invalid input. You need to enter the number of the tool.")


def check_all_prerequisites():
    config.GLOBAL_CONFIG = config.load_global_config()


def signal_handler(sig, frame):
    # Signal handler for processing CTRL+C
    logging.warning("Received keyboard interrupt. Stopping!")
    quit()


signal.signal(signal.SIGINT, signal_handler)

if is_main():
    check_all_prerequisites()
    menue()
