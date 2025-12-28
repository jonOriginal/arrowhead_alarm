"""EliteCloud Alarm Integration."""

from elitecloud_alarm.transport import TcpTransport

from .client import EciClient
from .types import (
    AlarmMessage,
    AlarmState,
    Area,
    ArmingMode,
    ConnectionState,
    EciTransport,
    Output,
    PanelStatus,
    PanelVersion,
    SerialCredentials,
    VersionInfo,
    Zone,
)


async def create_client(
    host: str, port: int, username: str | None, password: str | None
) -> EciClient:
    """Create and connect an EciClient instance to the specified host and port.

    :param host:Hostname or IP address of the Eci alarm panel.
    :param port:TCP port number of the Eci alarm panel.
    :return:An instance of EciClient connected to the panel.
    """
    transport = TcpTransport(host, port)
    if username and password:
        creds = SerialCredentials(username, password)
    else:
        creds = None
    client = EciClient(transport, creds)
    await client.connect()
    return client
