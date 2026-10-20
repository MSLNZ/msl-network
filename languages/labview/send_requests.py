"""Python code to send requests to the LabVIEW Service."""

from msl.network import Client

with Client() as c:
    print("Services available:", c.services())

    labview = c.link("LabVIEW")

    print("signatures:")
    for k, v in labview.signatures().items():
        print(f"  {k}{v}")

    print(labview.add(1, 2))

    print(labview.reverse_string("Hello, world!"))

    # If the scaling factor is > 0, the scaled array is returned
    print(labview.scale_array(2, [1, 2]))

    # Otherwise the Service returns an error
    try:
        _ = labview.scale_array(-1, [1, 2])
    except RuntimeError as e:
        print(f"\nWe expected this error because the scaling factor is negative!\n\n{e}")
