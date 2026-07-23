import ismrmrd
import pytest

import server.constants as constants
from server.connection import Connection
from conftest import FakeSocket, RaisingSocket

# ---------------------------------------------------------------------------
# read() / peek()
# ---------------------------------------------------------------------------
class TestReadAndPeek:
    def test_read_consumes_bytes(self):
        connection = Connection(FakeSocket(incoming=b"hello world"), savedata=False)
        assert connection.read(5) == b"hello"
        assert connection.read(6) == b" world"

    def test_peek_does_not_consume_bytes(self):
        connection = Connection(FakeSocket(incoming=b"hello world"), savedata=False)
        assert connection.peek(5) == b"hello"
        assert connection.read(6) == b"hello "


# ---------------------------------------------------------------------------
# read_mrd_message_length() / read_mrd_message_identifier() /
# peek_mrd_message_identifier() / unknow_message_identifier()
# ---------------------------------------------------------------------------
class TestMRDMessageIdentifier :
    def test_read_mrd_message_length(self):
        incoming = constants.MrdMessageLength.pack(1234)
        connection = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert connection.read_mrd_message_length() == 1234

    def test_unknow_message_identifier(self):
        with pytest.raises(StopIteration):
            Connection.unknown_message_identifier(9999)

    def test_read_mrd_message_identifier_normal_case(self):
        incoming = constants.MrdMessageIdentifier.pack(constants.MRD_MESSAGE_CLOSE)
        connection = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert connection.read_mrd_message_identifier() == constants.MRD_MESSAGE_CLOSE

    def test_read_mrd_message_identifier_empty_socket_close_connection(self):
        connection = Connection(FakeSocket(incoming=b""), savedata=False)
        result = connection.read_mrd_message_identifier()
        assert result is None
        assert connection.open is False

    def test_read_mrd_message_identifier_connection_reset_close_connection(self):
        connection = Connection(RaisingSocket(), savedata=False)
        result = connection.read_mrd_message_identifier()
        assert result is None
        assert connection.open is False

    def test_peek_mrd_message_identifier_does_not_consume(self):
        incoming = constants.MrdMessageIdentifier.pack(constants.MRD_MESSAGE_TEXT)
        connection = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert connection.peek_mrd_message_identifier() == constants.MRD_MESSAGE_TEXT
        assert connection.read_mrd_message_identifier() == constants.MRD_MESSAGE_TEXT

# ---------------------------------------------------------------------------
# read_config_file() / read_config_text() / read_metadata() / read_text()
# ---------------------------------------------------------------------------
class TestReadMRDMessage:
    def test_read_config_file_strips_null_padding(self):
        incoming = constants.MrdMessageConfigurationFile.pack(b"config_test.xml")
        conn = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert conn.read_config_file() == "config_test.xml"

    def test_read_config_text(self):
        content = "some config text\0"
        incoming = constants.MrdMessageLength.pack(len(content.encode())) + content.encode()
        conn = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert conn.read_config_text() == "some config text"

    def test_read_metadata(self):
        content = "<xml>fake header</xml>\0"
        incoming = constants.MrdMessageLength.pack(len(content.encode())) + content.encode()
        conn = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert conn.read_metadata() == "<xml>fake header</xml>"

    def test_read_text(self):
        content = "test\0"
        incoming = constants.MrdMessageLength.pack(len(content.encode())) + content.encode()
        conn = Connection(FakeSocket(incoming=incoming), savedata=False)
        assert conn.read_text() == "test"
    

