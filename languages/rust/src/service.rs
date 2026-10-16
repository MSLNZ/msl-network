use std::str::FromStr;

use bytes::Bytes;
use rand::RngExt;
use zeromq::{
    DealerSocket, PubSocket, Socket, SocketOptions, SocketRecv, SocketSend, ZmqError, ZmqMessage,
    util::PeerIdentity,
};

use crate::{Arg, BadRequest, Reply, Request};

/// A Service to handle requests and publish values.
pub struct Service {
    name: String,
    host: String,
    port: u16,
    socket: DealerSocket,
    pub_socket: PubSocket,
    pub_port: u16,
}

impl Service {
    /// Create a new Service.
    ///
    /// # Parameters
    /// * `name` - The name of the Service.
    /// * `host` - The hostname or IP address that the `Broker` is running on.
    /// * `port` - The port number that the `Broker` is running on.
    #[allow(clippy::missing_panics_doc)]
    #[must_use]
    pub fn new(name: &str, host: &str, port: u16) -> Self {
        let mut rng = rand::rng();
        let id: [u8; 8] = rng.random();
        let mut options = SocketOptions::default();
        options.no_connect_timeout().peer_identity(
            PeerIdentity::from_str(&format!("Server[{}]", hex::encode(id))).unwrap(),
        );

        Service {
            name: name.to_string(),
            host: host.to_string(),
            port,
            socket: DealerSocket::with_options(options),
            pub_socket: PubSocket::new(),
            pub_port: port + 2,
        }
    }

    /// Create a new Service that connects to a `Broker` running on `localhost:1875`.
    ///
    /// # Parameters
    /// * `name` - The name of the Service.
    #[allow(clippy::missing_panics_doc)]
    #[must_use]
    pub fn new_localhost(name: &str) -> Self {
        Service::new(name, "127.0.0.1", 1875)
    }

    /// Connect to the `Broker`.
    ///
    /// # Errors
    /// If the connection to the `Broker` cannot be established.
    pub async fn connect(&mut self) -> Result<(), ZmqError> {
        let endpoint = format!("tcp://{}:{}", self.host, self.port);
        self.socket.connect(&endpoint).await?;

        let pub_endpoint = format!("tcp://{}:{}", self.host, self.pub_port);
        self.pub_socket.connect(&pub_endpoint).await?;

        let message = Request::new("Broker")
            .function("SERVICE_AVAILABLE")
            .arg(Arg::String(self.name.clone()))
            .to_zmq_message();

        self.socket.send(message).await?;
        log::debug!("Connected to Broker");
        Ok(())
    }

    /// Disconnect from the `Broker`.
    pub async fn disconnect(mut self) {
        let message = Request::new("Broker")
            .function("SERVICE_UNAVAILABLE")
            .arg(Arg::String(self.name))
            .to_zmq_message();
        let _ = self.socket.send(message).await;
        self.socket.close().await;
        self.pub_socket.close().await;
        log::debug!("Disconnected from the Broker");
    }

    /// Publish a [`Reply`] to all subscribed [`Client`][crate::client::Client]s.
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be sent.
    pub async fn publish(&mut self, reply: Reply) -> Result<(), ZmqError> {
        let mut message = ZmqMessage::from(self.name.clone());
        message.push_back(reply.to_frame());
        self.pub_socket.send(message).await
    }

    /// Wait to receive a [`Request`].
    ///
    /// # Errors
    /// If the [`Request`] is bad (i.e., the message is composed of bad compression or serialization bytes).
    ///
    /// # Panics
    /// If the [`Client`][crate::client::Client] ID cannot be determined from the `ZeroMQ` message.
    pub async fn receive(&mut self) -> Result<Request, BadRequest> {
        match self.socket.recv().await {
            Ok(message) => Request::from_zmq_message(&message),
            Err(error) => Err(BadRequest::from(error, Bytes::new())),
        }
    }

    /// Send the result of a [`Request`].
    ///
    /// # Panics
    /// If the `result` cannot be sent.
    pub async fn send(&mut self, result: Result<Reply, BadRequest>) {
        let message = match result {
            Ok(r) => r.to_zmq_message(),
            Err(e) => e.to_zmq_message(),
        };
        self.socket.send(message).await.unwrap();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn connect_disconnect() {
        let mut broker = zeromq::RouterSocket::new();
        broker.bind("tcp://localhost:51822").await.unwrap();
        let mut sub_socket = zeromq::XSubSocket::new();
        sub_socket.bind("tcp://localhost:51824").await.unwrap();

        let mut client = Service::new("Rusty", "localhost", 51822);
        client.connect().await.unwrap();
        client.disconnect().await;

        broker.close().await;
        sub_socket.close().await;
    }

    #[test]
    fn new_localhost() {
        let s = Service::new_localhost("Rusty");
        assert_eq!(s.name, "Rusty");
        assert_eq!(s.host, "127.0.0.1");
        assert_eq!(s.port, 1875);
    }
}
