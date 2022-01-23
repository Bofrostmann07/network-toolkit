# -*- coding: UTF-8 -*-
import logging
import csv
import re
import traceback
from pathlib import Path

# Global variables
global_config = {}


def get_global_config():
    config = global_config
    return config


def wrapper_validate_csv_path():
    logging.info("Starting to process and validate all prerequisites [0/5]")
    while True:
        path_to_csv = check_if_path_ending_with_file_extension(global_config.path_to_csv_file)
        is_csv_file_existing, path_to_csv = check_if_csv_file_existing(path_to_csv)
        if is_csv_file_existing:
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
        logging.error(f"No Permission to access {path_to_csv}. Grant permission or enter diffrent absolute path.")
        print("Press [enter] to proceed after you granted permission.")
        user_entered_path_to_csv = input("[ENTER]/CSV Path:")
        return False, user_entered_path_to_csv
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
        raw_header = raw_csv_data.__next__()
        header = list(raw_header)
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


def get_csv_path_and_validate_header(config):
    set_global_config(config)
    path_to_csv = wrapper_validate_csv_path()
    check_if_csv_file_edited(path_to_csv)
    header_template = ['hostname', 'ip', 'os']  # Template for tool 'Interface search'
    wrapper_check_csv_header(path_to_csv, header_template)
    return path_to_csv


def set_global_config(config):
    global global_config
    global_config = config
    return
