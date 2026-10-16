//! A Service that handles requests from a Client.
//! cargo run --example handle_requests
use std::collections::BTreeMap;

use msl_network::{BadRequest, Flag, Reply, Request, Service};
use serde_bytes::ByteBuf;
use tokio;

/// Define the signatures that this Service provides.
/// A `function-name` to `function-signature` mapping.
fn signatures(request: &Request) -> Result<Reply, BadRequest> {
    let mut map = BTreeMap::new();
    map.insert("add", "(x: f64, y: f64) -> f64");
    map.insert("reverse_bytes", "(data: Vec<u8>, compress: u16) -> Vec<u8>");
    map.insert("reverse_string", "(s: String) -> String");
    map.insert("scale_vector", "(f: f64, vec: Vec<f64>) -> Vec<f64>");
    Ok(Reply::json(request, &map))
}

/// Add two floating-point numbers.
fn add(request: &Request) -> Result<Reply, BadRequest> {
    let x: f64 = request.get("x", 0)?;
    let y: f64 = request.get("y", 1)?;
    let result = x + y;
    Ok(Reply::json(request, &result))
}

/// Reverse a byte vector.
fn reverse_bytes(request: &Request) -> Result<Reply, BadRequest> {
    let mut data: ByteBuf = request.get("data", 0)?;
    let compress: u16 = request.get("compress", 1)?;
    let flag = Flag::from_bits_retain(compress);
    data.reverse();
    Ok(Reply::bytes_with_compression(request, &data, flag))
}

/// Reverse a string.
fn reverse_string(request: &Request) -> Result<Reply, BadRequest> {
    let s: String = request.get("s", 0)?;
    let result: String = s.chars().rev().collect();
    Ok(Reply::json(request, &result))
}

/// Scale a vector.
fn scale_vector(request: &Request) -> Result<Reply, BadRequest> {
    let f: f64 = request.get("f", 0)?;
    let mut vector: Vec<f64> = request.get("vec", 1)?;

    if f <= 0.0 {
        return Err(BadRequest::new(request, "The scaling factor must be > 0"));
    }

    // modify in place
    for x in vector.iter_mut() {
        *x *= f;
    }
    Ok(Reply::json(request, &vector))
}

/// Handle requests.
async fn handle_requests(service: &mut Service) {
    loop {
        log::info!("Waiting for request...");
        match service.receive().await {
            Ok(request) => {
                let function = request.function_name();
                log::info!("Handling `{function}`",);
                let reply = match function {
                    "add" => add(&request),
                    "reverse_string" => reverse_string(&request),
                    "reverse_bytes" => reverse_bytes(&request),
                    "scale_vector" => scale_vector(&request),
                    "signatures" => signatures(&request),
                    _ => Err(BadRequest::new(
                        &request,
                        &format!("Invalid function `{function}`"),
                    )),
                };
                service.send(reply).await;
            }
            Err(error) => log::error!("{error}"),
        }
    }
}

#[tokio::main]
async fn main() -> () {
    clang_log::init(log::Level::Debug, "msl-network");

    let mut rusty = Service::new_localhost("Rusty");
    rusty.connect().await.unwrap();

    tokio::select! {
        _ = handle_requests(&mut rusty) => {},
        _ = tokio::signal::ctrl_c() => {}
    }

    rusty.disconnect().await;
}
