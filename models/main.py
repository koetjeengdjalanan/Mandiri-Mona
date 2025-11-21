"""Collection of data models for whole application."""

from typing import Optional

from pydantic import BaseModel, Field, StrictBool, networks


class Devices(BaseModel):
    """
    Represents a network device with authentication credentials.

    This model encapsulates the essential information required to connect to and
    authenticate with network devices such as routers and switches.

    Attributes:
        device_type (str): The type of network device (e.g., 'router', 'switch', 'firewall').
        ip (networks.IPv4Address): The IPv4 address of the device used for connection.
        username (str): The username credential for authenticating to the device.
        password (str): The password credential for authenticating to the device.
        hostname (Optional[str]): An optional hostname for the device.
        monitored (StrictBool): A boolean indicating if the device packet descriptor is monitored.

    Example:
        >>> device = Devices(
        ...     device_type="router",
        ...     ip="192.168.1.1",
        ...     username="admin",
        ...     password="secure_password",
        ...     hostname="Router1",
        ...     monitored=True
        ... )
    """

    device_type: str = Field(..., description="Type of the device, e.g., router, switch.")
    ip: networks.IPv4Address = Field(..., description="IP address of the device.")
    username: str = Field(..., description="Username for device access.")
    password: str = Field(..., description="Password for device access.")
    hostname: Optional[str] = Field(None, description="Optional hostname of the device.")
    monitored: StrictBool = Field(default=False, description="Indicates if the device packet descriptor is monitored.")
