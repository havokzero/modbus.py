import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
from colorama import init, Fore, Style
import argparse
import readline
from prettytable import PrettyTable
from datetime import datetime
import os
import csv
import json
import asyncio

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
commands = ['read', 'write', 'scan', 'bruteforce', 'exit']
register_types = ['coils', 'discrete_inputs', 'input_registers', 'holding_registers', 'all']

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

def validate_register_type(register_type, action):
    if action == 'read':
        if register_type not in register_types:
            raise ValueError("Invalid register type. Must be one of: coils, discrete_inputs, input_registers, holding_registers, all")
    elif action == 'write':
        if register_type not in ['coils', 'holding_registers']:
            raise ValueError("Invalid register type. Must be one of: coils, holding_registers")

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
        action = input(Fore.YELLOW + "Do you want to read, write, scan for unit IDs, brute force function codes, or exit? (read/write/scan/bruteforce/exit): ").strip().lower()
        if action in ['read', 'write', 'scan', 'bruteforce', 'exit']:
            break
        print(Fore.RED + "Invalid option. Please enter 'read', 'write', 'scan', 'bruteforce', or 'exit'.")

    if action == 'exit':
        return None
    elif action == 'read':
        print(Fore.GREEN + "Recommended register types: coils, discrete_inputs, input_registers, holding_registers, all")
        while True:
            try:
                register_type = input(Fore.YELLOW + "Enter register type: ").strip().lower()
                validate_register_type(register_type, action)
                break
            except ValueError as e:
                print(Fore.RED + str(e))

        if register_type != "all":
            read_all = input(Fore.YELLOW + "Do you want to read all addresses and number of registers? (yes/no): ").strip().lower()
            if read_all == 'yes':
                return {'action': action, 'type': register_type, 'read_all': True}
            else:
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
        else:
            return {'action': action, 'type': register_type}

    elif action == 'write':
        print(Fore.GREEN + "Recommended register types: coils, holding_registers")
        while True:
            try:
                register_type = input(Fore.YELLOW + "Enter register type: ").strip().lower()
                validate_register_type(register_type, action)
                break
            except ValueError as e:
                print(Fore.RED + str(e))

        write_all = input(Fore.YELLOW + "Do you want to write to all addresses and number of registers? (yes/no): ").strip().lower()
        if write_all == 'yes':
            data = input(Fore.YELLOW + "Enter the data to write (comma-separated for coils or space-separated for holding registers): ")
            if register_type == 'coils':
                try:
                    values = [bool(int(val)) for val in data.split(',')]
                except ValueError:
                    print(Fore.RED + "Invalid data for coils. Enter comma-separated 0 or 1 values.")
                    return prompt_for_operation_args()
            else:
                values = [ord(char) for char in ' '.join(data.split())]
            return {'action': action, 'type': register_type, 'write_all': True, 'values': values}
        else:
            while True:
                try:
                    address = validate_positive_integer(input(Fore.YELLOW + "Enter the starting address (default 0): ") or 0, "address")
                    break
                except ValueError as e:
                    print(Fore.RED + str(e))

            data = input(Fore.YELLOW + "Enter the data to write (comma-separated for coils or space-separated for holding registers): ")
            if register_type == 'coils':
                try:
                    values = [bool(int(val)) for val in data.split(',')]
                except ValueError:
                    print(Fore.RED + "Invalid data for coils. Enter comma-separated 0 or 1 values.")
                    return prompt_for_operation_args()
            else:
                values = [ord(char) for char in ' '.join(data.split())]

            return {'action': action, 'type': register_type, 'address': address, 'values': values}

    elif action == 'scan':
        return {'action': action}

    elif action == 'bruteforce':
        return {'action': action}

def parse_written_data(data):
    hex_values = data.split()
    ascii_chars = [chr(int(hex_values[i], 16)) for i in range(0, len(hex_values), 2)]
    return ''.join(ascii_chars)

def decode_hex_response(hex_data):
    if isinstance(hex_data, int):
        return chr(hex_data)
    if hex_data.startswith("0x"):
        hex_data = hex_data[2:]
    bytes_data = bytes.fromhex(hex_data)
    try:
        return bytes_data.decode('utf-8', errors='ignore')
    except UnicodeDecodeError as e:
        return f"Unable to decode hex data: {e}"

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

