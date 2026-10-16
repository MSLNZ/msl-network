use std::{collections::HashMap, fmt::Display};

use bitflags::bitflags;
use bytes::{Buf, BufMut, Bytes, BytesMut};
use compcol::{
    bzip2::Bzip2,
    vec::{compress_to_vec, decompress_to_vec},
    xz::Xz,
    zlib::Zlib,
    zstd::Zstd,
};
use serde::{Deserialize, Serialize, de::IntoDeserializer};
use serde_pickle::{DeOptions, SerOptions};
use zeromq::ZmqMessage;

bitflags! {
    /// Serialization and compression flags.
    ///
    /// You may use a single flag or take a bitwise union of one serialization
    /// flag with one compression flag, e.g.,
    ///
    /// * `Flag::JSON` &mdash; JSON serialization. No compression.
    /// * `Flag::ZLIB` &mdash; No serialization. ZLIB compression.
    /// * `Flag::PICKLE | Flag::ZSTD` &mdash; Pickle serialization. ZSTD compression.
    #[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
    pub struct Flag: u16 {
        /// No serialization and no compression.
        const NONE = 0;

        /// (De)compression using the [bzip2](https://sourceware.org/bzip2/) format.
        const BZIP2 = 1 << 0;
        /// (De)compression using the [xz](https://tukaani.org/xz/) format.
        const XZ = 1 << 1;
        /// (De)compression using the [zlib](https://www.zlib.net/) library.
        const ZLIB = 1 << 2;
        /// (De)compression using the [Zstandard](https://facebook.github.io/zstd/doc/api_manual_latest.html) algorithm.
        const ZSTD = 1 << 3;

        /// (De)Serialization in the Python [pickle](https://docs.python.org/3/library/pickle.html) format.
        const PICKLE = 1 << 8;
        /// (De)Serialization in the [JSON](https://www.json.org/json-en.html) format.
        const JSON = 1 << 9;
        // const ORJSON = 1 << 10;

        /// Bitwise OR of all (de)compression flags.
        const COMPRESSION = Self::BZIP2.bits() | Self::XZ.bits() | Self::ZLIB.bits() | Self::ZSTD.bits();
        /// Bitwise OR of all (de)serialization flags.
        const SERIALIZATION = Self::PICKLE.bits() | Self::JSON.bits();
    }
}

/// A bad request is received.
#[derive(Debug)]
pub struct BadRequest {
    sender_id: Bytes,
    id: u64,
    reason: String,
}

impl BadRequest {
    /// Create a [`BadRequest`].
    ///
    /// # Parameters
    /// * `request` - The [`Request`] instance.
    /// * `reason` - The reason why the [`Request`] was bad.
    pub fn new(request: &Request, reason: &str) -> Self {
        BadRequest {
            sender_id: request.client_id.clone(),
            id: request.id,
            reason: reason.to_string(),
        }
    }

    /// Create a new [`BadRequest`] with a `id=0` and the `reason` from an error.
    pub(crate) fn from<T: Display>(error: T, sender_id: Bytes) -> Self {
        BadRequest {
            sender_id,
            id: 0,
            reason: error.to_string(),
        }
    }

    /// Convert the [`BadRequest`] to a `ZeroMQ` message.
    #[allow(clippy::missing_panics_doc)]
    pub(crate) fn to_zmq_message(&self) -> ZmqMessage {
        let data = serde_json::to_vec(&self.reason).unwrap();
        let mut buf = BytesMut::with_capacity(11 + data.len());
        buf.put_u16_le(Flag::JSON.bits());
        buf.put_u64_le(self.id);
        buf.put_u8(u8::from(false));
        buf.put_slice(&data);

        let mut message = ZmqMessage::from(self.sender_id.clone());
        message.push_back(buf.freeze());
        message
    }
}

impl Display for BadRequest {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.reason)
    }
}

/// A serialized value in either the JSON or Python Pickle format.
#[derive(Debug, Deserialize)]
#[serde(untagged)]
#[allow(clippy::upper_case_acronyms)]
pub(crate) enum SerializedValue {
    JSON(serde_json::Value),
    PICKLE(serde_pickle::Value),
}

/// A serialized request.
#[derive(Debug, Default, Deserialize)]
pub(crate) struct SerializedRequest {
    /// The ID of the request.
    id: u64,

    /// The name of the function on the [`Service`][crate::service::Service] to call.
    function: String,

    /// The arguments that the [`Service`][crate::service::Service]'s function requires.
    args: Vec<SerializedValue>,

    /// The keyword arguments that the [`Service`][crate::service::Service]'s function requires.
    kwargs: HashMap<String, SerializedValue>,
}

/// A [`Request`] argument.
#[derive(Debug, Serialize)]
#[serde(untagged)]
#[allow(missing_docs)]
pub enum Arg {
    None,
    Bool(bool),
    I8(i8),
    U8(u8),
    I16(i16),
    U16(u16),
    I32(i32),
    U32(u32),
    I64(i64),
    U64(u64),
    F32(f32),
    F64(f64),
    String(String),
    Bytes(Vec<u8>),
    Array(Vec<Arg>),
    Map(HashMap<String, Arg>),
}

/// Build a message to send to a [`Service`][crate::service::Service].
///
/// ```
/// use msl_network::{Arg, Flag, Request};
///
/// let request = Request::new("Rusty")
///     .function("reverse_bytes")
///     .flag(Flag::PICKLE)
///     .arg(Arg::Bytes(b"Hello, world!".into()))
///     .kwarg("compress", Arg::U16(Flag::ZLIB.bits()));
/// ```
#[derive(Debug)]
pub struct Request {
    /// The arguments that the [`Service`][crate::service::Service]'s function requires.
    args: Vec<Arg>,

