# -*- coding: UTF-8 -*-
import csv
import re
import socket
import traceback
import logging
from pathlib import Path
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from alive_progress import alive_bar
from ssh_connection import ssh_connect_only_one_show_command_singlethreaded

# Global variables
worker_threads = []
global_config = {}


class NetworkSwitch:
    def __init__(self, hostname, ip, os, reachable, line_number):
        self.hostname = hostname
        self.ip = ip
        self.os = os
        self.reachable = reachable
        self.line_number = line_number

        self.parse_status = False
        self.parse_error = ""
        self.config = ""

    def parse_cli_output(self, raw_cli_output):
        if raw_cli_output is None:
            self.parse_error = f"{self.ip} - Did not receive CLI output."
            logging.warning(self.parse_error)
            return

        re_pattern = re.compile(r"^(interface.*)\n((?:.*\n)+?)!", re.MULTILINE)
        parsed_cli_output = re_pattern.findall(raw_cli_output)

        if parsed_cli_output is None:
            self.parse_error = f"{self.ip} - RegEx capture didnt match anything."
            logging.warning(self.parse_error)
            return

        self.config = parsed_cli_output
        self.parse_status = True

    def config_to_dict(self):
        parsed_interface_data = {}
        final_cli_output = {}
        for element in self.config:
            interface_name = element[0]
            interface_config = element[1]
            interface_config_list = interface_config.split("\n ")
            interface_config_list = [x.strip() for x in interface_config_list]  # Remove leading blanks
            parsed_interface_data[interface_name] = interface_config_list
        final_cli_output[self.ip] = parsed_interface_data
        return final_cli_output


def is_main():
    return __name__ == "__main__"


def get_global_config():
    config = global_config
    return config


def validate_path_and_csv_file():
    logging.info("Starting to process and validate all prerequisites [0/5]")
    path_to_csv_from_config = global_config.path_to_csv_file
    while True:
        path_to_csv = check_if_path_ending_with_file_extension(path_to_csv_from_config)
        is_csv_file_existing, path_to_csv = check_if_csv_file_existing(path_to_csv)
        if is_csv_file_existing:
            break
    while True:
        is_csv_file_edited = check_if_csv_file_edited(path_to_csv)
        if is_csv_file_edited:
            break
    return path_to_csv


def check_if_path_ending_with_file_extension(path_to_csv):
    file_extension_re_pattern = re.compile(r"^.*\.csv$")
    valid_check = re.search(file_extension_re_pattern, path_to_csv)
    if valid_check is None:
        edited_path_to_csv = path_to_csv + ".csv"
        logging.debug("File extension is missing. Adding '.csv' to file path.")
        return edited_path_to_csv
    else:
        logging.debug("File extension exists.")
        return path_to_csv


def check_if_csv_file_existing(path_to_csv):
    try:
        with open(path_to_csv):
            logging.info(f"CSV file found @ {path_to_csv} [1/5]")
            return True, path_to_csv
    except FileNotFoundError:
        logging.error(f"CSV file could not be found @ {path_to_csv}. Please enter absolute path.")
        user_entered_path_to_csv = input("CSV Path: ")
        return False, user_entered_path_to_csv
    except PermissionError:
        logging.error(f"No Permission to access {path_to_csv}. Grant permission or enter absolute path.")
        print("Press [enter] to proceed after you granted permission.")
        user_entered_path_to_csv = input("[ENTER]/CSV Path:")
        return False, user_entered_path_to_csv
    except Exception:
        traceback.print_exc()


def check_if_csv_file_edited(path_to_csv):
    file_size = Path(path_to_csv).stat().st_size
    if file_size > 81:
        logging.debug(f"CSV file seems to be edited. Size: {file_size}B")
        return True
    else:
        logging.warning("CSV file seems to be unedited.")
        print("Press [enter] to check the CSV file once more, after you edited it.")
        print("Enter '[c]ontinue' to proceed.")
        user_input = input("[ENTER]/[c]:")
        if user_input == "":
            return False
        elif user_input == "c" or user_input == "continue":
            logging.info("Proceeding with unedited CSV file")
            return True
        else:
            logging.error("Invalid Input")
            return check_if_csv_file_edited(path_to_csv)