def generate_filename(ip_address, command, extension):
    base_filename = f"{ip_address}_{command}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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

def truncate_data(data, length=100):
    data_str = str(data)
    if len(data_str) > length:
        return data_str[:length] + '...'
    return data_str

def read_all_data(client, unit_id, ip_address):
    print(Fore.YELLOW + "Reading all data from Modbus device...")

    try:
        # Read Coils
        coils_response = client.read_coils(0, 128, unit=unit_id)
        coils_data = format_data('coils', coils_response.bits if not coils_response.isError() else "Error reading coils")

        # Read Discrete Inputs
        discrete_inputs_response = client.read_discrete_inputs(0, 128, unit=unit_id)
        discrete_inputs_data = format_data('discrete_inputs', discrete_inputs_response.bits if not discrete_inputs_response.isError() else "Error reading discrete inputs")

        # Read Input Registers
        input_registers_response = client.read_input_registers(0, 100, unit=unit_id)
        input_registers_data = format_data('input_registers', input_registers_response.registers if not input_registers_response.isError() else "Error reading input registers")

        # Read Holding Registers
        holding_registers_response = client.read_holding_registers(0, 100, unit=unit_id)
        holding_registers_data = format_data('holding_registers', holding_registers_response.registers if not holding_registers_response.isError() else "Error reading holding registers")

        # Display data in human-readable format
        table = PrettyTable(["Register Type", "Data"])
        table.align["Register Type"] = "l"
        table.align["Data"] = "l"
        table.add_row(["Coils", truncate_data(coils_data)])
        table.add_row(["Discrete Inputs", truncate_data(discrete_inputs_data)])
        table.add_row(["Input Registers", truncate_data(input_registers_data)])
        table.add_row(["Holding Registers", truncate_data(holding_registers_data)])

        print(Fore.CYAN + table.get_string())

        # Save data to CSV and JSON
        data = [
            ["Coils", coils_data],
            ["Discrete Inputs", discrete_inputs_data],
            ["Input Registers", input_registers_data],
            ["Holding Registers", holding_registers_data]
        ]

        csv_filename = os.path.join('csv', generate_filename(ip_address, 'read_all', 'csv'))
        json_filename = os.path.join('json', generate_filename(ip_address, 'read_all', 'json'))

        save_data_to_csv(csv_filename, data)
        save_data_to_json(json_filename, data)

        # Translate hex values to English values
        translated_data = translate_hex_values(data)
        table = PrettyTable(["Register Type", "Translated Data"])
        table.align["Register Type"] = "l"
        table.align["Translated Data"] = "l"
        for item in translated_data:
            table.add_row([item[0], truncate_data(item[1])])

        print(Fore.CYAN + "Translated Data:")
        print(table)

        translated_json_filename = os.path.join('json', generate_filename(ip_address, 'read_all_translated', 'json'))
        save_data_to_json(translated_json_filename, translated_data)

    except ModbusException as e:
        print(Fore.RED + f"Failed to read all data: {e}")

def translate_hex_values(data):
    translated_data = []
    for item in data:
        register_type = item[0]
        if register_type in ['Coils', 'Discrete Inputs']:
            translated_data.append([register_type, [bool(bit) for bit in item[1]]])
        elif register_type == 'Input Registers' or register_type == 'Holding Registers':
            translated_values = []
            for val in item[1]:
                if isinstance(val, int):
                    translated_values.append(chr(val))
                else:
                    translated_values.append(decode_hex_response(val))
            translated_data.append([register_type, translated_values])
    return translated_data

async def scan_modbus_unit_ids_async(ip_address, port, unit_id, semaphore, results):
    async with semaphore:
        client = get_modbus_client(ip_address, port)
        try:
            client.connect()
            request = client.read_input_registers(0, 1, unit=unit_id)
            client.close()
            if not request.isError():
                results.append(unit_id)
        except Exception:
            pass

