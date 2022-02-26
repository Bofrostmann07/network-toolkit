import logging
import re


class NetworkSwitch:
    def __init__(self, hostname, ip, os, reachable, line_number):
        self.hostname = hostname
        self.ip = ip
        self.os = os
        self.reachable = reachable
        self.line_number = line_number

        self.parse_status = False
        self.parse_error = ""
        self.interface_eth_config = ""
        self.interface_vlan_config = ""

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

        self.interface_eth_config = parsed_cli_output
        self.parse_status = True

    def config_to_dict(self):
        interface_eth_config = {}
        interface_vlan_config = {}
        final_interface_eth_config = {}
        final_interface_vlan_config = {}
        for element in self.interface_eth_config:
            interface_name = element[0]
            interface_config = element[1]
            interface_config_list = interface_config.split("\n ")
            interface_config_list = [x.strip() for x in interface_config_list]  # Remove leading blanks
            if interface_name.startswith("interface Vlan"):
                interface_vlan_config[interface_name] = interface_config_list
                final_interface_vlan_config[self.ip] = interface_vlan_config
            elif interface_name.startswith("interface"):
                interface_eth_config[interface_name] = interface_config_list
                final_interface_eth_config[self.ip] = interface_eth_config
        return final_interface_eth_config