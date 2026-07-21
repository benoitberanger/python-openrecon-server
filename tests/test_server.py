import ismrmrd
import numpy as np
import pytest

from server import constants
from server.server import Server

@pytest.fixture
def server_obj():
    # __init__ not called so no real socket
    s = Server.__new__(Server)
    s.debug = False
    s.app_config = "does_not_exist"
    s.app_config = "app"
    return s


# ---------------------------------------------------------------------------
# handle_metadata()
# ---------------------------------------------------------------------------
class FakeMinimalConnection:
    def __init__(self, value, open=True):
        self.value = value
        self.open = open

    def __next__(self):
        return self.value


class TestHandleMetadata:

    def test_valid_xml_is_parsed(self, server_obj):
        xml = (
            '<ismrmrdHeader xmlns="http://www.ismrm.org/ISMRMRD">'
            '<acquisitionSystemInformation><systemFieldStrength_T>7</systemFieldStrength_T>'
            '<systemVendor>Siemens</systemVendor><systemModel>MAGNETOM Terra.X</systemModel></acquisitionSystemInformation>'
            '</ismrmrdHeader>'
        )

        connection = FakeMinimalConnection(xml)

        result = server_obj.handle_metadata(connection)
        assert isinstance(result, ismrmrd.xsd.ismrmrdHeader)

    def test_invalid_xml_falls_back_to_raw_string(self, server_obj):
        connection = FakeMinimalConnection("this is not valid xml")
        result = server_obj.handle_metadata(connection)
        assert result == "this is not valid xml"
    
    def test_none_with_closed_connection_returns_none(self, server_obj):
        connection = FakeMinimalConnection(None, open=False)
        result = server_obj.handle_metadata(connection)
        assert result is None


# ---------------------------------------------------------------------------
# handleJSON()
# ---------------------------------------------------------------------------
class FakePeekableConnection:
    def __init__(self, peek_id, next_value=None):
        self.peek_id = peek_id
        self.next_value = next_value
    
    def peek_mrd_message_identifier(self):
        return self.peek_id
    
    def __next__(self):
        return self.next_value


class TestHandleJSON:
    """tests for handle JSON"""

    def test_parses_json_when_text_message_present(self, server_obj):
        connection = FakePeekableConnection(constants.MRD_MESSAGE_TEXT, next_value='{"TestParameters":"test"}')
        result = server_obj.handleJSON(connection)
        assert result == {"TestParameters":"test"}



# ---------------------------------------------------------------------------
# handle_image_stream()
# ---------------------------------------------------------------------------
class TestHandleImageStream:
    """tests for handle Image Stream"""

