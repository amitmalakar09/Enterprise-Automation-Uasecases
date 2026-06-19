# XtremIO SAN Storage Report Script

## Overview
This Python script automates the collection of SAN storage usage data from XtremIO devices, processes the data, and inserts it into a MariaDB database. It uses API calls to fetch storage details, parses the responses, and logs each step for traceability.

## Features
- Fetches storage details from multiple XtremIO devices.
- Connects to the XtremIO REST API using secure credentials.
- Converts storage values to terabytes (TB) for standardized reporting.
- Inserts processed data into a MariaDB table.
- Logs each step, including success and error messages.

## Prerequisites
- Python 3.6+
- Required Python packages:
  - `requests`
  - `mysql-connector-python`
  - `paramiko`
  - `configparser`
- XtremIO API access credentials.
- MariaDB instance with appropriate tables.
- Vault access for credential management.

## Installation
1. Clone the repository:
   ```sh
   git clone <repository_url>
   cd <repository_directory>
   ```

2. Install required packages:
   ```sh
   pip install -r requirements.txt
   ```

## Configuration
1. Create an `xtremio_ips.txt` file with each SAN device IP on a new line.
2. Store database and API credentials in your secret vault.
3. Update the settings file path in the script.

## Database Schema
Ensure your MariaDB table is set up as follows:
```sql
CREATE TABLE san_storage (
    Type VARCHAR(50),
    Array_name VARCHAR(100),
    Total_TBs FLOAT,
    Used_TBs FLOAT,
    Free_TBs FLOAT
);
```

## Usage
Run the script with necessary arguments:
```sh
python script.py <vault_password> <xtremio_user_key> <xtremio_pass_key> <db_host_key> <db_user_key> <db_pass_key> <db_name_key>
```

Example:
```sh
python script.py myVaultPassword xtremioUser xtremioPass dbHost dbUser dbPass dbName
```

## Logging
Logs are stored in `xtremio.log` with timestamps, logging info, and error details.

## Error Handling
- Connection errors are logged.
- API response issues or unexpected data formats are handled with detailed logs.
- Database insertion errors are caught and logged.

## Security Considerations
- Uses secure connections for API calls and database interactions.
- Fetches secrets from a vault to avoid storing credentials in plain text.

## Author
Amit Malakar

## License
MIT License


