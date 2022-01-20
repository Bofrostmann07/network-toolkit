# -*- coding: UTF-8 -*-
import logging
import json
from load_global_config import wrapper_generate_global_config
from get_and_validate_switchlist_csv import orchestrator_create_switches_and_validate

logging.basicConfig(
    # filename='test.log',
    # filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=logging.DEBUG
)
global_config = {}


def is_main():
    return __name__ == "__main__"


def get_global_config():
    config = global_config
    return config


def tool_nac_check():
    config = get_global_config()
    switch_data = orchestrator_create_switches_and_validate(config)

    # TODO rewrite code to be more readable but less pythonic, quite sad :(
    # Filter out all switches that are not reachable
    reachable_switches = [x for x in switch_data if x.reachable]
    parsed_config = wrapper_send_show_command_to_switches(reachable_switches, "show DUMMY", config)
    logging.info("Finished fetching switch config.")
    menue()
    # search_for_nac_enabled(parsed_config)
    # cli_show_command = "show privilege"
    # test = ssh_connect_only_one_show_command(switch_data, cli_show_command)
    # print(test)


def read_dir_and_get_file_names():
    path = "raw_output/show_derived_config_interfaces/"
    try:
        all_files = os.listdir(path)
        return all_files
    except FileNotFoundError:
    else:
        logging.warning(f"{user_input} was not found in directory.")
        return prompt_to_select_output_file(filtered_file_list)


    else:






def search_for_nac_enabled(parsed_config):
    search_result = {}
    for switch_ip, switch_config in parsed_config.items():
        interface_list = []
        for interface, config in switch_config.items():
            if interface.startswith("interface") and "switchport access vlan 20" in config:
                interface_list.append(interface)
        search_result[switch_ip] = interface_list
    print(json.dumps(search_result))




def menue():
    print("\nPlease choose the Tool by number:")
    print("1 - Interface search")
    print("2 - Advanced show interface")
    print("99 - Show Config Values (global_config.yml)")
    tool_number = input("Tool number: ")
    if tool_number == "1":
        print("\033[H\033[J", end="")  # Flush terminal
        logging.info("Tool: 'Interface search' started")
        search_command_user_input()
    elif tool_number == "2":
        print("Tool is not implemented yet.")
        menue()
    elif tool_number == "99":
        print(global_config)
        menue()
    else:
        print(tool_number)
        print("Invalid input. You need to enter the number of the tool.")
        menue()


def check_all_prerequisites():
    global global_config
    global_config = wrapper_generate_global_config()
    return


if is_main():
    check_all_prerequisites()
    menue()
