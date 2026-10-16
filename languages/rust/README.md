Rust implementation of a `Client` and `Service` for [msl-network](https://mslnz.github.io/msl-network/latest/).

The `PLAIN` and `CURVE` security mechanisms of `ZeroMQ` are not implemented.

## Getting Started

Install `msl-network` to act as the `Broker`,

```console
pip install msl-network
```

start the `Broker` in a terminal,

```console
msl-network start
```

run the `Service` examples in different terminals,

```console
cargo run --example handle_requests
cargo run --example publish
```

run a `Client` example, for example,

```console
cargo run --example send_requests
```

then run the other `Client` example.

```console
cargo run --example subscribe
```

There are also Python scripts in the `examples` directory that mimic the Rust examples for a `Client`.