def wrapper_read_csv_and_validate_switch_data(csv_file_path):
    while True:
        raw_switch_data = read_switch_data_from_csv(csv_file_path)
        is_data_valid = validate_raw_switch_data(raw_switch_data)
        if is_data_valid:
            break
    return raw_switch_data


def read_switch_data_from_csv(path_to_csv):
    switches_data = []
    with open(path_to_csv, mode="r", encoding="utf-8") as csv_switch_file:
        raw_csv_data = csv.DictReader(csv_switch_file)
        for line_number, row in enumerate(raw_csv_data, start=2):
            hostname = row.get("hostname") or "No Hostname"
            ip = row.get("ip") or "No IP"
            os = row.get("os") or "No OS"
            switch_data = NetworkSwitch(hostname, ip, os, False, line_number)
            switches_data.append(switch_data)
    logging.info(f"Read {len(switches_data)} rows from CSV. [2/5]")
    return switches_data


def validate_raw_switch_data(raw_switch_data):
    # RegEx Pattern for IPv4 address from https://stackoverflow.com/a/36760050
    ip_re_pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    os_re_pattern = re.compile(r"\bcisco_xe\b|\bcisco_ios\b")
    ip_faulty_counter = 0
    os_faulty_counter = 0
    for switch_element in raw_switch_data:
        ip_valid_check = re.search(ip_re_pattern, switch_element.ip)
        if ip_valid_check is None:
            ip_faulty_counter += 1
            logging.error(
                f"Error IP: Line {switch_element.line_number}, {switch_element.hostname}. Faulty entry: {switch_element.ip}.")
        os_valid_check = re.search(os_re_pattern, switch_element.os)
        if os_valid_check is None:
            os_faulty_counter += 1
            logging.error(f"Error OS: Line {switch_element.line_number}, {switch_element.hostname}. Faulty entry: {switch_element.os}.")
    if ip_faulty_counter >= 1 or os_faulty_counter >= 1:
        logging.error(f"Validated {len(raw_switch_data)} lines. {ip_faulty_counter} lines have wrong IP and {os_faulty_counter} lines have wrong OS entries.")
        print("Please change the faulty lines and validate the file again by pressing enter.")
        input("[ENTER]")
        raw_switch_data.clear()
        return False
    else:
        logging.info(f"Validated {len(raw_switch_data)} lines. No lines are faulty. [3/5]")
        return True


def fill_input_queue_start_worker_fill_output_queue(validated_switch_data):
    logging.info(f"Starting SSH reachability check on TCP port {global_config.ssh_port} for {len(validated_switch_data)} switches...")
    with alive_bar(total=len(validated_switch_data)) as bar:
        stop_event, input_queue, output_queue = start_workers(num_workers=global_config.number_of_worker_threads, bar=bar)
        for switch_element in validated_switch_data:
            if switch_element.reachable is False:
                ip = switch_element.ip
                input_queue.put((ip, global_config.ssh_port))

        # Wait for the input queue to be emptied
        while not input_queue.empty():
            sleep(0.1)
        # Stop the workers
        stop_event.set()
        # Wait until all worker threads are done
        for w in worker_threads:
            w.join()

    results = {}
    # Wait for the output queue to be emptied
    while not output_queue.empty() and len(validated_switch_data) != len(results):
        try:
            ip, reachable = output_queue.get(block=False)
        except Empty:
            pass
        else:
            results[ip] = reachable
    logging.debug(results)
    return results


