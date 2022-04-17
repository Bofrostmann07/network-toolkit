# -*- coding: UTF-8 -*-
import logging
import csv
import re
import traceback
from pathlib import Path
import network_toolkit.config as config


def wrapper_validate_csv_path():
    logging.info("Starting to process and validate all prerequisites [0/5]")
    while True:
        path_to_csv = check_if_path_ending_with_file_extension(config.GLOBAL_CONFIG.path_to_csv_file)
        is_csv_file_existing, path_to_csv = check_if_csv_file_existing(path_to_csv)
        if is_csv_file_existing:
            break
    return path_to_csv


def ensure_file_extension(path_to_csv):
    """Checks if path contains a file extension, adds it if it does not"""
    file_extension_re_pattern = re.compile(r"^.*\.csv$")
    valid_check = file_extension_re_pattern.search(path_to_csv)

    if valid_check is None:
        logging.debug("File extension is missing. Adding '.csv' to file path.")
        return path_to_csv + ".csv"

    logging.debug("File extension exists.")
    return path_to_csv


def ensure_csv_exists(path_to_csv):
    """Makes sure the csv file exists, asks the user to provide another file if it does not"""
    while True:
        try:
            with open(path_to_csv):
                logging.info(f"CSV file found @ {path_to_csv} [1/5]")
                return path_to_csv
        except FileNotFoundError:
            logging.error(f"CSV file could not be found @ {path_to_csv}. Please enter absolute path.")
            path_to_csv = input("CSV Path: ")
            continue
        except PermissionError:
            logging.error(f"No Permission to access {path_to_csv}. Grant permission or enter diffrent absolute path.")
            print("Press [enter] to proceed after you granted permission.")
            path_to_csv = input("[ENTER]/CSV Path:")
            continue
        except Exception:
            traceback.print_exc()


def check_if_csv_file_edited(path_to_csv):
    file_size = Path(path_to_csv).stat().st_size
    if file_size > 81:
        logging.debug(f"CSV file seems to be edited. Size: {file_size}B")
        return
    else:
        logging.warning("CSV file seems to be unedited.")
        print("Press [enter] to check the CSV file once more, after you edited it.")
        print("Enter '[c]ontinue' to proceed.")
        user_input = input("[ENTER]/[c]:")
        if user_input == "":
            return check_if_csv_file_edited(path_to_csv)
        elif user_input == "c" or user_input == "continue":
            logging.info("Proceeding with unedited CSV file")
            return
        else:
            logging.error("Invalid Input")
            return check_if_csv_file_edited(path_to_csv)


def wrapper_check_csv_header(path_to_csv, header_template):
    while True:
        header_csv = extract_csv_header(path_to_csv)
        is_header_valid = check_if_csv_header_matches_template(header_csv, header_template)
        if is_header_valid:
            break


def extract_csv_header(path_to_csv):
    with open(path_to_csv, mode="r", encoding="utf-8") as csv_file:
        raw_csv_data = csv.DictReader(csv_file)
        header = raw_csv_data.fieldnames
        return header


def check_if_csv_header_matches_template(header_csv, header_template):
    if header_csv != header_template:
        is_header_valid = False
        logging.critical(f"CSV header is invalid.")
        print(f"Actual header: {header_csv}\n"
              f"Template header: {header_template}\n"
              f"Please correct header in line 1. If first entry looks weird, you need to convert csv to UTF-8 encoding. Press [enter] to recheck CSV file.")
        input("Press [enter] to recheck CSV file: ")
    else:
        is_header_valid = True
        logging.debug("CSV header is valid.")
    return is_header_valid


def get_csv_path_and_validate_header():
    path_to_csv = wrapper_validate_csv_path()
    check_if_csv_file_edited(path_to_csv)
    header_template = ['hostname', 'ip', 'os']  # TODO Template for tool 'Interface search'
    wrapper_check_csv_header(path_to_csv, header_template)
    return path_to_csv


def validate_switch_data(switch_data):
    # RegEx Pattern for IPv4 address from https://stackoverflow.com/a/36760050
    ip_re_pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    os_re_pattern = re.compile(r"\bcisco_xe\b|\bcisco_ios\b")
    ip_faulty_counter = 0
    os_faulty_counter = 0

    for switch_element in switch_data:
        if ip_re_pattern.search(switch_element.ip) is None:
            ip_faulty_counter += 1
            logging.error(f"Error IP: Line {switch_element.line_number}, {switch_element.hostname}. Faulty entry: {switch_element.ip}.")
            continue

        if os_re_pattern.search(switch_element.os) is None:
            os_faulty_counter += 1
            logging.error(f"Error OS: Line {switch_element.line_number}, {switch_element.hostname}. Faulty entry: {switch_element.os}.")
            continue

    if ip_faulty_counter > 0 or os_faulty_counter > 0:
        logging.error(f"Validated {len(switch_data)} lines. {ip_faulty_counter} lines have wrong IP and {os_faulty_counter} lines have wrong OS entries.")
        print("Please change the faulty lines and validate the file again by pressing enter.")
        input("[ENTER]")
        switch_data.clear()
        return False

    logging.info(f"Validated {len(switch_data)} lines. No lines are faulty. [3/5]")
    return True
