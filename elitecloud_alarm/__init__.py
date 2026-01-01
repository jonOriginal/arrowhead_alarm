"""EliteCloud Alarm Integration."""

from elitecloud_alarm.transport import TcpTransport

from .client import EciClient
from .types import (
    AlarmState,
    Area,
    ArmingMode,
    ConnectionState,
    EciTransport,
    Login,
    Output,
    PanelState,
    PanelVersion,
    VersionInfo,
    Zone,
)

__all__ = [
    "PanelState",
    "AlarmState",
    "Area",
    "Zone",
    "Output",
    "ArmingMode",
    "ConnectionState",
    "EciTransport",
    "Login",
    "PanelVersion",
    "VersionInfo",
    "EciClient",
]


def create_tcp_client(
    host: str, port: int, username: str | None = None, password: str | None = None
) -> EciClient:
    """Create an EciClient instance.

    Args:
        host: Hostname or IP address of the Eci alarm panel.
        port: TCP port number of the Eci alarm panel.
        username: Username for authentication.
        password: Password for authentication.

    Returns:
        An instance of EciClient.

    """
    tcp_transport = TcpTransport(host, port)
    if username and password:
        creds = Login(username, password)
    else:
        creds = None
    return EciClient(tcp_transport, creds)
