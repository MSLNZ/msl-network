LabVIEW implementation of a `Client` and `Service` for [msl-network].

## Prerequisites

The LabVIEW VIs are compatible with LabVIEW 2023 Q1 and later (because the VIs require the [virtual environment] feature to be available). Ensure that the bitness of Python corresponds to the bitness of LabVIEW that is installed (i.e., use 32-bit Python with 32-bit LabVIEW). Follow the [overview] from the LabVIEW website for more information about Python and LabVIEW compatibility. If your version of LabVIEW is from 2022 or earlier, you can install the [labview-zmq] package and implement a `Client` and `Service` to build, transfer and extract ZeroMQ messages.

Create a Python virtual environment (using an appropriate bitness and version of Python),

```console
python -m venv venv
```

activate it,

```console
.\venv\Scripts\activate
```

install `msl-network` in the virtual environment,

```console
pip install msl-network
```

then start the Broker.

```console
msl-network start
```

## Examples

The `client.py` module allows LabVIEW code to act as a `Client` and this file is used by `send_requests.vi` and `subscribe.vi`.

The `service.py` module allows LabVIEW code to act as a `Service` and this file is used by `handle_requests.vi` and `publish.vi`.

### Request-Reply Pattern

The `send_requests` (request) and `handle_requests` (reply) files are available to run in both Python and LabVIEW. You can send requests from Python and let LabVIEW handle them (or vice-versa). You may also use the same programming language to both send and handle requests. If you use LabVIEW to both send and handle requests, make sure to set the name of the *Service* that you want to send the request to (in `send_requests.vi`) to be *LabVIEW* instead of the default value *Python*.

### Publish-Subscribe Pattern

The `publish` and `subscribe` files are available to run in both Python and LabVIEW. You can publish values from Python and let LabVIEW subscribe to them (or vice-versa). You may also use the same programming language to publish and subscribe. If you use LabVIEW to both publish and subscribe, make sure to set the name of the *Service* that you want to subscribe to (in `subscribe.vi`) to be *LabVIEW* instead of the default value *Python*.


[msl-network]: https://mslnz.github.io/msl-network/latest/
[virtual environment]: https://www.ni.com/en/support/documentation/supplemental/18/installing-python-for-calling-python-code.html#section-944747733
[overview]: https://www.ni.com/en/support/documentation/supplemental/18/installing-python-for-calling-python-code.html
[labview-zmq]: https://www.vipm.io/package/labview-zmq/