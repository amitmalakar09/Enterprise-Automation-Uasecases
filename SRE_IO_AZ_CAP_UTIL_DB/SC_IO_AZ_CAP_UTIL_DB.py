#code by Amit Malakar (revised genericversion)

import requests
from datetime import datetime, timedelta
from dateutil.parser import isoparse
import pandas as pd
import mysql.connector

# ==========================================================
# CONFIGURATION  
# ==========================================================

TENANT_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
CLIENT_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
CLIENT_SECRET = "dummy-client-secret"

DB_HOST = "localhost"
DB_USER = "db_user"
DB_PASSWORD = "db_password"
DB_NAME = "vm_reporting"

INPUT_FILE = "subscriptions.csv"

CPU_TABLE = "az_vm_cpu_usage"
MEMORY_TABLE = "az_vm_memory_usage"

# Optional filter(apply if needed to limit scope)
RESOURCE_GROUP_PREFIX = None

# ==========================================================
# AUTHENTICATION
# ==========================================================

def get_access_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://management.azure.com/.default"
    }

    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30
    )

    response.raise_for_status()

    return response.json()["access_token"]


# ==========================================================
# GENERIC REST HELPER
# ==========================================================

def fetch_all_pages(url, headers):
    results = []

    while url:
        response = requests.get(url, headers=headers, timeout=30)

        response.raise_for_status()

        data = response.json()

        results.extend(data.get("value", []))

        url = data.get("nextLink")

    return results


# ==========================================================
# AZURE RESOURCE FUNCTIONS
# ==========================================================

