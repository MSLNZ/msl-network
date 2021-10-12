"""
Example showing how a digital multimeter that has a non-Ethernet interface
(e.g., GPIB or RS232) can be controlled from any computer that is on the network.
"""
from msl.network import Service
from msl.equipment import (
    EquipmentRecord,
    ConnectionRecord,
)


class DigitalMultimeter(Service):

    def __init__(self):
        """Initialize the communication with the digital multimeter.

        This script must be run on a computer that the multimeter is
        physically connected to.
        """

        # Initialize the Service. Set the name of the DigitalMultimeter Service,
        # as it will appear on the Network Manager, to be 'Hewlett Packard 34401A'
        # and specify that only 1 Client on the network can control the digital
        # multimeter at any instance in time. Once the Client disconnects from
        # the Network Manager another Client would then be able to link with the
        # DigitalMultimeter Service to control the digital multimeter.
        super().__init__(name='Hewlett Packard 34401A', max_clients=1)

        # Connect to the digital multimeter
        # (see MSL-Equipment for more details)
        record = EquipmentRecord(
            manufacturer='HP',
            model='34401A',
            connection=ConnectionRecord(
                address='COM4',  # RS232 interface
                backend='MSL',
            )
        )
        self._dmm = record.connect()

    def write(self, command: str) -> None:
        """Write a command to the digital multimeter.

        Parameters
        ----------
        command : str
            The command to write.
        """
        self._dmm.write(command)

    def read(self) -> str:
        """Read the response from the digital multimeter.

        Returns
        -------
        str
            The response.
        """
        return self._dmm.read().rstrip()

    def query(self, command: str) -> str:
        """Query the digital multimeter.

        Performs a write then a read.

        Parameters
        ----------
        command : str
            The command to write.

        Returns
        -------
        str
            The response.
        """
        return self._dmm.query(command).rstrip()


if __name__ == '__main__':
    # Initialize and start the DigitalMultimeter Service
    dmm_service = DigitalMultimeter()
    dmm_service.start()
