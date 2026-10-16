//! A Client that sends requests to a Service.
//! cargo run --example send_requests
use std::collections::BTreeMap;

use bytes::Bytes;
use msl_network::{Arg, BadRequest, Client, Flag, Request};
use tokio;

#[tokio::main]
async fn main() -> () {
    let mut client = Client::new_localhost();
    client.connect().await.unwrap();

    println!("Services: {}", client.services().await.unwrap().join(", "));

    let request = Request::new("Rusty").function("signatures");
    let reply = client.send_and_receive(&request).await.unwrap();
    let signatures: BTreeMap<String, String> = reply.result().unwrap();
    println!("Signatures:");
    for (key, value) in signatures.iter() {
        println!("  {key}{value}");
    }

    let request = Request::new("Rusty")
        .function("add")
        .arg(Arg::F64(3.2))
        .arg(Arg::F64(1.5));
    let reply = client.send_and_receive(&request).await.unwrap();
    let add: f64 = reply.result().unwrap();
    println!("add: {add}");

    let request = Request::new("Rusty")
        .function("reverse_bytes")
        .flag(Flag::PICKLE)
        .arg(Arg::Bytes(b"Hello, world!".into()))
        .kwarg("compress", Arg::U16(Flag::ZLIB.bits()));
    let reply = client.send_and_receive(&request).await.unwrap();
    println!("reverse_bytes: {:?}", Bytes::from(reply.vec()));

    let request = Request::new("Rusty")
        .function("reverse_string")
        .arg(Arg::String("Hello, world!".into()));
    let reply = client.send_and_receive(&request).await.unwrap();
    let reverse_string: String = reply.result().unwrap();
    println!("reverse_string: {reverse_string}");

    let request = Request::new("Rusty")
        .function("scale_vector")
        .arg(Arg::F64(2.0))
        .arg(Arg::Array(
            vec![1, 2, 3, 4, 5]
                .into_iter()
                .map(|v| Arg::I32(v))
                .collect(),
        ));
    let reply = client.send_and_receive(&request).await.unwrap();
    let scale_vector: Vec<f64> = reply.result().unwrap();
    println!("scale_vector: {:?}", scale_vector);

    // The Service requires a scaling factor to be > 0,
    // so it sends a error message back
    let request = Request::new("Rusty")
        .function("scale_vector")
        .arg(Arg::F64(-2.0))
        .arg(Arg::Array(Vec::new()));
    let reply = client.send_and_receive(&request).await.unwrap();
    let result: Result<Vec<f64>, BadRequest> = reply.result();
    println!("ERROR! {}", result.unwrap_err());

    client.disconnect().await;
}
