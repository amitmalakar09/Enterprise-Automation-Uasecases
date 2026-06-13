# Azure VM CPU & Memory Utilization Collector

## Overview    

This Python script collects Azure Virtual Machine inventory and performance metrics and stores the results in a MariaDB/MySQL database.

The script performs the following tasks:

* Authenticates to Azure using a Service Principal
* Reads Azure Subscription IDs from a CSV file
* Enumerates Resource Groups and Virtual Machines
* Retrieves VM metadata
* Collects CPU utilization metrics for the previous 24 hours
* Collects memory utilization metrics for the previous 24 hours
* Retrieves VM power status
* Calculates memory utilization statistics
* Stores CPU and memory reports in MariaDB/MySQL

---

## Features

* Azure REST API based authentication
* Multi-subscription support
* Automatic API pagination handling
* CPU utilization reporting
* Memory utilization reporting
* VM inventory collection
* MariaDB/MySQL integration
* Batch database commits
* Configurable Resource Group filtering
* Error handling for inaccessible resources

---

## Prerequisites

### Python Version

Python 3.8 or later is recommended.

---

### Required Python Packages

Install dependencies using:

```bash
pip install requests pandas python-dateutil mysql-connector-python
```

---

## Azure Permissions

The Azure Service Principal must have access to:

* Reader Role (minimum)
* Monitoring Reader Role (recommended)

at either:

* Subscription Level
* Management Group Level
* Resource Group Level

---

## Input File

Create a file named:

```text
subscriptions.csv
```

Example:

```csv
subscription_id
11111111-1111-1111-1111-111111111111
22222222-2222-2222-2222-222222222222
33333333-3333-3333-3333-333333333333
```

---

## Configuration

Update the configuration section in the script:

```python
TENANT_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
CLIENT_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
CLIENT_SECRET = "your-client-secret"

DB_HOST = "localhost"
DB_USER = "db_user"
DB_PASSWORD = "db_password"
DB_NAME = "vm_reporting"
```

Optional Resource Group filter:

```python
RESOURCE_GROUP_PREFIX = None
```

Examples:

```python
RESOURCE_GROUP_PREFIX = "prod"
```

or

```python
RESOURCE_GROUP_PREFIX = None
```

---

## Database Tables

### CPU Usage Table

```sql
CREATE TABLE az_vm_cpu_usage (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    subscription_id VARCHAR(100),
    resource_group VARCHAR(255),
    vm_name VARCHAR(255),
    status VARCHAR(50),
    cpu_max DECIMAL(10,2),
    cpu_min DECIMAL(10,2),
    cpu_avg DECIMAL(10,2),
    cpu_peak_time DATETIME,
    report_time DATETIME
);
```

---

### Memory Usage Table

```sql
CREATE TABLE az_vm_memory_usage (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    subscription_id VARCHAR(100),
    resource_group VARCHAR(255),
    vm_name VARCHAR(255),
    allocated_memory_gb DECIMAL(10,2),
    memory_max_gb DECIMAL(10,2),
    memory_min_gb DECIMAL(10,2),
    memory_avg_gb DECIMAL(10,2),
    memory_peak_time DATETIME,
    report_time DATETIME
);
```

---

## Execution

Run the script:

```bash
python azure_vm_metrics.py
```

---

## Data Collected

### VM Inventory

* Subscription ID
* Resource Group
* VM Name
* VM Size
* Region
* Environment Tag
* Creation Time
* VM Power State

### CPU Metrics

* Maximum CPU Utilization (%)
* Minimum CPU Utilization (%)
* Average CPU Utilization (%)
* Peak CPU Timestamp

### Memory Metrics

* Allocated Memory (GB)
* Maximum Memory Utilization (GB)
* Minimum Memory Utilization (GB)
* Average Memory Utilization (GB)
* Peak Memory Timestamp

---

## Error Handling

The script continues processing when:

* A VM no longer exists
* Metric retrieval fails
* A subscription encounters an error
* Resource access is denied

Errors are logged to standard output.

---

## Performance Considerations

Current implementation:

* Retrieves metrics for the last 24 hours
* Commits database transactions in batches
* Uses paginated Azure API calls
* Processes subscriptions sequentially

For very large environments, consider:

* Parallel subscription processing
* Bulk database inserts
* Connection pooling
* Azure SDK migration

---

## Security Recommendations

Do not hardcode credentials in production.

Recommended approaches:

* Environment Variables
* Azure Key Vault
* Managed Identity
* Secret Management Platforms

Example:

```python
import os

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
```

---

## Disclaimer

This project is intended as a generic example for collecting Azure VM performance data. Modify API versions, database schemas, and authentication methods as needed to match your organization's standards and Azure environment.
