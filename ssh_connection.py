import logging
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException
from netmiko.ssh_exception import AuthenticationException
from ntc_templates.parse import parse_output
import traceback

logging.basicConfig(
    # filename='test.log',
    # filemode='w',
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=logging.INFO
)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)


def ssh_connect_only_one_show_command(switch_data, cli_show_command, global_config):
    output_data = {}
    logging.info(f"Starting to connect to {len(switch_data)} switches and enter show command...")
    for switch_element in switch_data:
        ssh_parameter = {
            'device_type': switch_element.os,
            'host': switch_element.ip,
            'username': global_config.ssh_username,
            'password': global_config.ssh_password,
            'port': global_config.ssh_port
        }
        try:
            with ConnectHandler(**ssh_parameter) as ssh_connection:
                # logging.debug(switch_element.ip)
                output = ssh_connection.send_command(cli_show_command)
                output_data[switch_element.ip] = output
        except AuthenticationException:
            logging.warning(f"Authentication failed for {switch_element.hostname} @ {switch_element.ip}")
            output_data[switch_element.ip] = "failed"
        except NetMikoTimeoutException:
            logging.warning(f"SSH timeout for {switch_element.hostname} @ {switch_element.ip}")
            output_data[switch_element.ip] = "timeout"
        except SSHException:
            logging.warning(
                f"SSH not enabled or could not be negotiated for {switch_element.hostname} @ {switch_element.ip}")
            output_data[switch_element.ip] = "failed"
        except Exception:
            traceback.print_exc()

    return output_data

    # vlan_parsed = parse_output(platform="cisco_ios", command="show vlan", data=vlan_output)
    # json_vlan_parsed = (json.dumps(vlan_parsed))

# ssh_connect()
# print("finish")
