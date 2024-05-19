# Modbus Client Script

This repository contains a Modbus client script written in Python. The script allows for reading and writing Modbus registers, scanning for unit IDs, and brute forcing function codes.

## Features

- Read coils, discrete inputs, input registers, and holding registers
- Write to coils and holding registers
- Scan for active Modbus unit IDs
- Brute force Modbus function codes
- Save results to CSV and JSON files
- Display results in human-readable format with ASCII art and colored output

## Requirements

- Python 3.6+
- [pymodbus](https://pypi.org/project/pymodbus/)
- [colorama](https://pypi.org/project/colorama/)
- [prettytable](https://pypi.org/project/prettytable/)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/havokzero/modbus.py.git
   cd modbus.py
   ```

Command-Line Arguments

    --ip: Modbus device IP address
    --port: Modbus device port (default: 502)
    --unit: Modbus device unit ID (default: 1)
    --unit-id-from: Modbus Unit ID start range for scanning (default: 1)
    --unit-id-to: Modbus Unit ID end range for scanning (default: 247)
    --max-concurrent-tasks: Maximum number of concurrent tasks for scanning (default: 10)
    --timeout: Timeout for the network probe, 0 means no timeout (default: 2)

## Interactive Mode

When the script is run, it will prompt for the operation you wish to perform:

    read: Read registers from the Modbus device
    write: Write registers to the Modbus device
    scan: Scan for active Modbus unit IDs
    bruteforce: Brute force function codes
    exit: Exit the script

Example

```bash

Do you want to read, write, scan for unit IDs, brute force function codes, or exit? (read/write/scan/bruteforce/exit): read
Recommended register types: coils, discrete_inputs, input_registers, holding_registers, all
Enter register type: holding_registers
Do you want to read all addresses and number of registers? (yes/no): yes
```
Saving Results

The script saves results in both CSV and JSON formats. The files are named based on the operation performed and include the IP address and timestamp.
Error Handling

If an error occurs, the script will display an appropriate message. Common errors include connection issues, invalid register types, and read/write errors.
Contribution

Contributions are welcome! Please submit a pull request or open an issue to discuss changes.
License

This project is licensed under the MIT License.
