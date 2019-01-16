"""
Example showing how a digital multimeter that has a non-Ethernet interface,
e.g., GPIB or RS232, can be controlled from any computer that is on the network.
"""
from msl.network import Service


class DigitalMultimeter(Service):

    def __init__(self, config_path, alias):
        """Initialize and start the Service.

        Parameters
        ----------
        config_path : str
            The path to the configuration file that is used by MSL-Equipment.
        alias : str
            The alias of the digital multimeter that was defined in the
            MSL-Equipment configuration file.
        """

        # Initialize the Service. Set the name of the DigitalMultimeter Service,
        # as it will appear on the Network Manager, to be 'Hewlett Packard 34401A'
        # and specify that only 1 Client on the network can control the digital
        # multimeter at any instance in time. Once the Client disconnects from
        # the Network Manager another Client would then be able to link with the
        # DigitalMultimeter Service to control the digital multimeter.
        super().__init__(name='Hewlett Packard 34401A', max_clients=1)

        # Load the MSL-Equipment database
        # See MSL-Equipment for details
        db = Config(config_path).database()

        # Connect to the digital multimeter
        self._dmm = db.equipment[alias].connect()

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
    import sys
    from msl.equipment import Config

    # The user must specify the path to the configuration file that is used by MSL-Equipment
    # and the alias of the EquipmentRecord (see the documentation for MSL-Equipment for more details)
    if len(sys.argv) != 3:
        sys.exit('You must specify the path to the configuration file and the alias of the DMM')

    dmm_service = DigitalMultimeter(*sys.argv[1:])

    # Start the Service
    dmm_service.start()
