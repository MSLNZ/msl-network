//! A Client that subscribes to a value published by a Service.
//! cargo run --example subscribe
use msl_network::Client;

async fn handle_publications(client: &mut Client) {
    loop {
        let value = client.wait_for_publication().await.unwrap();
        println!("{} published {}", value.service(), value.result::<i32>());
    }
}

#[tokio::main]
async fn main() -> () {
    let mut client = Client::new_localhost();
    client.connect().await.unwrap();

    println!("Services: {}", client.services().await.unwrap().join(", "));
    client.subscribe("Heartbeat").await.unwrap();

    tokio::select! {
        _ = handle_publications(&mut client) => {},
        _ = tokio::signal::ctrl_c() => {}
    }

    client.disconnect().await;
}
