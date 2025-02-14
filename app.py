import streamlit as st
import yaml
from pathlib import Path
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =============================
# NautobotClient Implementation
# =============================
class NautobotClient:
    def __init__(
        self,
        url: str,
        token: str | None = None,
        **kwargs,
    ):
        self.base_url = self._parse_url(url)
        self._token = token
        self.verify_ssl = kwargs.get("verify_ssl", False)
        self.retries = kwargs.get("retries", 3)
        self.timeout = kwargs.get("timeout", 10)
        self.proxies = kwargs.get("proxies", None)
        self._create_session()

    def _parse_url(self, url: str) -> str:
        """Checks if the provided URL has http or https and updates it if needed."""
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            return f"http://{url}"
        return parsed_url.geturl()

    def _create_session(self):
        """Creates the requests.Session object and applies the necessary parameters."""
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Authorization"] = f"Token {self._token}"
        if self.proxies:
            self.session.proxies.update(self.proxies)

        retry_method = Retry(
            total=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_method)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def http_call(
        self,
        method: str,
        url: str,
        data: dict | str | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
        verify: bool = False,
        params: dict | list[tuple] | None = None,
    ) -> dict:
        """
        Performs the HTTP operation.

        Required Attributes:
        - `method` (str): HTTP method to perform: GET, POST, etc.
        - `url` (str): URL target (this will be appended to the base URL)
        - `data`: Dictionary or byte data for the request body.
        - `json_data`: Dictionary to be passed as JSON.
        - `headers`: Dictionary of HTTP Headers.
        - `verify`: SSL Verification.
        - `params`: Query string parameters.
        """
        _request = requests.Request(
            method=method.upper(),
            url=self.base_url + url,
            data=data,
            json=json_data,
            headers=headers,
            params=params,
        )

        _request = self.session.prepare_request(_request)

        try:
            _response = self.session.send(request=_request, verify=verify, timeout=self.timeout)
        except Exception as err:
            raise err

        # Raise error if object already exists.
        if "already exists" in _response.text:
            raise ValueError(_response.text)

        try:
            _response.raise_for_status()
        except Exception as err:
            raise err

        if _response.status_code == 204:
            return {}
        return _response.json()

# =============================
# Helper Functions
# =============================

def load_yaml(source):
    """
    Loads a YAML file from a file path or a file-like object.
    """
    if hasattr(source, "read"):
        return yaml.safe_load(source)
    else:
        with open(source, "r") as f:
            return yaml.safe_load(f)

# A simple logging class to print messages in Streamlit
class Console:
    def log(self, message, style=None):
        # You can adjust the style mapping as needed
        st.info(message)

console = Console()

# =============================
# Nautobot Data Loader Function
# =============================

