import streamlit as st
import yaml
from pathlib import Path

# --- Helpers and Dummy Implementations ---

# If you have an actual NautobotClient, import it instead.
try:
    from nautobot_client import NautobotClient
except ImportError:
    class NautobotClient:
        def __init__(self, url, token):
            self.url = url
            self.token = token

        def http_call(self, url, method, json_data):
            st.write(f"HTTP {method} call to {self.url}{url} with payload:")
            st.json(json_data)
            # Dummy response with id and display fields.
            return {"id": 1, "display": json_data.get("name", "dummy")}

# A simple console class that prints to Streamlit.
class Console:
    def log(self, message, style=None):
        # You might map different styles to st.info/st.warning/etc.
        st.info(message)

console = Console()

# Utility to load YAML from a file-like object or file path.
def load_yaml(source):
    # If the source has a 'read' attribute, assume it's a file-like object (e.g. from st.file_uploader)
    if hasattr(source, "read"):
        return yaml.safe_load(source)
    else:
        with open(source, "r") as f:
            return yaml.safe_load(f)

# --- Nautobot Data Loader Function ---

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
        url="/api/extras/roles/",
        method="post",
        json_data={"name": "network_device", "content_types": ["dcim.device"]},
    )
    console.log(f"Created Role: {roles.get('display')}", style="info")

    # Create Manufacturers in Nautobot
    manufacturers = nautobot_client.http_call(
        url="/api/dcim/manufacturers/",
        method="post",
        json_data={"name": "Arista"},
    )
    console.log(f"Created Manufacturer: {manufacturers.get('display')}", style="info")

    # Create Device Types in Nautobot
    device_types = nautobot_client.http_call(
        url="/api/dcim/device-types/",
        method="post",
        json_data={"manufacturer": "Arista", "model": "cEOS"},
    )
    console.log(f"Created Device Types: {device_types.get('display')}", style="info")

    # Create Location Types
    location_type = nautobot_client.http_call(
        url="/api/dcim/location-types/",
        method="post",
        json_data={"name": "site", "content_types": ["dcim.device"]},
    )
    console.log(f"Created Location Type: {location_type.get('display')}", style="info")

    # Create Statuses
    statuses = nautobot_client.http_call(
        url="/api/extras/statuses/",
        method="post",
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
        url="/api/extras/statuses/",
        method="post",
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
        url="/api/dcim/locations/",
        method="post",
        json_data={
            "name": "lab",
            "location_type": {"id": location_type.get("id")},
            "status": {"id": statuses.get("id")},
        },
    )
    console.log(f"Created Location: {locations.get('display')}", style="info")

    # Create IPAM Namespace
    ipam_namespace = nautobot_client.http_call(
        url="/api/ipam/namespaces/",
        method="post",
        json_data={"name": "lab-default"},
    )
    console.log(f"Created IPAM Namespace: {ipam_namespace.get('display')}", style="info")

    # Create Prefixes for the Namespace
    for prefix_data in extra_topology_vars_dict.get("prefixes", []):
        prefix = nautobot_client.http_call(
            url="/api/ipam/prefixes/",
            method="post",
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
        url="/api/ipam/prefixes/",
        method="post",
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
            url="/api/dcim/devices/",
            method="post",
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
                url="/api/ipam/ip-addresses/",
                method="post",
                json_data={
                    "address": intf_data["ipv4"],
                    "status": {"id": statuses.get("id")},
                    "namespace": {"id": ipam_namespace.get("id")},
                    "type": "host",
                },
            )
            console.log(f"Created IP Address: {ip_address.get('display')}", style="info")

            interface = nautobot_client.http_call(
                url="/api/dcim/interfaces/",
                method="post",
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
                url="/api/ipam/ip-address-to-interface/",
                method="post",
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
            url="/api/ipam/ip-addresses/",
            method="post",
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
            url="/api/dcim/interfaces/",
            method="post",
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
            url="/api/ipam/ip-address-to-interface/",
            method="post",
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
            url=f"/api/dcim/devices/{device.get('id')}/",
            method="patch",
            json_data={
                "primary_ip4": {"id": mgmt_ip_address.get("id")},
            },
        )
        console.log(f"Updated Device: {device.get('display')}", style="info")

# --- Streamlit App UI ---

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
        utils_load_nautobot_data(
            nautobot_token, topology_file, extra_topology_vars_file, nautobot_url
        )
        st.success("Data load process completed (check logs above).")