    /// The ID of the Client associated with the request.
    client_id: Bytes,

    /// The serialization and compression flags to use to build the message.
    flag: Flag,

    /// The name of the function on the [`Service`][crate::service::Service] to call.
    fcn: String,

    /// The ID of the request.
    id: u64,

    /// The keyword arguments that the [`Service`][crate::service::Service]'s function requires.
    kwargs: HashMap<String, Arg>,

    /// A request that is serialized.
    serialized: SerializedRequest,

    /// The name of the Service to handle the request.
    service: String,
}

impl Request {
    /// Build a new request.
    ///
    /// By default, JSON is used to serialize the request and no compression is applied.
    /// Call [`flag`][Request::flag] to change how the request is serialized and compressed.
    ///
    /// # Parameters
    /// * `service` - The name of the [`Service`][crate::service::Service] to handle the request.
    #[must_use]
    pub fn new(service: &str) -> Self {
        Request {
            args: Vec::new(),
            client_id: Bytes::new(),
            flag: Flag::JSON,
            fcn: String::new(),
            id: 0,
            kwargs: HashMap::new(),
            serialized: SerializedRequest::default(),
            service: service.to_string(),
        }
    }

    /// Add an argument that the function on the [`Service`][crate::service::Service] requires.
    #[must_use]
    pub fn arg(self, arg: Arg) -> Self {
        let mut args = self.args;
        args.push(arg);
        Request { args, ..self }
    }

    /// Set the serialization and compression flag to use to build the request message.
    ///
    /// You may use a single flag or take a bitwise union of one serialization
    /// flag with one compression flag, e.g.,
    ///
    /// * `Flag::JSON` &mdash; JSON serialization. No compression.
    /// * `Flag::ZLIB` &mdash; No serialization. ZLIB compression.
    /// * `Flag::PICKLE | Flag::ZSTD` &mdash; Pickle serialization. ZSTD compression.
    #[must_use]
    pub fn flag(self, flag: Flag) -> Self {
        Request { flag, ..self }
    }

    /// Set the name of the function on the [`Service`][crate::service::Service] to call.
    #[must_use]
    pub fn function(self, name: &str) -> Self {
        Request {
            fcn: name.to_string(),
            ..self
        }
    }

    /// Get the name of the function to handle the [`Request`].
    pub fn function_name(&self) -> &str {
        self.fcn.as_str()
    }

    /// Get a parameter in the specified type.
    ///
    /// This function will first check if the [`Request`] contains a keyword argument named `key`.
    /// If it exists, the corresponding value is returned. If the `key` is not found, then
    /// the argument value at position `index` is returned. The first argument is at index 0.
    ///
    /// # Errors
    /// If neither the `key` or `index` exist.
    pub fn get<'de, T>(&'de self, key: &str, index: usize) -> Result<T, BadRequest>
    where
        T: Deserialize<'de>,
    {
        if let Some(v) = self
            .serialized
            .kwargs
            .get(key)
            .or_else(|| self.serialized.args.get(index))
        {
            match v {
                SerializedValue::JSON(v) => {
                    let deserializer = v.into_deserializer();
                    T::deserialize(deserializer).map_err(|e| BadRequest {
                        sender_id: self.client_id.clone(),
                        id: self.id,
                        reason: e.to_string(),
                    })
                }
                SerializedValue::PICKLE(v) => {
                    serde_pickle::from_value(v.clone()).map_err(|e| BadRequest {
                        sender_id: self.client_id.clone(),
                        id: self.id,
                        reason: e.to_string(),
                    })
                }
            }
        } else {
            Err(BadRequest {
                sender_id: self.client_id.clone(),
                id: self.id,
                reason: format!(
                    "A parameter with name '{key}' (or at position {index}) was not specified in the request"
                ),
            })
        }
    }

    /// Set the ID of the request.
    ///
    /// The ID is used by a [`Client`][crate::client::Client] to keep track of which
    /// [`Reply`] corresponds to which request when sending asynchronous requests to
    /// one or more [`Service`][crate::service::Service]s.
    #[must_use]
    pub fn id(self, value: u64) -> Self {
        Request { id: value, ..self }
    }

    /// Add a keyword (named) argument that the function on the [`Service`][crate::service::Service] requires.
    #[must_use]
    pub fn kwarg(self, key: &str, value: Arg) -> Self {
        let mut kwargs = self.kwargs;
        kwargs.insert(key.to_string(), value);
        Request { kwargs, ..self }
    }

    /// Convert a `ZeroMQ` message into a [`Request`].
    pub(crate) fn from_zmq_message(message: &ZmqMessage) -> Result<Request, BadRequest> {
        let client_id = message.get(0).unwrap().clone();
        let frame = message.get(1).unwrap();
        let flag = Flag::from_bits_retain(frame.slice(0..2).get_u16_le());

        let slice = match decompress(&frame.slice(2..), flag) {
            Ok(data) => data,
            Err(error) => return Err(BadRequest::from(error, client_id)),
        };

        let serialized: SerializedRequest = match flag & Flag::SERIALIZATION {
            Flag::PICKLE => match serde_pickle::from_slice(&slice, DeOptions::default()) {
                Ok(request) => request,
                Err(error) => return Err(BadRequest::from(error, client_id)),
            },
            // otherwise match JSON or ORJSON
            _ => match serde_json::from_slice(&slice) {
                Ok(request) => request,
                Err(error) => return Err(BadRequest::from(error, client_id)),
            },
        };

        Ok(Request {
            args: Vec::new(),
            client_id,
            flag,
            fcn: serialized.function.clone(),
            id: serialized.id,
            kwargs: HashMap::new(),
            serialized,
            service: String::new(),
        })
    }

    /// Convert the message into a `ZeroMQ` frame.
    ///
    /// # Panics
    /// If the `request` is not serializable or compressible.
    pub(crate) fn to_zmq_message(&self) -> ZmqMessage {
        let tuple = (&self.id, &self.fcn, &self.args, &self.kwargs);
        let data = match self.flag & Flag::SERIALIZATION {
            Flag::PICKLE => serde_pickle::to_vec(&tuple, SerOptions::default()).unwrap(),
            _ => serde_json::to_vec(&tuple).unwrap(),
        };
        let compressed = compress(&data, self.flag);
        let mut buf = BytesMut::with_capacity(2 + compressed.len());
        buf.put_u16_le(self.flag.bits());
        buf.put_slice(&compressed);

        let mut msg = ZmqMessage::from(self.service.clone());
        msg.push_back(buf.freeze());
        msg
    }
}

