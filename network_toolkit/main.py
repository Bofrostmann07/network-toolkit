# -*- coding: UTF-8 -*-
import json
import logging
import os
import signal
from datetime import datetime
from pathlib import Path

import network_toolkit.config as config
from inventory import import_switches_from_csv
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


def fetch_switch_config():
    """Read config via ssh from switches defined in switchlist.csv"""
    switch_data = import_switches_from_csv()
    switch_data = check_ssh_connection(switch_data)

    # TODO rewrite code to be more readable but less pythonic, quite sad :(
    # Filter out all switches that are not reachable
    reachable_switches = [x for x in switch_data if x.reachable]
    parsed_config = run_show_command(reachable_switches, "show derived-config | begin interface")
    logging.info("Finished fetching switch config.")
    return parsed_config


def save_parsed_cli_output_as_json(parsed_cli_output):
    """Stores the parsed cli output as json file and returns path"""
    local_time = datetime.now()
    timestamp_url_safe = local_time.strftime("%Y-%m-%dT%H-%M-%S")
    file_path = "raw_output/interface_eth_config/" + timestamp_url_safe + ".json"
    try:
        with open(file_path, "x") as json_file:
            json.dump(parsed_cli_output, json_file, indent=2)
            logging.info(f"Created result file @ {file_path}")
        return file_path
    except Exception:
        logging.error("Could not create result file")


def search_command_user_input():
    all_files = fetch_interface_config_files()
    filtered_file_list = filter_json_files(all_files)

    if not filtered_file_list:
        logging.warning("Could not find a 'show run' file. Retrieving now!")
        switch_config = fetch_switch_config()
        config_path = save_parsed_cli_output_as_json(switch_config)
        filtered_file_list.append(config_path)

    logging.info(f"Found {len(filtered_file_list)} 'show run' files. The latest is from {filtered_file_list[-1].strip('.json')}.")
    print("To use the lastet file, press [enter]. To use another file, type the full filename.\n"
          "To list all 'sh run' files, use 'dir' or 'ls'. To retrieve 'show run' now, use 'get'.")

    path_output_file = prompt_to_select_output_file(filtered_file_list)

    print("You can use a 'negative search' to list all interfaces, which dont have the typed in command present, by appending '--n' at the end.\n"
          "For example: 'switchport mode access --n' will list all interfaces, which arent access ports.")

    search_command, positive_search = prompt_for_search_command()
    output_file = open_selected_output_file(path_output_file)
    search_result = search_in_output_file(output_file, search_command, positive_search)
    write_search_result(search_result, path_output_file, search_command, positive_search)


def fetch_interface_config_files():
    """Reads local directory and returns list of all stored config files"""
    path_raw_output = Path.cwd() / 'raw_output/interface_eth_config'
    try:
        all_files = os.listdir(path_raw_output)
        return all_files
    except FileNotFoundError:
        logging.error(f"Could not found {path_raw_output}")
        quit()


def filter_json_files(all_files):
    """Filter out all files that don't end on .json"""
    filtered_file_list = []
    for file_name in all_files:
        if file_name.endswith(".json"):
            filtered_file_list.append(file_name)

    return sorted(filtered_file_list)


def prompt_to_select_output_file(filtered_file_list):
    file_path = "raw_output/interface_eth_config/"  # TODO use path from class ToolConfiguration
    while True:
        user_input = input()
        if user_input == "" or user_input == "latest":
            output_file_path = file_path + filtered_file_list[-1]
            absolute_file_path = Path.cwd() / output_file_path
            logging.info(f"Using lastet file '{filtered_file_list[-1]}'")
            return absolute_file_path
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
            print(filtered_file_list)
        else:
            logging.warning(f"{user_input} was not found in directory.")


def prompt_user_when_no_shrun_file_exist():
    logging.warning("Could not find a 'show run' file.")
    user_input = input("Retrieve from switches now? [yes]/no: ")
    if user_input == "yes" or user_input == "":
        fetch_switch_config()
    else:
        print("\033[H\033[J", end="")  # Flush terminal


def prompt_for_search_command():
    raw_command = input("Enter search command: ")
    if raw_command == "":
        logging.warning("Search command cant be empty")
        return prompt_for_search_command()
    elif raw_command.endswith("--n"):
        positive_search = False
        search_command = raw_command.strip("--n")
        search_command = search_command.strip(" ")
    else:
        search_command = raw_command.strip(" ")
        positive_search = True
    logging.info(f"Command: '{search_command}'. Positive search: {positive_search}.")
    return search_command, positive_search


def open_selected_output_file(path_output_file):
    with open(path_output_file, mode="r", encoding="utf-8") as serial_output_file:
        output_file = json.load(serial_output_file)
    return output_file


def search_in_output_file(output_file, search_command, positive_search):
    search_result = {}
    for switch_ip, switch_config in output_file.items():
        interface_list = []
        for interface, int_config in switch_config.items():
            if interface.startswith("interface") and (search_command in int_config) == positive_search:
                interface_list.append(interface)
        search_result[switch_ip] = interface_list
    return search_result


def write_search_result(search_result, path_output_file, search_command, positive_search):
    path_results = 'results/'
    local_time = datetime.now()
    timestamp_url_safe = (local_time.strftime("%Y-%m-%dT%H-%M-%S"))
    file_path = path_results + timestamp_url_safe + ".json"
    with open(file_path, "x") as json_file:
        json_file.write(f"This result is based on data @ {path_output_file}.\n"
                        f"Search command: '{search_command}'. Positive Search: {positive_search}\n\n")
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
    config.GLOBAL_CONFIG = config.load_config()


def signal_handler(sig, frame):
    # Signal handler for processing CTRL+C
    logging.warning("Received keyboard interrupt. Stopping!")
    quit()


signal.signal(signal.SIGINT, signal_handler)

if is_main():
    check_all_prerequisites()
    menue()

    # search_interface_eth:
    # input_file: switchlist.csv
    # output_needs_parse: True
    # parse_pattern: ^ (interface. *)\n((?:.* \n) +?)!
    # path_raw_output: raw_output / interface_eth_config   ERLEDIGT
    # path_results: results / ERLEDIGT
