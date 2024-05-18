import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse
from colorama import init, Fore, Style
import argparse
import readline
from prettytable import PrettyTable
from datetime import datetime
import os
import csv
import json
import random
import socket
import secrets
import threading
from time import sleep
from queue import Queue
from scapy.all import ARP, send

# Initialize colorama
init(autoreset=True)

# Custom logging handler for colorized output
class ColorizingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            message = self.format(record)
            if "RECV:" in message or "Processing:" in message:
                message = Fore.GREEN + message + Style.RESET_ALL
            elif "Changing transaction state" in message or "TRANSACTION_COMPLETE" in message or "Factory Response" in message:
                message = Fore.CYAN + message + Style.RESET_ALL
            elif "Frame check, no more data!" in message:
                message = Fore.RED + message + Style.RESET_ALL
            else:
                message = message
            self.stream.write(message + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = ColorizingStreamHandler()
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Set up tab completion
commands = ['read', 'write', 'exit']
register_types = ['coils', 'discrete_inputs', 'input_registers', 'holding_registers']

def completer(text, state):
    options = [cmd for cmd in commands + register_types if cmd.startswith(text)]
    if state < len(options):
        return options[state]
    return None

readline.set_completer(completer)
readline.parse_and_bind("tab: complete")

def get_modbus_client(ip_address, port):
    return ModbusTcpClient(ip_address, port=port)

def read_registers(client, register_type, address, count, unit_id):
    if register_type == "coils":
        return client.read_coils(address, count, unit=unit_id)
    elif register_type == "discrete_inputs":
        return client.read_discrete_inputs(address, count, unit=unit_id)
    elif register_type == "input_registers":
        return client.read_input_registers(address, count, unit=unit_id)
    elif register_type == "holding_registers":
        return client.read_holding_registers(address, count, unit=unit_id)
    else:
        raise ValueError("Invalid register type")

def write_registers(client, register_type, address, values, unit_id):
    if register_type == "coils":
        return client.write_coils(address, values, unit=unit_id)
    elif register_type == "holding_registers":
        return client.write_registers(address, values, unit=unit_id)
    else:
        raise ValueError("Can only write to coils or holding registers")

def validate_register_type(register_type):
    if register_type not in register_types:
        raise ValueError("Invalid register type. Must be one of: coils, discrete_inputs, input_registers, holding_registers")

def validate_positive_integer(value, field_name):
    try:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError
    except ValueError:
        raise ValueError(f"Invalid {field_name}. Must be a positive integer.")
    return ivalue

def prompt_for_operation_args():
    while True:
        action = input(Fore.YELLOW + "Do you want to read or write registers? (read/write/exit): ").strip().lower()
        if action in ['read', 'write', 'exit']:
            break
        print(Fore.RED + "Invalid option. Please enter 'read', 'write', or 'exit'.")

    if action == 'exit':
        return None
    elif action == 'read':
        print(Fore.GREEN + "Recommended register types: coils, discrete_inputs, input_registers, holding_registers")
        while True:
            try:
                register_type = input(Fore.YELLOW + "Enter register type: ").strip().lower()
                validate_register_type(register_type)
                break
            except ValueError as e:
                print(Fore.RED + str(e))
        
        while True:
            try:
                address = validate_positive_integer(input(Fore.YELLOW + "Enter the starting address (default 0): ") or 0, "address")
                break
            except ValueError as e:
                print(Fore.RED + str(e))
        
        while True:
            try:
                count = validate_positive_integer(input(Fore.YELLOW + "Enter the number of registers to read (default 1): ") or 1, "count")
                break
            except ValueError as e:
                print(Fore.RED + str(e))

        return {'action': action, 'type': register_type, 'address': address, 'count': count}
    elif action == 'write':
        print(Fore.GREEN + "Recommended register types: coils, holding_registers")
        while True:
            try:
                register_type = input(Fore.YELLOW + "Enter register type: ").strip().lower()
                validate_register_type(register_type)
                if register_type not in ['coils', 'holding_registers']:
                    print(Fore.RED + "Can only write to coils or holding registers.")
                    continue
                break
            except ValueError as e:
                print(Fore.RED + str(e))

        while True:
            try:
                address = validate_positive_integer(input(Fore.YELLOW + "Enter the starting address (default 0): ") or 0, "address")
                break
            except ValueError as e:
                print(Fore.RED + str(e))

        data = input(Fore.YELLOW + "Enter the data to write (e.g., 'John' for holding registers): ")
        values = [ord(char) for char in data] if register_type == 'holding_registers' else [bool(int(char)) for char in data]

        return {'action': action, 'type': register_type, 'address': address, 'values': values}

def parse_written_data(data):
    hex_values = data.split()
    ascii_chars = [chr(int(hex_values[i], 16)) for i in range(0, len(hex_values), 2)]
    return ''.join(ascii_chars)

def decode_hex_response(hex_data):
    if hex_data.startswith("0x"):
        hex_data = hex_data[2:]
    bytes_data = bytes.fromhex(hex_data)
    return bytes_data.decode('utf-8', errors='ignore')

def translate_modbus_response(response):
    if response.isError():
        return f"Error: {response}"
    if hasattr(response, 'registers'):
        return f"Register values: {response.registers}"
    elif hasattr(response, 'bits'):
        return f"Bit values: {response.bits}"
    return "No data found in response."

def decode_holding_registers(registers):
    try:
        return ''.join(chr(reg) for reg in registers)
    except:
        return "Unable to decode"

def generate_filename(ip_address, extension):
    base_filename = f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    counter = 1
    filename = f"{base_filename}.{extension}"
    while os.path.exists(os.path.join('csv' if extension == 'csv' else 'json', filename)):
        counter += 1
        filename = f"{base_filename}_{counter:02d}.{extension}"
    return filename

def save_data_to_csv(filename, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Register Type", "Data"])
        for row in data:
            writer.writerow(row)
    print(Fore.GREEN + f"Data saved to {filename}")

def save_data_to_json(filename, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)
    print(Fore.GREEN + f"Data saved to {filename}")

def format_data(register_type, data):
    if register_type == "coils" or register_type == "discrete_inputs":
        return [bool(bit) for bit in data]
    elif register_type == "input_registers" or register_type == "holding_registers":
        if isinstance(data, list):
            return data
        return [data]
    return data

def read_all_data(client, unit_id, ip_address):
    print(Fore.YELLOW + "Reading all data from Modbus device...")
    
    try:
        # Read Coils
        coils_response = client.read_coils(0, 16, unit=unit_id)
        coils_data = format_data('coils', coils_response.bits if not coils_response.isError() else "Error reading coils")

        # Read Discrete Inputs
        discrete_inputs_response = client.read_discrete_inputs(0, 16, unit=unit_id)
        discrete_inputs_data = format_data('discrete_inputs', discrete_inputs_response.bits if not discrete_inputs_response.isError() else "Error reading discrete inputs")

        # Read Input Registers
        input_registers_response = client.read_input_registers(0, 10, unit=unit_id)
        input_registers_data = format_data('input_registers', input_registers_response.registers if not input_registers_response.isError() else "Error reading input registers")

        # Read Holding Registers
        holding_registers_response = client.read_holding_registers(0, 10, unit=unit_id)
        holding_registers_data = format_data('holding_registers', holding_registers_response.registers if not holding_registers_response.isError() else "Error reading holding registers")

        # Display data in human-readable format
        table = PrettyTable(["Register Type", "Data"])
        table.align["Register Type"] = "l"
        table.align["Data"] = "l"
        table.add_row(["Coils", coils_data])
        table.add_row(["Discrete Inputs", discrete_inputs_data])
        table.add_row(["Input Registers", input_registers_data])
        table.add_row(["Holding Registers", f"{holding_registers_data} ({decode_holding_registers(holding_registers_data)})"])

        print(Fore.CYAN + table.get_string())

        # Save data to CSV and JSON
        data = [
            ["Coils", coils_data],
            ["Discrete Inputs", discrete_inputs_data],
            ["Input Registers", input_registers_data],
            ["Holding Registers", holding_registers_data]
        ]

        csv_filename = os.path.join('csv', generate_filename(ip_address, 'csv'))
        json_filename = os.path.join('json', generate_filename(ip_address, 'json'))

        save_data_to_csv(csv_filename, data)
        save_data_to_json(json_filename, data)

    except ModbusException as e:
        print(Fore.RED + f"Failed to read all data: {e}")

def main():
    parser = argparse.ArgumentParser(description="Modbus Client Script")
    
    parser.add_argument('--ip', type=str, help="Modbus device IP address")
    parser.add_argument('--port', type=int, help="Modbus device port (default: 502)")
    parser.add_argument('--unit', type=int, help="Modbus device unit ID (default: 1)")

    args = parser.parse_args()

    if not args.ip:
        args.ip = input(Fore.YELLOW + "Enter the Modbus device IP address: ")
    if not args.port:
        args.port = int(input(Fore.YELLOW + "Enter the Modbus device port (default 502): ") or 502)
    if not args.unit:
        args.unit = int(input(Fore.YELLOW + "Enter the Modbus device unit ID (default 1): ") or 1)

    client = get_modbus_client(args.ip, args.port)
    
    try:
        connection = client.connect()
        if connection:
            print(Fore.GREEN + "Connected to Modbus device.")
            
            # Read all data from the Modbus device
            read_all_data(client, args.unit, args.ip)
            
            while True:
                operation_args = prompt_for_operation_args()
                if operation_args is None:
                    print(Fore.YELLOW + "Exiting program.")
                    break
                
                action = operation_args['action']
                try:
                    if action == 'read':
                        response = read_registers(client, operation_args['type'], operation_args['address'], operation_args['count'], args.unit)
                        if not response.isError():
                            print(Fore.CYAN + translate_modbus_response(response))
                            print(Fore.CYAN + f"Hex data: {response}")
                        else:
                            print(Fore.RED + f"Error reading registers: {response}")
                    elif action == 'write':
                        response = write_registers(client, operation_args['type'], operation_args['address'], operation_args['values'], args.unit)
                        if not response.isError():
                            hex_data = ' '.join([f"0x{ord(char):02x}" for char in operation_args['data']])
                            parsed_data = parse_written_data(hex_data)
                            print(Fore.CYAN + f"Data written successfully. Hex data: {hex_data}")
                            print(Fore.CYAN + f"Parsed data: {parsed_data}")
                        else:
                            print(Fore.RED + f"Error writing data: {response}")
                except ValueError as e:
                    print(Fore.RED + f"Value error: {e}")
                except ModbusException as e:
                    print(Fore.RED + f"Modbus exception: {e}")
                except Exception as e:
                    print(Fore.RED + f"An unexpected error occurred: {e}")
        else:
            print(Fore.RED + "Failed to connect to Modbus device.")
    except ConnectionException as e:
        print(Fore.RED + f"Connection exception: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