def worker(stop_event, input_queue, output_queue, bar):
    while not (stop_event.is_set() and input_queue.empty()):
        try:
            ip, port = input_queue.get(block=True, timeout=1)
        except Empty:
            continue
        try:
            # Open TCP Socket for SSH reachability check
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                socket.setdefaulttimeout(global_config.ssh_timeout)
                result = sock.connect_ex((ip, port))
            if result == 0:
                reachable = True
            else:
                reachable = False
        except Exception as e:
            reachable = False
            print(e)
        output_queue.put((ip, reachable))
        bar()


def start_workers(num_workers, bar):
    stop_event = Event()
    input_queue = Queue()
    output_queue = Queue()
    for _ in range(num_workers):
        w = Thread(target=worker, args=(stop_event, input_queue, output_queue, bar))
        w.daemon = True
        w.start()
        worker_threads.append(w)
    return stop_event, input_queue, output_queue


def manipulate_networkswitches_reachability(validated_switch_data, results_from_ssh_reachability_checker):
    for switch_element in validated_switch_data:
        for result_ip, result_reachable in results_from_ssh_reachability_checker.items():
            if switch_element.ip == result_ip:
                switch_element.reachable = result_reachable
        if not switch_element.reachable:
            if switch_element.hostname == "No Hostname":
                logging.warning(f"{switch_element.ip} is not reachable")
            else:
                logging.warning(f"{switch_element.hostname} @ {switch_element.ip} is not reachable")
    logging.debug(validated_switch_data)
    logging.info("SSH reachability check is successfuly completed. [4/5]")
    return validated_switch_data


def check_if_ssh_login_is_working(switch_data):  # TODO this is super ugly, please clean me up in the future :(
    logging.info(f"Starting to check if SSH session gets established and user gets authenticated. Trying the first 3 switches...")
    # Expected output from 'show privilege' is 'Current privilege level is [priv level]'
    cli_show_command = "show privilege"
    priv_re_pattern = re.compile(r"\d{1,2}")
    counter_failed_logins = 0
    first_three_switches = switch_data[:2]
    config = get_global_config()
    raw_cli_output = ssh_connect_only_one_show_command_singlethreaded(first_three_switches, cli_show_command, config)
    for ip, cli_output in raw_cli_output.items():
        logging.debug(cli_output)
        login_success_check = (re.findall(priv_re_pattern, cli_output))
        if len(login_success_check) == 0:
            counter_failed_logins += 1
        elif int(login_success_check[0]) != 15:
            counter_failed_logins += 1
            logging.error(f"Insufficent privileges for {ip}: priv {login_success_check[0]}")
        else:
            logging.debug(f"Authencation successful for {ip}")

    if counter_failed_logins >= 1:
        logging.error(f"Authentication failed for {counter_failed_logins} switches")
        print(f"Check if user '{global_config.ssh_username}' is available, has privilege 15 and the password is correct. Press [enter] to retry.")
        input("[ENTER]")
        return check_if_ssh_login_is_working(first_three_switches)
    else:
        logging.info("SSH login check is successfuly completed. [5/5]")
        return


def wrapper_check_for_ssh_reachability(validated_switch_data):
    results_from_ssh_reachability_checker = fill_input_queue_start_worker_fill_output_queue(validated_switch_data)
    reachable_switch_data = manipulate_networkswitches_reachability(validated_switch_data, results_from_ssh_reachability_checker)
    return reachable_switch_data


def orchestrator_create_switches_and_validate(config):
    set_global_config(config)
    validated_csv_file_path = validate_path_and_csv_file()
    validated_switch_data = wrapper_read_csv_and_validate_switch_data(validated_csv_file_path)
    reachable_switch_data = wrapper_check_for_ssh_reachability(validated_switch_data)
    check_if_ssh_login_is_working(reachable_switch_data)
    logging.info("All prerequisites are fullfilled.")
    return reachable_switch_data


def set_global_config(config):
    global global_config
    global_config = config
    return