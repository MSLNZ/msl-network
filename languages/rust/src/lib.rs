//! Rust implementation of a [`Client`] and [`Service`] for [msl-network](https://mslnz.github.io/msl-network/latest/).
//!
//! Install the `Broker`,
//!
//! ```console
//! pip install msl-network
//! ```
//!
//! then start the `Broker`.
//!
//! ```console
//! msl-network start
//! ```
//!
//! Examples for how to use a [`Client`] and [`Service`] are found in the
//! [repository](https://github.com/MSLNZ/msl-network/tree/main/languages/rust/).
#![warn(clippy::missing_errors_doc)]
#![deny(missing_docs, clippy::all, clippy::pedantic)]
mod client;
mod message;
mod service;
pub use client::Client;
pub use message::{Arg, BadRequest, Flag, Reply, Request, Value};
pub use service::Service;