/// The reply to a [`Request`].
#[derive(Debug, PartialEq)]
pub struct Reply {
    sender_id: Bytes,
    flag: Flag,
    request_id: u64,
    ok: bool,
    value: Vec<u8>,
}

impl Reply {
    /// Create a [`Reply`] where the `value` is an empty byte vector.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    pub fn empty(request: &Request) -> Self {
        Reply::bytes(request, b"")
    }

    /// Create a [`Reply`] where the `value` is serialized in the JSON format.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    /// * `value` - The value to return.
    ///
    /// # Panics
    /// If the `value` is not JSON serializable.
    pub fn json<T: Serialize + ?Sized>(request: &Request, value: &T) -> Self {
        Reply {
            sender_id: request.client_id.clone(),
            flag: Flag::JSON,
            request_id: request.id,
            ok: true,
            value: serde_json::to_vec(value).expect("The value is not JSON serializable"),
        }
    }

    /// Create a [`Reply`] where the `value` is serialized in the JSON format and then compressed.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    /// * `value` - The value to return.
    /// * `flag` - The compression format to use.
    ///
    /// # Panics
    /// If the `value` is not JSON serializable or compressible.
    pub fn json_with_compression<T: Serialize + ?Sized>(
        request: &Request,
        value: &T,
        flag: Flag,
    ) -> Self {
        Reply {
            sender_id: request.client_id.clone(),
            flag: Flag::JSON | flag,
            request_id: request.id,
            ok: true,
            value: compress(
                &serde_json::to_vec(value).expect("The value is not JSON serializable"),
                flag,
            ),
        }
    }

    /// Create a [`Reply`] where the `value` is serialized in the Python pickle format.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    /// * `value` - The value to return.
    ///
    /// # Panics
    /// If the `value` is not pickle serializable.
    pub fn pickle<T: Serialize>(request: &Request, value: &T) -> Self {
        Reply {
            sender_id: request.client_id.clone(),
            flag: Flag::PICKLE,
            request_id: request.id,
            ok: true,
            value: serde_pickle::to_vec(value, SerOptions::default())
                .expect("The value is not pickle serializable"),
        }
    }

    /// Create a [`Reply`] where the `value` is serialized in the Python pickle format and then compressed.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    /// * `value` - The value to return.
    /// * `flag` - The compression format to use.
    ///
    /// # Panics
    /// If the `result` is not pickle serializable or compressible.
    pub fn pickle_with_compression<T: Serialize>(request: &Request, value: &T, flag: Flag) -> Self {
        Reply {
            sender_id: request.client_id.clone(),
            flag: Flag::PICKLE | flag,
            request_id: request.id,
            ok: true,
            value: compress(
                &serde_pickle::to_vec(value, SerOptions::default())
                    .expect("The value is not pickle serializable"),
                flag,
            ),
        }
    }

    /// Create a [`Reply`] where the `value` is a byte vector.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    /// * `value` - The value to return.
    pub fn bytes<T: Into<Vec<u8>>>(request: &Request, value: T) -> Self {
        Reply {
            sender_id: request.client_id.clone(),
            flag: Flag::NONE,
            request_id: request.id,
            ok: true,
            value: value.into(),
        }
    }

    /// Create a [`Reply`] where the `value` is a compressed byte vector.
    ///
    /// # Parameters
    /// * `request` - The [`Request`] associated with this reply.
    /// * `value` - The value to return.
    /// * `flag` - The compression format to use.
    pub fn bytes_with_compression(request: &Request, value: &[u8], flag: Flag) -> Self {
        Reply {
            sender_id: request.client_id.clone(),
            flag,
            request_id: request.id,
            ok: true,
            value: compress(value, flag),
        }
    }

    /// Get the ID of the [`Request`].
    pub fn id(&self) -> u64 {
        self.request_id
    }

    /// Get the `value` of the reply in the specified type.
    ///
    /// # Errors
    /// If the [`Request`] was bad.
    ///
    /// # Panics
    /// If the `value` cannot be deserialized into `T`.
    #[allow(clippy::missing_panics_doc)]
    pub fn result<'de, T>(&'de self) -> Result<T, BadRequest>
    where
        T: Deserialize<'de>,
    {
        let sender_id = self.sender_id.clone();
        let ser_value: SerializedValue = match self.flag & Flag::SERIALIZATION {
            Flag::PICKLE => match serde_pickle::from_slice(&self.value, DeOptions::default()) {
                Ok(v) => v,
                Err(e) => {
                    return Err(BadRequest {
                        sender_id,
                        id: self.request_id,
                        reason: e.to_string(),
                    });
                }
            },
            _ => match serde_json::from_slice(&self.value) {
                Ok(v) => v,
                Err(e) => {
                    return Err(BadRequest {
                        sender_id,
                        id: self.request_id,
                        reason: e.to_string(),
                    });
                }
            },
        };

        if self.ok {
            match ser_value {
                SerializedValue::JSON(v) => {
                    let deserializer = v.into_deserializer();
                    Ok(T::deserialize(deserializer).unwrap())
                }
                SerializedValue::PICKLE(v) => Ok(serde_pickle::from_value(v).unwrap()),
            }
        } else {
            let reason: String = match ser_value {
                SerializedValue::JSON(v) => serde_json::from_value(v).unwrap(),
                SerializedValue::PICKLE(v) => serde_pickle::from_value(v).unwrap(),
            };
            Err(BadRequest {
                sender_id,
                id: self.request_id,
                reason,
            })
        }
    }

    /// Whether the [`Request`] was successfully processed.
    pub fn success(&self) -> bool {
        self.ok
    }

    /// Get the `value` of the reply as a byte vector.
    pub fn vec(self) -> Vec<u8> {
        self.value
    }

    /// Create a [`Reply`] from a `ZeroMQ` message.
    ///
    /// # Panics
    /// If the `value` cannot be decompressed.
    pub(crate) fn from_zmq_message(message: &ZmqMessage) -> Self {
        let service_id = message.get(0).unwrap().clone();
        let frame = message.get(1).unwrap();
        let flag = Flag::from_bits_retain(frame.slice(0..2).get_u16_le());
        let request_id = frame.slice(2..10).get_u64_le();
        let ok = frame.slice(10..11).get_u8() == 1u8;
        Reply {
            sender_id: service_id,
            flag,
            request_id,
            ok,
            value: decompress(&frame.slice(11..), flag).unwrap(),
        }
    }

    /// Convert the [`Reply`] to a `ZeroMQ` frame.
    pub(crate) fn to_frame(&self) -> Bytes {
        let mut buf = BytesMut::with_capacity(11 + self.value.len());
        buf.put_u16_le(self.flag.bits());
        buf.put_u64_le(self.request_id);
        buf.put_u8(u8::from(self.ok));
        buf.put_slice(&self.value);
        buf.freeze()
    }

    /// Convert the [`Reply`] to a `ZeroMQ` message.
    pub(crate) fn to_zmq_message(&self) -> ZmqMessage {
        let mut message = ZmqMessage::from(self.sender_id.clone());
        message.push_back(self.to_frame());
        message
    }
}