def get_resource_groups(access_token, subscription_id):

    url = (
        f"https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourcegroups"
        f"?api-version=2021-04-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    return fetch_all_pages(url, headers)


def get_virtual_machines(
    access_token,
    subscription_id,
    resource_group_name
):

    url = (
        f"https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/"
        f"{resource_group_name}/providers/"
        f"Microsoft.Compute/virtualMachines"
        f"?api-version=2021-07-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    return fetch_all_pages(url, headers)


def get_vm_details(access_token, resource_id):

    url = (
        f"https://management.azure.com"
        f"{resource_id}"
        f"?api-version=2023-03-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    if response.status_code == 404:
        print(f"VM not found: {resource_id}")
        return {}

    response.raise_for_status()

    return response.json()


def get_vm_status(access_token, resource_id):

    url = (
        f"https://management.azure.com"
        f"{resource_id}/InstanceView"
        f"?api-version=2021-07-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        vm_instance = response.json()

        for status in vm_instance.get("statuses", []):

            if "PowerState" in status.get("code", ""):
                return status["code"].split("/")[-1]

        return "Unknown"

    except Exception as e:
        print(f"Status Error: {resource_id} -> {e}")
        return "Error"


# ==========================================================
# METRICS
# ==========================================================

def get_metric(
    access_token,
    resource_id,
    metric_name
):

    url = (
        f"https://management.azure.com"
        f"{resource_id}"
        f"/providers/microsoft.insights/metrics"
    )

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)

    params = {
        "metricnames": metric_name,
        "timespan": f"{start_time.isoformat()}Z/{end_time.isoformat()}Z",
        "aggregation": "Average,Maximum,Minimum",
        "api-version": "2018-01-01"
    }

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:
        print(f"Metric Error: {resource_id} -> {e}")
        return None


def process_cpu_metrics(metrics):

    if not metrics:
        return None, None, None, None

    total = 0
    count = 0

    max_value = float("-inf")
    min_value = float("inf")
    peak_time = None

    for value in metrics.get("value", []):

        if value["name"]["value"] != "Percentage CPU":
            continue

        for ts in value.get("timeseries", []):

            for point in ts.get("data", []):

                avg = point.get("average")

                if avg is None:
                    continue

                total += avg
                count += 1

                if avg > max_value:
                    max_value = avg
                    peak_time = point["timeStamp"]

                min_value = min(min_value, avg)

    if count == 0:
        return None, None, None, None

    return (
        round(max_value, 2),
        round(min_value, 2),
        round(total / count, 2),
        peak_time
    )


def process_memory_metrics(metrics):

    if not metrics:
        return None, None, None, None

    total = 0
    count = 0

    max_value = float("-inf")
    min_value = float("inf")
    peak_time = None

    for value in metrics.get("value", []):

        if value["name"]["value"] != "Available Memory Bytes":
            continue

        for ts in value.get("timeseries", []):

            for point in ts.get("data", []):

                avg = point.get("average")

                if avg is None:
                    continue

                total += avg
                count += 1

                if avg > max_value:
                    max_value = avg
                    peak_time = point["timeStamp"]

                min_value = min(min_value, avg)

    if count == 0:
        return None, None, None, None

    return (
        round(max_value / (1024**3), 2),
        round(min_value / (1024**3), 2),
        round((total / count) / (1024**3), 2),
        peak_time
    )


# ==========================================================
# MEMORY ALLOCATION
# ==========================================================

def get_allocated_memory(
    access_token,
    subscription_id,
    region,
    vm_size
):

    url = (
        f"https://management.azure.com/subscriptions/"
        f"{subscription_id}/providers/"
        f"Microsoft.Compute/locations/{region}/vmSizes"
        f"?api-version=2021-03-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    vm_sizes = response.json().get("value", [])

    for size in vm_sizes:

        if size["name"] == vm_size:
            return size["memoryInMB"] / 1024

    return None


# ==========================================================
# DATABASE
# ==========================================================

def connect_to_database():

    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def insert_row(cursor, table_name, data):

    columns = ", ".join(data.keys())

    placeholders = ", ".join(["%s"] * len(data))

    sql = (
        f"INSERT INTO {table_name} "
        f"({columns}) VALUES ({placeholders})"
    )

    cursor.execute(
        sql,
        tuple(data.values())
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    subscriptions = pd.read_csv(INPUT_FILE)

    access_token = get_access_token()

    conn = connect_to_database()
    cursor = conn.cursor()

    commit_counter = 0

    for subscription_id in subscriptions["subscription_id"]:

        print(f"Processing {subscription_id}")

        try:

            resource_groups = get_resource_groups(
                access_token,
                subscription_id
            )

            for rg in resource_groups:

                rg_name = rg["name"]

                if RESOURCE_GROUP_PREFIX:

                    if not rg_name.lower().startswith(
                        RESOURCE_GROUP_PREFIX.lower()
                    ):
                        continue

                vms = get_virtual_machines(
                    access_token,
                    subscription_id,
                    rg_name
                )

                for vm in vms:

                    resource_id = vm["id"]
                    vm_name = vm["name"]

                    vm_details = get_vm_details(
                        access_token,
                        resource_id
                    )

                    if not vm_details:
                        continue

                    vm_size = (
                        vm_details.get("properties", {})
                        .get("hardwareProfile", {})
                        .get("vmSize", "Unknown")
                    )

                    region = vm_details.get(
                        "location",
                        "Unknown"
                    )

                    allocated_memory = get_allocated_memory(
                        access_token,
                        subscription_id,
                        region,
                        vm_size
                    )

                    cpu_metrics = get_metric(
                        access_token,
                        resource_id,
                        "Percentage CPU"
                    )

                    memory_metrics = get_metric(
                        access_token,
                        resource_id,
                        "Available Memory Bytes"
                    )

                    cpu_max, cpu_min, cpu_avg, cpu_peak = \
                        process_cpu_metrics(cpu_metrics)

                    mem_max, mem_min, mem_avg, mem_peak = \
                        process_memory_metrics(memory_metrics)

                    vm_status = get_vm_status(
                        access_token,
                        resource_id
                    )

                    report_time = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    cpu_data = {
                        "subscription_id": subscription_id,
                        "resource_group": rg_name,
                        "vm_name": vm_name,
                        "status": vm_status,
                        "cpu_max": cpu_max,
                        "cpu_min": cpu_min,
                        "cpu_avg": cpu_avg,
                        "cpu_peak_time": cpu_peak,
                        "report_time": report_time
                    }

                    memory_data = {
                        "subscription_id": subscription_id,
                        "resource_group": rg_name,
                        "vm_name": vm_name,
                        "allocated_memory_gb": allocated_memory,
                        "memory_max_gb": mem_max,
                        "memory_min_gb": mem_min,
                        "memory_avg_gb": mem_avg,
                        "memory_peak_time": mem_peak,
                        "report_time": report_time
                    }

                    insert_row(
                        cursor,
                        CPU_TABLE,
                        cpu_data
                    )

                    insert_row(
                        cursor,
                        MEMORY_TABLE,
                        memory_data
                    )

                    commit_counter += 1

                    if commit_counter >= 100:
                        conn.commit()
                        commit_counter = 0

        except Exception as e:
            print(
                f"Subscription Error "
                f"{subscription_id}: {e}"
            )

    conn.commit()

    cursor.close()
    conn.close()

    print("Completed successfully")


if __name__ == "__main__":
    main()