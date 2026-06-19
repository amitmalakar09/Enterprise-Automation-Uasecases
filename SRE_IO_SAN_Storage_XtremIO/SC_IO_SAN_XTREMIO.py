import requests
import logging
import urllib3
import mysql.connector

# ==========================================================
# CONFIGURATION
# ==========================================================

XTREMIO_USERNAME = "xtremio_user"
XTREMIO_PASSWORD = "xtremio_password"

DB_HOST = "localhost"
DB_USER = "db_user"
DB_PASSWORD = "db_password"
DB_NAME = "storage_reporting"

INPUT_FILE = "xtremio_arrays.txt"
LOG_FILE = "xtremio_storage.log"

TABLE_NAME = "san_storage"

# ==========================================================
# DISABLE SSL WARNINGS
# ==========================================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filemode="a"
)

# ==========================================================
# SAN STORAGE REPORT CLASS
# ==========================================================


class SANStorageReport:

    def __init__(
        self,
        xtremio_user,
        xtremio_pass,
        db_user,
        db_pass,
        db_host,
        db_name
    ):

        self.xtremio_user = xtremio_user
        self.xtremio_pass = xtremio_pass

        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host = db_host
        self.db_name = db_name

        self.input_file = INPUT_FILE

        self.session = requests.Session()

        self.session.auth = (
            self.xtremio_user,
            self.xtremio_pass
        )

        self.session.verify = False

        self.san_devices = self.load_san_devices()

    # ======================================================
    # LOAD SAN DEVICES
    # ======================================================

    def load_san_devices(self):

        try:

            with open(self.input_file, "r") as file:

                devices = [
                    line.strip()
                    for line in file
                    if line.strip()
                ]

            logging.info(
                "Loaded %s SAN devices from %s",
                len(devices),
                self.input_file
            )

            return devices

        except FileNotFoundError:

            logging.error(
                "Input file not found: %s",
                self.input_file
            )

            return []

    # ======================================================
    # UNIT CONVERSION
    # ======================================================

    @staticmethod
    def bytes_to_tb(value):

        try:
            return round(
                float(value) / (1024 ** 3),
                2
            )
        except Exception:
            return 0

    # ======================================================
    # FETCH CLUSTERS
    # ======================================================

    def fetch_san_data(self, san_ip):

        url = (
            f"https://{san_ip}"
            "/api/json/v3/types/clusters"
        )

        try:

            response = self.session.get(
                url,
                timeout=30
            )

            response.raise_for_status()

            logging.info(
                "Successfully fetched SAN data from %s",
                san_ip
            )

            return response.json().get(
                "clusters",
                []
            )

        except requests.exceptions.RequestException as err:

            logging.error(
                "Failed to fetch SAN data from %s : %s",
                san_ip,
                err
            )

            return []

    # ======================================================
    # FETCH CLUSTER DETAILS
    # ======================================================

    def fetch_cluster_details(self, href):

        try:

            response = self.session.get(
                href,
                timeout=30
            )

            response.raise_for_status()

            return response.json().get(
                "content",
                {}
            )

        except requests.exceptions.RequestException as err:

            logging.error(
                "Failed to fetch cluster details %s : %s",
                href,
                err
            )

            return {}

    # ======================================================
    # PROCESS XTREMIO DATA
    # ======================================================

    def process_data(self):

        records = []

        for san_ip in self.san_devices:

            logging.info(
                "Processing XtremIO Array: %s",
                san_ip
            )

            clusters = self.fetch_san_data(
                san_ip
            )

            for cluster in clusters:

                href = cluster.get("href")

                if not href:
                    continue

                details = self.fetch_cluster_details(
                    href
                )

                total_space = details.get(
                    "ud-ssd-space"
                )

                used_space = details.get(
                    "ud-ssd-space-in-use"
                )

                total_tb = self.bytes_to_tb(
                    total_space
                )

                used_tb = self.bytes_to_tb(
                    used_space
                )

                free_tb = round(
                    total_tb - used_tb,
                    2
                )

                used_pct = (
                    round(
                        (used_tb / total_tb) * 100,
                        2
                    )
                    if total_tb > 0
                    else 0
                )

                free_pct = round(
                    100 - used_pct,
                    2
                )

                records.append(
                    (
                        "XTREMIO",
                        cluster.get(
                            "name",
                            "Unknown"
                        ),
                        total_tb,
                        used_tb,
                        free_tb,
                        used_pct,
                        free_pct
                    )
                )

        logging.info(
            "Processed %s records",
            len(records)
        )

        return records

    # ======================================================
    # DATABASE INSERT
    # ======================================================

    def insert_into_db(self, records):

        if not records:

            logging.warning(
                "No records available for insertion"
            )

            return

        insert_query = f"""
        INSERT INTO {TABLE_NAME}
        (
            Type,
            Array_name,
            Total_TBs,
            Used_TBs,
            Free_TBs,
            Used_pct,
            Free_pct
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """

        try:

            conn = mysql.connector.connect(
                host=self.db_host,
                user=self.db_user,
                password=self.db_pass,
                database=self.db_name
            )

            cursor = conn.cursor()

            cursor.executemany(
                insert_query,
                records
            )

            conn.commit()

            logging.info(
                "Inserted %s records into %s",
                cursor.rowcount,
                TABLE_NAME
            )

            cursor.close()
            conn.close()

        except mysql.connector.Error as err:

            logging.error(
                "Database Error: %s",
                err
            )

    # ======================================================
    # EXECUTE REPORT
    # ======================================================

    def run(self):

        processed_data = self.process_data()

        if processed_data:
            self.insert_into_db(
                processed_data
            )
        else:
            logging.warning(
                "No valid XtremIO data collected"
            )


# ==========================================================
# MAIN
# ==========================================================

def main():

    logging.info(
        "XtremIO SAN Storage Collection Started"
    )

    report = SANStorageReport(
        xtremio_user=XTREMIO_USERNAME,
        xtremio_pass=XTREMIO_PASSWORD,
        db_user=DB_USER,
        db_pass=DB_PASSWORD,
        db_host=DB_HOST,
        db_name=DB_NAME
    )

    report.run()

    logging.info(
        "XtremIO SAN Storage Collection Completed"
    )


if __name__ == "__main__":
    main()