/// A value to [`publish`][crate::service::Service::publish] to all subscribed [`Client`][crate::client::Client]s.
#[derive(Debug)]
pub struct Value {
    pub(crate) reply: Reply,
}

impl Value {
    /// Create a [`Reply`] where the `value` is serialized in the JSON format.
    ///
    /// # Parameters
    /// * `value` - The value to publish.
    ///
    /// # Panics
    /// If the `value` is not JSON serializable.
    pub fn json<T: Serialize + ?Sized>(value: &T) -> Reply {
        Reply::json(&Request::new(""), value)
    }

    /// Create a [`Reply`] where the `value` is serialized in the JSON format and then compressed.
    ///
    /// # Parameters
    /// * `value` - The value to publish.
    /// * `flag` - The compression format to use.
    ///
    /// # Panics
    /// If the `value` is not JSON serializable or compressible.
    pub fn json_with_compression<T: Serialize + ?Sized>(value: &T, flag: Flag) -> Reply {
        Reply::json_with_compression(&Request::new(""), value, flag)
    }

    /// Create a [`Reply`] where the `value` is serialized in the Python pickle format.
    ///
    /// # Parameters
    /// * `value` - The value to publish.
    ///
    /// # Panics
    /// If the `value` is not pickle serializable.
    pub fn pickle<T: Serialize>(value: &T) -> Reply {
        Reply::pickle(&Request::new(""), value)
    }

    /// Create a [`Reply`] where the `value` is serialized in the Python pickle format and then compressed.
    ///
    /// # Parameters
    /// * `value` - The value to publish.
    /// * `flag` - The compression format to use.
    ///
    /// # Panics
    /// If the `value` is not pickle serializable or compressible.
    pub fn pickle_with_compression<T: Serialize>(value: &T, flag: Flag) -> Reply {
        Reply::pickle_with_compression(&Request::new(""), value, flag)
    }

    /// Create a [`Reply`] where the `value` is a byte vector.
    ///
    /// # Parameters
    /// * `value` - The value to publish.
    pub fn bytes<T: Into<Vec<u8>>>(value: T) -> Reply {
        Reply::bytes(&Request::new(""), value)
    }

    /// Create a [`Reply`] where the `value` is a compressed byte vector.
    ///
    /// # Parameters
    /// * `value` - The value to publish.
    /// * `flag` - The compression format to use.
    #[must_use]
    pub fn bytes_with_compression(value: &[u8], flag: Flag) -> Reply {
        Reply::bytes_with_compression(&Request::new(""), value, flag)
    }

