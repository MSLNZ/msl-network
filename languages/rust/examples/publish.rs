//! A Service that publishes a value to all subscribed Clients.
//! cargo run --example publish
use msl_network::{Service, Value};
use tokio::time::{Duration, sleep};

async fn publish(service: &mut Service) {
    let mut counter: u64 = 0;
    loop {
        counter += 1;
        let _ = service.publish(Value::json(&counter)).await;
        log::info!("Published {counter}");
        sleep(Duration::from_secs(1)).await;
    }
}

#[tokio::main]
async fn main() -> () {
    clang_log::init(log::Level::Debug, "msl-network");

    let mut heartbeat = Service::new_localhost("Heartbeat");
    heartbeat.connect().await.unwrap();

    tokio::select! {
        _ = publish(&mut heartbeat) => {},
        _ = tokio::signal::ctrl_c() => {}
    }

    heartbeat.disconnect().await;
}
