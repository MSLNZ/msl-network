"""Python code to send requests to the LabVIEW Service."""

from msl.network import Client

with Client() as c:
    print("Services available:", c.services())

    labview = c.link("LabVIEW")
    print(labview.signatures())
    print(labview.add(1, 2))
    print(labview.reverse_string("Hello, world!"))