    /// Get the [`publish`][crate::service::Service::publish]ed value in the specified type.
    ///
    /// # Panics
    /// If the `value` cannot be deserialized into `T`.
    pub fn result<'de, T>(&'de self) -> T
    where
        T: Deserialize<'de>,
    {
        self.reply.result().unwrap()
    }

    /// Get the name of the [`Service`][crate::service::Service] that
    /// [`publish`][crate::service::Service::publish]ed the value.
    #[allow(clippy::missing_panics_doc)]
    pub fn service(&self) -> String {
        String::from_utf8(self.reply.sender_id.to_vec()).unwrap()
    }

    /// Get the [`publish`][crate::service::Service::publish]ed value as a byte vector.
    pub fn vec(self) -> Vec<u8> {
        self.reply.vec()
    }
}

pub(crate) fn compress(data: &[u8], flag: Flag) -> Vec<u8> {
    match flag & Flag::COMPRESSION {
        Flag::BZIP2 => compress_to_vec::<Bzip2>(data).expect("Failed to compress using Bzip2"),
        Flag::XZ => compress_to_vec::<Xz>(data).expect("Failed to compress using XZ"),
        Flag::ZLIB => compress_to_vec::<Zlib>(data).expect("Failed to compress using ZLIB"),
        Flag::ZSTD => compress_to_vec::<Zstd>(data).expect("Failed to compress using ZSTD"),
        _ => data.to_vec(),
    }
}