def utils_load_nautobot_data(
    nautobot_token: str,
    topology,
    extra_topology_vars,
    nautobot_url: str = "http://localhost:8080",
):
    """Load Nautobot data from containerlab topology file."""
    console.log(
        f"Loading Nautobot data from topology file: {topology} and {extra_topology_vars}",
        style="info",
    )

    console.log("Reading containerlab topology file", style="info")
    topology_dict = load_yaml(topology)

    console.log("Reading extra topology vars file", style="info")
    extra_topology_vars_dict = load_yaml(extra_topology_vars)

    # Add extra vars to topology dict (assuming structure exists)
    for key, value in extra_topology_vars_dict.get("nodes", {}).items():
        if key in topology_dict.get("topology", {}).get("nodes", {}):
            topology_dict["topology"]["nodes"][key].update(value)
        else:
            console.log(f"Key {key} not found in topology_dict", style="warning")

    console.log("Instantiating Nautobot Client", style="info")
    nautobot_client = NautobotClient(url=nautobot_url, token=nautobot_token)

    # Create Roles in Nautobot
    roles = nautobot_client.http_call(
        method="post",
        url="/api/extras/roles/",
        json_data={"name": "network_device", "content_types": ["dcim.device"]},
    )
    console.log(f"Created Role: {roles.get('display')}", style="info")

    # Create Manufacturers in Nautobot
    manufacturers = nautobot_client.http_call(
        method="post",
        url="/api/dcim/manufacturers/",
        json_data={"name": "Arista"},
    )
    console.log(f"Created Manufacturer: {manufacturers.get('display')}", style="info")

    # Create Device Types in Nautobot
    device_types = nautobot_client.http_call(
        method="post",
        url="/api/dcim/device-types/",
        json_data={"manufacturer": "Arista", "model": "cEOS"},
    )
    console.log(f"Created Device Types: {device_types.get('display')}", style="info")

    # Create Location Types
    location_type = nautobot_client.http_call(
        method="post",
        url="/api/dcim/location-types/",
        json_data={"name": "site", "content_types": ["dcim.device"]},
    )
    console.log(f"Created Location Type: {location_type.get('display')}", style="info")

    # Create Statuses
    statuses = nautobot_client.http_call(
        method="post",
        url="/api/extras/statuses/",
        json_data={
            "name": "lab-active",
            "content_types": [
                "dcim.device",
                "dcim.interface",
                "dcim.location",
                "ipam.ipaddress",
                "ipam.prefix",
            ],
            "color": "aaf0d1",
        },
    )
    console.log(f"Created Status: {statuses.get('display')}", style="info")
    alerted_statuses = nautobot_client.http_call(
        method="post",
        url="/api/extras/statuses/",
        json_data={
            "name": "Alerted",
            "content_types": [
                "dcim.device",
                "dcim.interface",
                "dcim.location",
                "ipam.ipaddress",
                "ipam.prefix",
            ],
            "color": "ff5a36",
        },
    )
    console.log(f"Created Status: {alerted_statuses.get('display')}", style="info")

    # Create Locations
    locations = nautobot_client.http_call(
        method="post",
        url="/api/dcim/locations/",
        json_data={
            "name": "lab",
            "location_type": {"id": location_type.get("id")},
            "status": {"id": statuses.get("id")},
        },
    )
    console.log(f"Created Location: {locations.get('display')}", style="info")

    # Create IPAM Namespace
    ipam_namespace = nautobot_client.http_call(
        method="post",
        url="/api/ipam/namespaces/",
        json_data={"name": "lab-default"},
    )
    console.log(f"Created IPAM Namespace: {ipam_namespace.get('display')}", style="info")

    # Create Prefixes for the Namespace
    for prefix_data in extra_topology_vars_dict.get("prefixes", []):
        prefix = nautobot_client.http_call(
            method="post",
            url="/api/ipam/prefixes/",
            json_data={
                "prefix": prefix_data["prefix"],
                "namespace": {"id": ipam_namespace.get("id")},
                "type": "network",
                "status": {"id": statuses.get("id")},
                "description": prefix_data["name"],
            },
        )
        console.log(f"Created Prefix: {prefix.get('display')}", style="info")

    # Create Management Prefix
    mgmt_prefix = nautobot_client.http_call(
        method="post",
        url="/api/ipam/prefixes/",
        json_data={
            "prefix": topology_dict.get("mgmt", {}).get("ipv4-subnet"),
            "namespace": {"id": ipam_namespace.get("id")},
            "type": "network",
            "status": {"id": statuses.get("id")},
            "description": "lab-mgmt-prefix",
        },
    )
    console.log(f"Created Prefix: {mgmt_prefix.get('display')}", style="info")

    # Create Devices and their associated data
    for node, node_data in topology_dict.get("topology", {}).get("nodes", {}).items():
        device = nautobot_client.http_call(
            method="post",
            url="/api/dcim/devices/",
            json_data={
                "name": node,
                "role": {"id": roles.get("id")},
                "device_type": {"id": device_types.get("id")},
                "location": {"id": locations.get("id")},
                "status": {"id": statuses.get("id")},
                "customn_fields": {
                    "containerlab": {
                        "node_kind": node_data.get("kind"),
                        "node_address": node_data.get("mgmt-ipv4"),
                    }
                },
            },
        )
        console.log(f"Created Device: {device.get('display')}", style="info")

        # Create IP Addresses and Interfaces
        for intf_data in node_data.get("interfaces", []):
            ip_address = nautobot_client.http_call(
                method="post",
                url="/api/ipam/ip-addresses/",
                json_data={
                    "address": intf_data["ipv4"],
                    "status": {"id": statuses.get("id")},
                    "namespace": {"id": ipam_namespace.get("id")},
                    "type": "host",
                },
            )
            console.log(f"Created IP Address: {ip_address.get('display')}", style="info")

            interface = nautobot_client.http_call(
                method="post",
                url="/api/dcim/interfaces/",
                json_data={
                    "device": {"id": device.get("id")},
                    "name": intf_data["name"],
                    "type": "virtual",
                    "enabled": True,
                    "description": f"Interface {intf_data['name']}",
                    "status": {"id": statuses.get("id")},
                    "label": intf_data.get("role"),
                },
            )
            console.log(
                f"Created Interface: {device.get('display')}:{interface.get('display')}",
                style="info",
            )

            # Create IP address to interface mapping
            mapping = nautobot_client.http_call(
                method="post",
                url="/api/ipam/ip-address-to-interface/",
                json_data={
                    "ip_address": {"id": ip_address.get("id")},
                    "interface": {"id": interface.get("id")},
                },
            )
            console.log(
                f"Created IP Address to Interface Mapping: {mapping.get('display')}",
                style="info",
            )

        # Create Mgmt IP Address
        mgmt_ip_address = nautobot_client.http_call(
            method="post",
            url="/api/ipam/ip-addresses/",
            json_data={
                "address": node_data.get("mgmt-ipv4"),
                "status": {"id": statuses.get("id")},
                "namespace": {"id": ipam_namespace.get("id")},
                "type": "host",
            },
        )
        console.log(f"Created Mgmt IP Address: {mgmt_ip_address.get('display')}", style="info")

        # Create Mgmt Interface
        mgmt_interface = nautobot_client.http_call(
            method="post",
            url="/api/dcim/interfaces/",
            json_data={
                "device": {"id": device.get("id")},
                "name": "Management0",
                "type": "virtual",
                "enabled": True,
                "description": "Management Interface",
                "status": {"id": statuses.get("id")},
                "label": "mgmt",
            },
        )
        console.log(
            f"Created Mgmt Interface: {device.get('display')}:{mgmt_interface.get('display')}",
            style="info",
        )

        # Create Mgmt IP address to interface mapping
        mgmt_mapping = nautobot_client.http_call(
            method="post",
            url="/api/ipam/ip-address-to-interface/",
            json_data={
                "ip_address": {"id": mgmt_ip_address.get("id")},
                "interface": {"id": mgmt_interface.get("id")},
            },
        )
        console.log(
            f"Created Mgmt IP Address to Interface Mapping: {mgmt_mapping.get('display')}",
            style="info",
        )

        # Update Device with Primary IP Address
        device = nautobot_client.http_call(
            method="patch",
            url=f"/api/dcim/devices/{device.get('id')}/",
            json_data={
                "primary_ip4": {"id": mgmt_ip_address.get("id")},
            },
        )
        console.log(f"Updated Device: {device.get('display')}", style="info")

# =============================
# Streamlit App UI
# =============================

st.title("Streamlit Nautobot Data Loader")

st.markdown(
    """
This app loads Nautobot data using containerlab topology files.
Provide your Nautobot credentials and upload the necessary YAML files.
"""
)

nautobot_token = st.text_input("Enter Nautobot Token")
nautobot_url = st.text_input("Enter Nautobot URL", value="http://localhost:8080")

topology_file = st.file_uploader("Upload Topology YAML file", type=["yml", "yaml"])
extra_topology_vars_file = st.file_uploader(
    "Upload Extra Topology Vars YAML file", type=["yml", "yaml"]
)

if st.button("Load Nautobot Data"):
    if not nautobot_token:
        st.error("Please enter your Nautobot Token.")
    elif not topology_file:
        st.error("Please upload the Topology YAML file.")
    elif not extra_topology_vars_file:
        st.error("Please upload the Extra Topology Vars YAML file.")
    else:
        st.info("Starting data load...")
        try:
            utils_load_nautobot_data(
                nautobot_token, topology_file, extra_topology_vars_file, nautobot_url
            )
            st.success("Data load process completed (check logs above).")
        except Exception as e:
            st.error(f"An error occurred: {e}")


