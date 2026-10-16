"""A Client that sends requests to the Rust Service."""

from msl.network import Client, Flag

with Client() as client:
    print("Services:", client.services())

    rusty = client.link("Rusty")

    print("Signatures:")
    for key, value in rusty.signatures().items():
        print(f"  {key}{value}")

    add = rusty.add(x=3.2, y=1.5)
    print("add:", add)

    reverse_bytes = rusty.reverse_bytes(b"Hello, world!", compress=int(Flag.ZLIB))
    print("reverse_bytes:", reverse_bytes)

    reverse_string = rusty.reverse_string("Hello, world!")
    print("reverse_string:", reverse_string)

    scale_vector = rusty.scale_vector(2, [1, 2, 3, 4, 5])
    print("scale_vector:", scale_vector)

    # The Service requires a scaling factor to be > 0,
    # so it sends a error message back
    try:
        _ = rusty.scale_vector(-2, [])
    except RuntimeError as e:
        print(f"ERROR! {e}")