pub(crate) fn decompress(data: &Bytes, flag: Flag) -> Result<Vec<u8>, compcol::Error> {
    match flag & Flag::COMPRESSION {
        Flag::BZIP2 => decompress_to_vec::<Bzip2>(data),
        Flag::XZ => decompress_to_vec::<Xz>(data),
        Flag::ZLIB => decompress_to_vec::<Zlib>(data),
        Flag::ZSTD => decompress_to_vec::<Zstd>(data),
        _ => Ok(data.to_vec()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_bytes::ByteBuf;

    #[test]
    fn reply_empty() {
        let request = Request::new("").id(1);
        let reply = Reply::empty(&request);
        let expect = b"\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
        assert_eq!(Reply::from_zmq_message(&reply.to_zmq_message()), reply);
        assert_eq!(reply.vec(), b"");
    }

    #[test]
    fn reply_bytes() {
        let request = Request::new("").id(1);
        let reply = Reply::bytes(&request, b"hello, world!");
        let expect = b"\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01hello, world!";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
        assert_eq!(Reply::from_zmq_message(&reply.to_zmq_message()), reply);
        assert_eq!(reply.vec(), b"hello, world!");
    }

    #[test]
    fn reply_bytes_with_compression_bzip2() {
        let request = Request::new("").id(1);
        let reply = Reply::bytes_with_compression(&request, b"hello, world!", Flag::BZIP2);
        let expect = b"\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01BZh61AY&SY\xe7\xcc\xea\x05\x00\x00\x02\x91\x80`\x04\x06D\x90\x80 \x001\x000 \x0c%\xe1$%\xb0\xc3\xf1w$S\x85\t\x0e|\xce\xa0P";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
    }

    #[test]
    fn reply_bytes_with_compression_xz() {
        // cSpell: ignore chello
        let request = Request::new("").id(1);
        let reply = Reply::bytes_with_compression(&request, b"hello, world!", Flag::XZ);
        let expect = b"\x02\0\x01\0\0\0\0\0\0\0\x01\xfd7zXZ\0\0\x01i\"\xde6\x02\0!\x01\x14\0\0\0\xff\xe7\xec\t\x01\0\x0chello, world!\0\0\0\0\x13\x8d\x98X\0\x01!\ru\xdc\xa8\xd2\x90B\x99\r\x01\0\0\0\0\x01YZ";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
    }

    #[test]
    fn reply_bytes_with_compression_zlib() {
        let request = Request::new("").id(1);
        let reply = Reply::bytes_with_compression(&request, b"hello, world!", Flag::ZLIB);
        let expect = b"\x04\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01x\x9c\xcbH\xcd\xc9\xc9\xd7Q(\xcf/\xcaIQ\x04\x00!\xfe\x04\xaa";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
    }

    #[test]
    fn reply_bytes_with_compression_zstd() {
        let request = Request::new("").id(1);
        let reply = Reply::bytes_with_compression(&request, b"hello, world!", Flag::ZSTD);
        let expect = b"\x08\0\x01\0\0\0\0\0\0\0\x01(\xb5/\xfd\0pi\0\0hello, world!";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
    }

    #[test]
    fn reply_json() {
        let request = Request::new("").id(1);
        let reply = Reply::json(&request, &String::from("hello, world!"));
        let expect = b"\x00\x02\x01\x00\x00\x00\x00\x00\x00\x00\x01\"hello, world!\"";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
        assert_eq!(Reply::from_zmq_message(&reply.to_zmq_message()), reply);
        assert_eq!(reply.vec(), b"\"hello, world!\"");
    }

    #[test]
    fn reply_json_with_compression_zlib() {
        let request = Request::new("").id(1);
        let reply =
            Reply::json_with_compression(&request, &"hello, world!".to_string(), Flag::ZLIB);
        let expect = b"\x04\x02\x01\x00\x00\x00\x00\x00\x00\x00\x01x\x9cS\xcaH\xcd\xc9\xc9\xd7Q(\xcf/\xcaIQT\x02\x00(\xc9\x04\xee";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
    }

    #[test]
    fn reply_pickle() {
        let request = Request::new("").id(1);
        let reply = Reply::pickle(&request, &String::from("hello, world!"));
        let expect =
            b"\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x80\x03X\r\x00\x00\x00hello, world!.";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
        assert_eq!(Reply::from_zmq_message(&reply.to_zmq_message()), reply);
    }

    #[test]
    fn reply_pickle_with_compression_bzip2() {
        let request = Request::new("").id(1);
        let reply =
            Reply::pickle_with_compression(&request, &String::from("hello, world!"), Flag::BZIP2);
        let expect = b"\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01BZh61AY&SY\xfe\xe1\x88\x9a\x00\x00\nS\xc0H\x02`\x05\x00@\x06D\x90\x80@\x00 \x001L\x00\x13B \x0f(l\xa5\xab\x0cl\xc9\x13%,C\t\xfc]\xc9\x14\xe1BC\xfb\x86\"h";
        assert_eq!(reply.to_frame(), Bytes::copy_from_slice(expect));
    }

    #[test]
    fn compress_flag_json() {
        let value = compress(b"hello, world!", Flag::JSON);
        assert_eq!(value, Vec::from(b"hello, world!"));
    }

    #[test]
    fn bad_request() {
        let request = Request::new("").id(2);
        let bad = BadRequest::new(&request, "bad function name");
        let msg = bad.to_zmq_message();
        let expect = b"\x00\x02\x02\x00\x00\x00\x00\x00\x00\x00\x00\"bad function name\"";
        assert_eq!(*msg.get(1).unwrap(), Bytes::copy_from_slice(expect));
        assert_eq!(bad.to_string(), "bad function name");
    }

    #[test]
    fn request_from_zmq_message_1() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[e2858be52b04bf12]"));
        msg.push_back(Bytes::copy_from_slice(b"\0\x01\x80\x05\x95\x14\0\0\0\0\0\0\0(K\x03\x8c\x03add\x94K\x01K\x02\x86\x94}\x94t\x94."));

        let request = Request::from_zmq_message(&msg).unwrap();
        assert_eq!(request.id, 3);
        assert_eq!(request.fcn, "add");
        assert_eq!(request.function_name(), "add");
        assert_eq!(request.args.len(), 0);
        assert_eq!(request.kwargs.len(), 0);
        assert_eq!(request.serialized.args.len(), 2);
        assert_eq!(request.serialized.kwargs.len(), 0);

        let x: f64 = request.get("x", 0).unwrap();
        assert_eq!(x, 1.0);

        let y: f64 = request.get("y", 1).unwrap();
        assert_eq!(y, 2.0);

        let y: Result<String, BadRequest> = request.get("y", 1);
        let err = y.expect_err("should not panic");
        assert_eq!(err.id, 3);
        assert_eq!(err.reason, "invalid type: integer `2`, expected a string");

        let z: Result<f64, BadRequest> = request.get("z", 2);
        let err = z.expect_err("should not panic");
        assert_eq!(err.id, 3);
        assert_eq!(
            err.reason,
            "A parameter with name 'z' (or at position 2) was not specified in the request"
        );
    }

    #[test]
    fn request_from_zmq_message_2() {
        // cSpell: ignore bhello
        let mut msg = ZmqMessage::from(Vec::from(b"Client[e2858be52b04bf12]"));
        msg.push_back(Bytes::copy_from_slice(b"\0\x01\x80\x05\x95*\0\0\0\0\0\0\0(K\x02\x8c\rreverse_bytes\x94C\x0bhello world\x94K\0\x86\x94}\x94t\x94."));

        let request = Request::from_zmq_message(&msg).unwrap();
        assert_eq!(request.id, 2);
        assert_eq!(request.fcn, "reverse_bytes");
        assert_eq!(request.args.len(), 0);
        assert_eq!(request.kwargs.len(), 0);
        assert_eq!(request.serialized.args.len(), 2);
        assert_eq!(request.serialized.kwargs.len(), 0);

        let data: serde_bytes::ByteBuf = request.get("data", 0).unwrap();
        let compress: u16 = request.get("compress", 1).unwrap();
        assert_eq!(data.to_vec(), Vec::from(b"hello world"));
        assert_eq!(compress, 0);

        let result: Result<Vec<u8>, BadRequest> = request.get("data", 0);
        let err = result.expect_err("should not panic");
        assert_eq!(err.id, 2);
        assert_eq!(
            err.reason,
            "decoding error: invalid type: byte array, expected a sequence"
        );
    }

    #[test]
    fn request_from_zmq_message_bad_bytes() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[e2858be52b04bf12]"));
        msg.push_back(Bytes::copy_from_slice(
            b"\0\x01\x80\x05\x95\x14\0\0\0\0\0\0\0(K\x03\x8c\x03WRONG-EOF",
        ));

        let result = Request::from_zmq_message(&msg);
        let err = result.expect_err("should not panic");
        assert_eq!(err.reason, "eval error at offset 21: EOF while parsing");
    }

    #[test]
    fn request_from_zmq_message_json() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[369caeb12220d07b]"));
        msg.push_back(Bytes::copy_from_slice(b"\0\x02[2,\"signatures\",[],{}]"));

        let request = Request::from_zmq_message(&msg).unwrap();
        assert_eq!(request.id, 2);
        assert_eq!(request.fcn, "signatures");
        assert_eq!(request.args.len(), 0);
        assert_eq!(request.kwargs.len(), 0);
        assert_eq!(request.serialized.args.len(), 0);
        assert_eq!(request.serialized.kwargs.len(), 0);
    }

    #[test]
    fn request_from_zmq_message_orjson() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[a]"));
        msg.push_back(Bytes::copy_from_slice(b"\0\x04[1,\"foo\",[1],{\"x\":2}]"));

        let request = Request::from_zmq_message(&msg).unwrap();
        assert_eq!(request.id, 1);
        assert_eq!(request.fcn, "foo");
        assert_eq!(request.args.len(), 0);
        assert_eq!(request.kwargs.len(), 0);
        assert_eq!(request.serialized.args.len(), 1);
        assert_eq!(request.serialized.kwargs.len(), 1);
    }

    #[test]
    fn request_from_zmq_message_json_bad_string() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[369caeb12220d07b]"));
        msg.push_back(Bytes::copy_from_slice(b"\0\x02[2,\"signatures,[],{}]"));

        let result = Request::from_zmq_message(&msg);
        let err = result.expect_err("should not panic");
        assert_eq!(err.reason, "EOF while parsing a string at line 1 column 21");
    }

    #[test]
    fn request_from_zmq_message_bad_bzip2_bytes() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[369caeb12220d07b]"));
        msg.push_back(Bytes::copy_from_slice(b"\x01\x02XXX"));

        let result = Request::from_zmq_message(&msg);
        let err = result.expect_err("should not panic");
        assert_eq!(err.reason, "unexpected end of input");
    }

    #[test]
    fn request_from_zmq_message_bad_xz_bytes() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[369caeb12220d07b]"));
        msg.push_back(Bytes::copy_from_slice(b"\x02\x02XXX"));

        let result = Request::from_zmq_message(&msg);
        let err = result.expect_err("should not panic");
        assert_eq!(err.reason, "unexpected end of input");
    }

    #[test]
    fn request_from_zmq_message_bad_zlib_bytes() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[369caeb12220d07b]"));
        msg.push_back(Bytes::copy_from_slice(b"\x04\x02XXX"));

        let result = Request::from_zmq_message(&msg);
        let err = result.expect_err("should not panic");
        assert_eq!(err.reason, "container header is malformed");
    }

    #[test]
    fn request_from_zmq_message_bad_zstd_bytes() {
        let mut msg = ZmqMessage::from(Vec::from(b"Client[369caeb12220d07b]"));
        msg.push_back(Bytes::copy_from_slice(b"\x08\x02XXX"));

        let result = Request::from_zmq_message(&msg);
        let err = result.expect_err("should not panic");
        assert_eq!(err.reason, "unexpected end of input");
    }

    #[test]
    fn request_json() {
        let r = Request::new("Whatever")
            .function("foo")
            .arg(Arg::None)
            .arg(Arg::Bool(true))
            .arg(Arg::F64(1.2))
            .arg(Arg::U16(10000))
            .kwarg("x", Arg::U8(100))
            .kwarg("foo", Arg::String("bar".to_string()))
            .kwarg(
                "array",
                Arg::Array(Vec::from([Arg::F64(2.), Arg::F32(5e1)])),
            );

        let msg = r.to_zmq_message();
        let request = Request::from_zmq_message(&msg).unwrap();
        assert_eq!(request.id, 0);
        assert_eq!(request.fcn, "foo");

        let first: Option<i8> = request.get("missing", 0).unwrap();
        assert_eq!(first, None);

        let second: bool = request.get("missing", 1).unwrap();
        assert!(second);

        let third: f64 = request.get("missing", 2).unwrap();
        assert_eq!(third, 1.2);

        let fourth: u16 = request.get("missing", 3).unwrap();
        assert_eq!(fourth, 10000);

        let x: i8 = request.get("x", 100).unwrap();
        assert_eq!(x, 100);

        let foo: String = request.get("foo", 100).unwrap();
        assert_eq!(foo, "bar");

        let array: Vec<f64> = request.get("array", 100).unwrap();
        assert_eq!(array, vec![2.0, 50.0]);
    }

    #[test]
    fn request_pickle() {
        let r = Request::new("Whatever")
            .id(98)
            .function("any")
            .flag(Flag::PICKLE | Flag::ZLIB)
            .arg(Arg::F64(3.14159))
            .kwarg("b", Arg::Bytes(Vec::from(b"hello!")));

        let zmq = r.to_zmq_message();
        let prefix = b"\x04\x01x\x9ck`\xd6\xf0";
        let frame = zmq.get(1).unwrap();
        assert_eq!(frame[..8], Bytes::copy_from_slice(prefix));

        let request = Request::from_zmq_message(&zmq).unwrap();
        assert_eq!(request.id, 98);
        assert_eq!(request.fcn, "any");

        let arg: f32 = request.get("missing", 0).unwrap();
        assert_eq!(arg, 3.14159);

        let b: ByteBuf = request.get("b", 1).unwrap();
        assert_eq!(b, Bytes::copy_from_slice(b"hello!"));
    }

    #[test]
    fn request_json_with_bytes() {
        let r = Request::new("Whatever")
            .id(101)
            .function("run")
            .arg(Arg::Bytes(Vec::from(b"hello,")))
            .kwarg("b", Arg::Bytes(Vec::from(b" world!")));

        let msg = r.to_zmq_message();
        let request = Request::from_zmq_message(&msg).unwrap();
        assert_eq!(request.id, 101);
        assert_eq!(request.fcn, "run");

        let first: ByteBuf = request.get("missing", 0).unwrap();
        assert_eq!(first, b"hello,");

        let b: ByteBuf = request.get("b", 1).unwrap();
        assert_eq!(b, b" world!");
    }

    #[test]
    fn reply_result_vec() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(
            b"\0\x02\0\0\0\0\0\0\0\0\x01[2.0,4.0,6.0,8.0,10.0]",
        ));

        let reply = Reply::from_zmq_message(&message);
        assert!(reply.success());
        assert_eq!(
            reply.result::<Vec<f64>>().unwrap(),
            vec![2.0, 4.0, 6.0, 8.0, 10.0]
        );
    }

    #[test]
    fn reply_json_request_was_bad() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(
            b"\x00\x02\x03\x00\x00\x00\x00\x00\x00\x00\x00\"value out of range\"",
        ));

        let reply = Reply::from_zmq_message(&message);
        assert!(!reply.success());
        assert_eq!(reply.id(), 3);
        assert_eq!(reply.flag & Flag::SERIALIZATION, Flag::JSON);

        let result: Result<Vec<f64>, BadRequest> = reply.result();
        let bad = result.unwrap_err();
        assert_eq!(bad.to_string(), "value out of range");
    }

    #[test]
    fn reply_pickle_request_was_bad() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(b"\x00\x01\x04\x00\x00\x00\x00\x00\x00\x00\x00\x80\x05\x95\x16\x00\x00\x00\x00\x00\x00\x00\x8c\x12value out of range\x94."));

        let reply = Reply::from_zmq_message(&message);
        assert!(!reply.success());
        assert_eq!(reply.id(), 4);
        assert_eq!(reply.flag & Flag::SERIALIZATION, Flag::PICKLE);

        let result: Result<Vec<f64>, BadRequest> = reply.result();
        let bad = result.unwrap_err();
        assert_eq!(bad.to_string(), "value out of range");
    }

    #[test]
    fn reply_pickle_zlib() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(b"\x04\x01\x05\x00\x00\x00\x00\x00\x00\x00\x01x\x9ck`\x9d*\xc8\x00\x01\xce\xbc\x1e\xa999\xf9:\n\xe5\xf9E9)\x8aS\xf4\x00Oj\x06\xc7"));

        let reply = Reply::from_zmq_message(&message);
        assert!(reply.success());
        assert_eq!(reply.id(), 5);
        assert_eq!(reply.flag & Flag::SERIALIZATION, Flag::PICKLE);
        assert_eq!(reply.result::<ByteBuf>().unwrap(), b"Hello, world!");
    }

    #[test]
    fn reply_pickle_zlib_bad_opcode() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(
            b"\x04\x01\0\0\0\0\0\0\0\0\x01x\x9cSL\xc9)\xca/W\xd0\xc9\xcf\xc9I\xf5\0\0\x1f:\x04\x8a",
        ));

        let reply = Reply::from_zmq_message(&message);
        assert!(reply.success());
        assert_eq!(reply.flag & Flag::SERIALIZATION, Flag::PICKLE);
        assert_eq!(
            reply.result::<ByteBuf>().unwrap_err().to_string(),
            "eval error at offset 1: unsupported opcode '!'"
        );
    }

    #[test]
    fn reply_json_malformed() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(
            b"\x00\x02\x05\x00\x00\x00\x00\x00\x00\x00\x01[1,2",
        ));

        let reply = Reply::from_zmq_message(&message);
        assert!(reply.success());
        assert_eq!(reply.flag & Flag::SERIALIZATION, Flag::JSON);
        assert_eq!(
            reply.result::<String>().unwrap_err().to_string(),
            "EOF while parsing a list at line 1 column 4"
        );
    }

    #[test]
    fn value_json() {
        let value = Value::json("hi");
        assert_eq!(value.result::<String>().unwrap(), "hi");
    }

    #[test]
    fn value_json_with_compression() {
        let value = Value::json_with_compression("hi", Flag::ZLIB);
        assert_eq!(value.vec(), b"x\x9cS\xca\xc8T\x02\x00\x02\xb8\x01\x16");
    }

    #[test]
    fn value_pickle() {
        let value = Value::pickle(&"hi".to_string());
        assert_eq!(value.result::<String>().unwrap(), "hi");
    }

    #[test]
    fn value_pickle_with_compression() {
        let value = Value::pickle_with_compression(&"hi".to_string(), Flag::NONE);
        assert_eq!(value.result::<String>().unwrap(), "hi");
    }

    #[test]
    fn value_bytes() {
        let value = Value::bytes(b"hi");
        assert_eq!(value.vec(), b"hi");
    }

    #[test]
    fn value_bytes_with_compression() {
        let value = Value::bytes_with_compression(b"hi", Flag::ZLIB);
        assert_eq!(value.vec(), b"x\x9c\xcb\xc8\x04\x00\x01;\x00\xd2");
    }

    #[test]
    fn value_new() {
        let mut message = ZmqMessage::from("Server[a48869a30d26c4f3]");
        message.push_back(Bytes::copy_from_slice(
            b"\0\x02\0\0\0\0\0\0\0\0\x01[2.0,4.0,6.0,8.0,10.0]",
        ));

        let value = Value {
            reply: Reply::from_zmq_message(&message),
        };
        assert_eq!(value.service(), "Server[a48869a30d26c4f3]");
        assert_eq!(value.result::<Vec<f64>>(), vec![2.0, 4.0, 6.0, 8.0, 10.0]);
        assert_eq!(
            value.vec(),
            Bytes::copy_from_slice(b"[2.0,4.0,6.0,8.0,10.0]")
        );
    }
}