def scan_modbus_unit_ids(ip_address, port, from_unit, to_unit, max_concurrent_tasks, timeout):
    semaphore = asyncio.Semaphore(max_concurrent_tasks)
    results = []
    loop = asyncio.get_event_loop()

    tasks = [
        scan_modbus_unit_ids_async(ip_address, port, unit_id, semaphore, results)
        for unit_id in range(from_unit, to_unit + 1)
    ]

    try:
        loop.run_until_complete(asyncio.gather(*tasks))
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nScan interrupted by user.")

    if results:
        json_filename = os.path.join('json', generate_filename(ip_address, 'scan', 'json'))
        save_data_to_json(json_filename, {"valid_unit_ids": results})
        print(Fore.CYAN + f"Valid Unit IDs saved to {json_filename}")
    else:
        print(Fore.RED + "No valid Unit IDs found")

async def brute_force_function_codes_async(ip_address, port, unit_id, function_code, semaphore, results):
    async with semaphore:
        client = get_modbus_client(ip_address, port)
        try:
            client.connect()
            request = client.execute(client.framer.buildRequest(function_code, unit_id))
            client.close()
            if not request.isError():
                results.append(function_code)
        except Exception:
            pass

def brute_force_function_codes(ip_address, port, unit_id, start_code, end_code, max_concurrent_tasks=10):
    semaphore = asyncio.Semaphore(max_concurrent_tasks)
    results = []
    loop = asyncio.get_event_loop()

    tasks = [
        brute_force_function_codes_async(ip_address, port, unit_id, function_code, semaphore, results)
        for function_code in range(start_code, end_code + 1)
    ]

    try:
        loop.run_until_complete(asyncio.gather(*tasks))
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nBrute force interrupted by user.")

    return results

def main():
    parser = argparse.ArgumentParser(description="Modbus Client Script")

    parser.add_argument('--ip', type=str, help="Modbus device IP address")
    parser.add_argument('--port', type=int, help="Modbus device port (default: 502)")
    parser.add_argument('--unit', type=int, help="Modbus device unit ID (default: 1)")
    parser.add_argument('--unit-id-from', type=int, default=1, help="Modbus Unit ID start range")
    parser.add_argument('--unit-id-to', type=int, default=247, help="Modbus Unit ID end range")
    parser.add_argument('--max-concurrent-tasks', type=int, default=10, help="Maximum number of concurrent tasks")
    parser.add_argument('--timeout', type=int, default=2, help="Timeout for the network probe, 0 means no timeout")

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
                        if operation_args['type'] == 'all':
                            read_all_data(client, args.unit, args.ip)
                        else:
                            if operation_args.get('read_all'):
                                response = read_registers(client, operation_args['type'], 0, 65535, args.unit)
                            else:
                                response = read_registers(client, operation_args['type'], operation_args['address'], operation_args['count'], args.unit)
                            if not response.isError():
                                print(Fore.CYAN + translate_modbus_response(response))
                                print(Fore.CYAN + "----------------------------------------")
                                print(Fore.CYAN + f"Hex data: {response}")
                            else:
                                print(Fore.RED + f"Error reading registers: {response}")
                    elif action == 'write':
                        if operation_args.get('write_all'):
                            response = write_registers(client, operation_args['type'], 0, operation_args['values'], args.unit)
                        else:
                            response = write_registers(client, operation_args['type'], operation_args['address'], operation_args['values'], args.unit)
                        if not response.isError():
                            print(Fore.CYAN + f"Data written successfully.")
                        else:
                            print(Fore.RED + f"Error writing data: {response}")
                    elif action == 'scan':
                        scan_modbus_unit_ids(args.ip, args.port, args.unit_id_from, args.unit_id_to, args.max_concurrent_tasks, args.timeout)
                    elif action == 'bruteforce':
                        start_code = int(input(Fore.YELLOW + "Enter the starting function code (default 1): ") or 1)
                        end_code = int(input(Fore.YELLOW + "Enter the ending function code (default 255): ") or 255)
                        results = brute_force_function_codes(args.ip, args.port, args.unit, start_code, end_code, args.max_concurrent_tasks)
                        if results:
                            json_filename = os.path.join('json', generate_filename(args.ip, 'bruteforce', 'json'))
                            save_data_to_json(json_filename, {"valid_function_codes": results})
                            print(Fore.CYAN + f"Valid function codes saved to {json_filename}")
                        else:
                            print(Fore.RED + "No valid function codes found")
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
