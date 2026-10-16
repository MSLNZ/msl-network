use std::{collections::HashSet, str::FromStr};

use rand::RngExt;
use zeromq::{
    DealerSocket, Socket, SocketOptions, SocketRecv, SocketSend, SubSocket, ZmqError,
    util::PeerIdentity,
};

use crate::{
    Value,
    message::{Reply, Request},
};

/// A Client to send requests and subscribe to published values.
pub struct Client {
    host: String,
    port: u16,
    socket: DealerSocket,
    sub_socket: SubSocket,
    sub_port: u16,
    subscriptions: HashSet<String>,
}

impl Client {
    /// Create a new Client.
    ///
    /// # Parameters
    /// * `host` - The hostname or IP address that the `Broker` is running on.
    /// * `port` - The port number that the `Broker` is running on.
    #[allow(clippy::missing_panics_doc)]
    #[must_use]
    pub fn new(host: &str, port: u16) -> Self {
        let mut rng = rand::rng();
        let id: [u8; 8] = rng.random();
        let client_id = format!("Client[{}]", hex::encode(id));
        let mut options = SocketOptions::default();
        options
            .no_connect_timeout()
            .peer_identity(PeerIdentity::from_str(&client_id).unwrap());

        Client {
            host: host.to_string(),
            port,
            socket: DealerSocket::with_options(options),
            sub_socket: SubSocket::new(),
            sub_port: port + 1,
            subscriptions: HashSet::new(),
        }
    }

    /// Create a new Client that connects to a `Broker` running on `localhost:1875`.
    #[allow(clippy::missing_panics_doc)]
    #[must_use]
    pub fn new_localhost() -> Self {
        Client::new("127.0.0.1", 1875)
    }

    /// Connect to the `Broker`.
    ///
    /// # Errors
    /// If the connection to the `Broker` cannot be established.
    pub async fn connect(&mut self) -> Result<(), ZmqError> {
        let endpoint = format!("tcp://{}:{}", self.host, self.port);
        let sub_endpoint = format!("tcp://{}:{}", self.host, self.sub_port);
        self.socket.connect(&endpoint).await?;
        self.sub_socket.connect(&sub_endpoint).await?;
        log::debug!("Connected to Broker");
        Ok(())
    }

    /// Disconnect from the `Broker`.
    pub async fn disconnect(mut self) {
        let names = self.subscriptions.clone();
        for name in &names {
            let _ = self.unsubscribe(name).await;
        }
        self.socket.close().await;
        self.sub_socket.close().await;
        log::debug!("Disconnected from the Broker");
    }

    /// Wait to receive a [`Reply`].
    ///
    /// # Errors
    /// If a `ZeroMQ` message cannot be received.
    ///
    /// # Panics
    /// If the `ZeroMQ` message cannot be decompressed.
    pub async fn receive(&mut self) -> Result<Reply, ZmqError> {
        let message = self.socket.recv().await?;
        Ok(Reply::from_zmq_message(&message))
    }

    /// Send a [`Request`].
    ///
    /// # Parameters
    /// * `request` - The [`Request`] to send.
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be sent.
    ///
    /// # Panics
    /// If the `request` is not serializable or compressible.
    pub async fn send(&mut self, request: &Request) -> Result<(), ZmqError> {
        self.socket.send(request.to_zmq_message()).await
    }

    /// Send a [`Request`] and wait to receive the [`Reply`].
    ///
    /// # Parameters
    /// * `request` - The [`Request`] to send.
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be sent or received.
    ///
    /// # Panics
    /// If the `request` is not serializable or compressible.
    pub async fn send_and_receive(&mut self, request: &Request) -> Result<Reply, ZmqError> {
        self.send(request).await?;
        self.receive().await
    }

    /// Request the names of the [`Service`][crate::service::Service]s that are
    /// available from the `Broker`.
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be sent or received.
    #[allow(clippy::missing_panics_doc)]
    pub async fn services(&mut self) -> Result<Vec<String>, ZmqError> {
        let request = Request::new("Broker").function("SERVICES");
        let reply = self.send_and_receive(&request).await?;
        Ok(reply.result().unwrap())
    }

    /// Set the port to [`subscribe`][Client::subscribe] to [`publish`][crate::service::Service::publish]ed values.
    ///
    /// Typically, this function does not need to be called as the port is known based on
    /// the port used to connect to a `Broker`.
    ///
    /// If you need to call this function, you must do so before [`connect`][Client::connect] is called.
    pub fn set_subscribe_port(&mut self, port: u16) {
        self.sub_port = port;
    }

    /// Subscribe to a [`Service`][crate::service::Service] that publishes a [`Value`].
    ///
    /// # Parameters
    /// * `name` - The name of the [`Service`][crate::service::Service] to subscribe to.
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be sent.
    pub async fn subscribe(&mut self, name: &str) -> Result<(), ZmqError> {
        if self.subscriptions.contains(name) {
            log::debug!("Already subscribed to {name}");
            Ok(())
        } else {
            log::debug!("Subscribed to {name}");
            self.subscriptions.insert(name.to_string());
            self.sub_socket.subscribe(name).await
        }
    }

    /// Unsubscribe from a [`Service`][crate::service::Service] that publishes a [`Value`].
    ///
    /// # Parameters
    /// * `name` - The name of the [`Service`][crate::service::Service] to unsubscribe from.
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be sent.
    pub async fn unsubscribe(&mut self, name: &str) -> Result<(), ZmqError> {
        if self.subscriptions.contains(name) {
            log::debug!("Unsubscribed from {name}");
            self.subscriptions.remove(name);
            self.sub_socket.unsubscribe(name).await
        } else {
            Ok(())
        }
    }

    /// Wait for a [`Service`][crate::service::Service] to publish a [`Value`].
    ///
    /// # Errors
    /// If the `ZeroMQ` message cannot be received.
    pub async fn wait_for_publication(&mut self) -> Result<Value, ZmqError> {
        let message = self.sub_socket.recv().await?;
        Ok(Value {
            reply: Reply::from_zmq_message(&message),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn connect_disconnect() {
        let mut broker = zeromq::RouterSocket::new();
        broker.bind("tcp://localhost:42894").await.unwrap();
        let mut pub_socket = zeromq::XPubSocket::new();
        pub_socket.bind("tcp://localhost:42895").await.unwrap();

        let mut client = Client::new("localhost", 42894);
        client.connect().await.unwrap();
        client.disconnect().await;

        broker.close().await;
        pub_socket.close().await;
    }

    #[test]
    fn new_localhost() {
        let c = Client::new_localhost();
        assert_eq!(c.host, "127.0.0.1");
        assert_eq!(c.port, 1875);
    }
}
