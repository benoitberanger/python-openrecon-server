import ismrmrd
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# FAKE IMAGE
# Minimal class to reproduce a complex ismrd.Image object
# ---------------------------------------------------------------------------
class FakeImage:
    def __init__(self, slice=0, contrast=0, average=0, phase=0,
                 repetition=0, set=0, image_type=1, image_series_index=0,
                 data=None):
        self.slice = slice
        self.contrast = contrast
        self.average = average
        self.phase = phase
        self.repetition = repetition
        self.set = set
        self.image_type = image_type
        self.image_series_index = image_series_index
        self.data = data if data is not None else np.ones((1, 2, 3, 3), dtype=np.float32)
        self.attribute_string = "<?xml version='1.0' encoding='UTF-8'?><ismrmrdMeta></ismrmrdMeta>"

    def getHead(self):
        return {"slice": self.slice, "contrast": self.contrast}


# ------------------------------------------------------

class FakeConnection:
 
    def __init__(self):
        self.sent_images = []
        self.logs = []
        self.closed = False
 
    def send_image(self, image_or_list):
        if isinstance(image_or_list, list):
            self.sent_images.extend(image_or_list)
        else:
            self.sent_images.append(image_or_list)
 
    def send_logging(self, level, message):
        self.logs.append((level, message))
 
    def send_close(self):
        self.closed = True
 
 
@pytest.fixture
def fake_connection():
    return FakeConnection()
 
 
@pytest.fixture
def make_image():
 
    def _make(
        slice=0,
        contrast=0,
        average=0,
        phase=0,
        repetition=0,
        set=0,
        image_type=ismrmrd.IMTYPE_MAGNITUDE,
        image_series_index=0,
        shape=(1, 1, 4, 4),
        value=1.0,
        dtype=np.float32,
    ):
        data = np.full(shape, value, dtype=dtype)
        img = ismrmrd.Image.from_array(data, transpose=False)
 
        img.slice = slice
        img.contrast = contrast
        img.average = average
        img.phase = phase
        img.repetition = repetition
        img.set = set
        img.image_type = image_type
        img.image_series_index = image_series_index
 
        meta = ismrmrd.Meta()
        img.attribute_string = meta.serialize()
 
        return img
 
    return _make
 
 
@pytest.fixture
def dummy_app(tmp_path, monkeypatch):
    import sys
    import types
 
    module = types.ModuleType("app.dummy_app")
 
    def process_image(img_array, configJSON, metadata):
        from utils.img_array import flatten, stack_images
 
        images = flatten(img_array)
        data, head, meta = stack_images(images, dtype=np.float32)
        return [(data, head, meta)]
 
    module.process_image = process_image
    sys.modules["app.dummy_app"] = module
 
    yield "dummy_app"
 
    del sys.modules["app.dummy_app"]