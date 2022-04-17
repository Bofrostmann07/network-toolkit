# -*- coding: UTF-8 -*-
import csv
import logging
from .validator.csv_validator import get_csv_path_and_validate_header, validate_raw_csv_switch_data  # TODO . weg
from .network_switch import NetworkSwitch
import network_toolkit.config as config


def wrapper_read_csv_and_validate_switch_data(csv_file_path):
    while True:
        raw_switch_data = import_csv_fill_class_networkswitch(csv_file_path)
        is_data_valid = validate_raw_csv_switch_data(raw_switch_data)
        if is_data_valid:
            break
    return raw_switch_data


def import_csv_fill_class_networkswitch(path_to_csv):
    switches_data = []
    with open(path_to_csv, mode="r", encoding="utf-8") as csv_switch_file:
        raw_csv_data = csv.DictReader(csv_switch_file)
        for line_number, row in enumerate(raw_csv_data, start=2):
            hostname = row.get("hostname") or "No Hostname"
            ip = row.get("ip") or "No IP"
            os = row.get("os") or "No OS"
            switch_data = NetworkSwitch(hostname=hostname, ip=ip, os=os, reachable=False, line_number=line_number)
            switches_data.append(switch_data)
    logging.info(f"Read {len(switches_data)} rows from CSV. [2/5]")
    return switches_data


def import_switches_from_csv():
    validated_csv_file_path = get_csv_path_and_validate_header()
    validated_switch_data = wrapper_read_csv_and_validate_switch_data(validated_csv_file_path)
    # reachable_switch_data = check_ssh_connection(validated_switch_data)
    return validated_switch_data
