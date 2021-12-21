import csv
import json
import re
import os
import socket
import traceback
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep


def is_main():
    return __name__ == "__main__"


def tool_nac_check():
    print("\033[H\033[J", end="")
    default_path = "D:/Downloads/cisco-tools-csv.csv"
    csv_path = default_path
    while True:
        csv_file_is_good, csv_path = check_for_csv_file(csv_path)
        if csv_file_is_good is True:
            print("CSV found. Continuing to check CSV content...")
            break
        elif csv_file_is_good is False:
            continue
    dict_all_switches = {}
    while True:
        csv_entries_are_valid, dict_all_switches = read_csv(csv_path)
        if csv_entries_are_valid is True:
            print("All CSV entries are valid. Continuing to check SSH reachability on Port 22...")
            break
        elif csv_entries_are_valid is False:
            continue
    multithread_port_check(dict_all_switches)


def check_for_csv_file(csv_path):
    try:
        size = os.path.getsize(csv_path)
        if size > 82:
            return True, csv_path
        else:
            print("File was found, but seems to be unedited.")
            print("Press enter to continue or enter absolute path to edited CSV.")
            user_path = input("[ENTER]/CSV Path: ")
            if user_path == "":
                return True, csv_path
            else:
                return False, user_path
    except FileNotFoundError:
        print("CSV Template could not be found. Please enter absolute path.")
        user_path = input("CSV Path: ")
        return False, user_path
    except Exception:
        traceback.print_exc()
        return False


def read_csv(csv_path):
    with open(csv_path, mode='r') as csv_switch_file:
        line_count = 0
        line_in_csv = 1
        dict_all_switches = {}
        dict_wrong_ip_switches = {}
        dict_wrong_os_switches = {}
        # RegEx Pattern for IPv4 address from https://stackoverflow.com/a/36760050
        ip_re_pattern = r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$"
        os_re_pattern = r"\biosxe\b|\bios\b"
        csv_reader = csv.DictReader(csv_switch_file)
        for row in csv_reader:
            line_in_csv += 1
            line_count += 1
            # Add line number in csv to row
            row["line"] = line_in_csv
            # Fill up empty IP / OS entries
            if row["hostname"] == "":
                row["hostname"] = "No Hostname"
            if row["ip"] == "":
                row["ip"] = "No IP"
            if row["os"] == "":
                row["os"] = "No OS"
            # Validate IP and OS entries
            ip_valid_check = re.search(ip_re_pattern, row["ip"])
            os_valid_check = re.search(os_re_pattern, row["os"])
            # Get table entries in vars
            hostname = row["hostname"]
            ip = row["ip"]
            os = row["os"]
            if ip_valid_check is None:
                print(f"Error IP: Line {line_in_csv}, {hostname}. Faulty entry: {ip}.")
                line_hostname = row["hostname"]
                dict_wrong_ip_switches[line_hostname] = row
            if os_valid_check is None:
                print(f"Error OS: Line {line_in_csv}, {hostname}. Faulty entry: {os}.")
                line_hostname = row["hostname"]
                dict_wrong_os_switches[line_hostname] = row
            # Build dict with all switch entries
            line_ip = row["ip"]
            dict_all_switches[line_ip] = row
        quantity_wrong_ip_switches = len(dict_wrong_ip_switches)
        quantity_wrong_os_switches = len(dict_wrong_os_switches)
        if quantity_wrong_ip_switches == 0 and quantity_wrong_os_switches == 0:
            print(f"Processed {line_count} lines. Zero lines are faulty. Continuing to test SSH reachability...")
            return True, dict_all_switches
        elif quantity_wrong_ip_switches >= 1 and quantity_wrong_os_switches == 0:
            print(f"Processed {line_count} lines. {quantity_wrong_ip_switches} lines have wrong IP entries.")
            print("Please change the faulty lines and validate the file again by pressing enter.")
            return False
        elif quantity_wrong_ip_switches == 0 and quantity_wrong_os_switches >= 1:
            print(f"Processed {line_count} lines. {quantity_wrong_os_switches} lines have wrong OS entries.")
            print("Please change the faulty lines and validate the file again by pressing enter.")
            return False
        elif quantity_wrong_ip_switches >= 1 and quantity_wrong_os_switches >= 1:
            print(
                f"Processed {line_count} lines. {quantity_wrong_ip_switches} lines have wrong IP and {quantity_wrong_os_switches} lines have wrong OS entries.")
            print("Please change the faulty lines and validate the file again by pressing enter.")
            input("Validate again: [ENTER]")
            return False
        else:
            print("infinity loopi")
        # print(json.dumps(dict_all_switches))
        # print(len(dict_all_switches))
        print(json.dumps(dict_wrong_os_switches))
        print(json.dumps(dict_wrong_ip_switches))
        # print(f"Processed {line_count} lines. ")


def worker(i, stop_event, input_queue, output_queue):
    while not stop_event.is_set():
        try:
            ip, port = input_queue.get(block=True, timeout=1)
        except Empty:
            continue

        ssh_reachable = {}
        try:
            # TCP Socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Timeout in seconds
            socket.setdefaulttimeout(2.0)
            # Close socket
            result = sock.connect_ex((ip, port))
            if result == 0:
                # print("Port is open")
                ssh_reachable[ip] = True
            else:
                # print("Port is closed/filtered")
                ssh_reachable[ip] = False
            sock.close()
        except Exception as e:
            ssh_reachable[ip] = False
            print(e)

        output_queue.put(ssh_reachable)


def start_workers(num_workers):
    stop_event = Event()
    input_queue = Queue()
    output_queue = Queue()
    for i in range(num_workers):
        # print(f"Starting worker {i}")
        w = Thread(target=worker, args=(i, stop_event, input_queue, output_queue))
        w.daemon = True
        w.start()
    return stop_event, input_queue, output_queue


def multithread_port_check(dict_all_switches):
    port = 22
    stop_event, input_queue, output_queue = start_workers(num_workers=12)
    for value in dict_all_switches.values():
        ip = value["ip"]
        input_queue.put((ip, port))

    # Wait for the input queue to be emptied
    while not input_queue.empty():
        sleep(0.1)
    sleep(3)
    # Stop the workers
    stop_event.set()

    results = []
    # Wait for the output queue to be emptied
    while not output_queue.empty() and len(dict_all_switches) != len(results):
        try:
            element = output_queue.get(block=False)
        except Empty:
            pass
        else:
            results.append(element)

    print(results)


def menue():
    print("\nPlease choose the Tool:")
    print("1. NAC Check")
    print("2. Advanced show interface")
    tool_number = input("Tool number: ")
    if tool_number == "1":
        tool_nac_check()
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
    # csv_state = check_for_csv()
    # print(csv_state)
    # read_csv()
