# -*- coding: UTF-8 -*-
import csv
import re
import os
import socket
import traceback
import logging
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from alive_progress import alive_bar
from nac_check import ssh_connect
from dataclasses import dataclass

logging.basicConfig(
    # filename='test.log',
    # filemode='w',
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=logging.DEBUG
)

# Global variables
worker_threads = []

@dataclass
class NetworkSwitch:
    __slots__ = ["hostname", "ip", "os", "reachable", "line_number"]
    hostname: str
    ip: str
    os: str
    reachable: bool
    line_number: int


def is_main():
    return __name__ == "__main__"


def wrapper_validate_path_and_csv_file():
    path_to_csv_from_config = "D:/Downloads/cisco-tools-csv"
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
            logging.info(f"CSV file found @ {path_to_csv}")
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
    file_size = os.path.getsize(path_to_csv)
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
    logging.info(f"Read {len(switches_data)} rows from CSV.")
    return switches_data


def validate_raw_switch_data(raw_switch_data):
    # RegEx Pattern for IPv4 address from https://stackoverflow.com/a/36760050
    ip_re_pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    os_re_pattern = re.compile(r"\biosxe\b|\bios\b")
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
            logging.error(
                f"Error OS: Line {switch_element.line_number}, {switch_element.hostname}. Faulty entry: {switch_element.os}.")
    if ip_faulty_counter >= 1 or os_faulty_counter >= 1:
        logging.error(
            f"Validated {len(raw_switch_data)} lines. {ip_faulty_counter} lines have wrong IP and {os_faulty_counter} lines have wrong OS entries.")
        print("Please change the faulty lines and validate the file again by pressing enter.")
        input("[ENTER]")
        raw_switch_data.clear()
        return False
    else:
        logging.info(f"Validated {len(raw_switch_data)} lines. No lines are faulty.")
        return True


def fill_input_queue_start_worker_fill_output_queue(validated_switch_data):
    port = 22
    logging.info(f"Starting SSH reachability check on TCP port {port} for {len(validated_switch_data)} switches...")
    with alive_bar(total=len(validated_switch_data)) as bar:
        stop_event, input_queue, output_queue = start_workers(num_workers=12, bar=bar)
        for switch_element in validated_switch_data:
            if switch_element.reachable is False:
                ip = switch_element.ip
                input_queue.put((ip, port))

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


def worker(i, stop_event, input_queue, output_queue, bar):
    while not (stop_event.is_set() and input_queue.empty()):
        try:
            ip, port = input_queue.get(block=True, timeout=1)
        except Empty:
            continue
        ssh_reachable = {}
        reachable = False
        try:
            # TCP Socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Timeout in seconds
            socket.setdefaulttimeout(2.0)
            result = sock.connect_ex((ip, port))
            if result == 0:
                ssh_reachable[ip] = True
                reachable = True
            else:
                ssh_reachable[ip] = False
                reachable = False
            # Close TCP socket
            sock.close()
        except Exception as e:
            ssh_reachable[ip] = False
            reachable = False
            print(e)
        output_queue.put((ip, reachable))
        bar()


def start_workers(num_workers, bar):
    stop_event = Event()
    input_queue = Queue()
    output_queue = Queue()
    for i in range(num_workers):
        w = Thread(target=worker, args=(i, stop_event, input_queue, output_queue, bar))
        w.daemon = True
        w.start()
        worker_threads.append(w)
    return stop_event, input_queue, output_queue


def manipulate_NetworkSwitches_reachability(validated_switch_data, results_from_ssh_reachability_checker):
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
    return validated_switch_data


def wrapper_check_for_ssh_reachability(validated_switch_data):
    results_from_ssh_reachability_checker = fill_input_queue_start_worker_fill_output_queue(validated_switch_data)
    reachable_switch_data = manipulate_NetworkSwitches_reachability(validated_switch_data, results_from_ssh_reachability_checker)
    return reachable_switch_data


def orchestrator_create_switches_and_validate():
    validated_csv_file_path = wrapper_validate_path_and_csv_file()
    validated_switch_data = wrapper_read_csv_and_validate_switch_data(validated_csv_file_path)
    reachable_switch_data = wrapper_check_for_ssh_reachability(validated_switch_data)
    print("ssh check completed")


def menue():
    print("\nPlease choose the Tool:")
    print("1. NAC Check")
    print("2. Advanced show interface")
    tool_number = input("Tool number: ")
    if tool_number == "1":
        # Flush terminal
        print("\033[H\033[J", end="")
        logging.info("Tool: NAC Check started")
        orchestrator_create_switches_and_validate()

        # menue()
    elif tool_number == "2":
        print("Tool is not implemented yet.")
        menue()
    else:
        print(tool_number)
        print("Invalid input. You need to enter the number of the tool.")
        menue()


if is_main():
    menue()
