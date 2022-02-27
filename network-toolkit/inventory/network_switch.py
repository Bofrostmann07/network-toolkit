import logging
import re


class NetworkSwitch:
    def __init__(self, hostname, ip, os, reachable, line_number):
        self.hostname = hostname
        self.ip = ip
        self.os = os
        self.reachable = reachable
        self.line_number = line_number

        self.parse_error = ""
        self.interface_eth_config = {}
        # self.interface_vlan_config = ""

    def parse_cli_output(self, pattern, raw_cli_output):
        if raw_cli_output is None:
            self.parse_error = f"{self.ip} - Did not receive CLI output."
            logging.warning(self.parse_error)
            return

        re_pattern = re.compile(pattern, re.MULTILINE)
        parsed_cli_output = re_pattern.findall(raw_cli_output)

        if parsed_cli_output is None:
            self.parse_error = f"{self.ip} - RegEx capture didn't match anything."
            logging.warning(self.parse_error)
            return

        return parsed_cli_output

    def parse_interface_cli_output(self, raw_cli_output):
        interface_eth_config = self.parse_cli_output(r"^(interface.*)\n((?:.*\n)+?)!", raw_cli_output)

        for element in interface_eth_config:
            interface_name = element[0]
            interface_config = element[1]
            interface_config_list = interface_config.split("\n ")
            interface_config_list = [x.strip() for x in interface_config_list]  # Remove leading blanks
            if interface_name.startswith("interface Vlan"):  # Strip off VLAN interfaces
                continue
            self.interface_eth_config[interface_name] = interface_config_list

    def parse_vlan_cli_output(self, raw_cli_output):
        self.vlan_eth_config = self.parse_cli_output(r"...", raw_cli_output)