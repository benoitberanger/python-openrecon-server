import sys

import ismrmrd
import numpy as np
import pytest

from server.pipeline import Pipeline
from utils.img_array import build_image_array, flatten


@pytest.fixture
def dummy_app():
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


# ---------------------------------------------------------------------------
# test of pipeline.load_module()
# ---------------------------------------------------------------------------
class TestLoadModule:
    def test_load_module_import_error_leaves_module_none(self, fake_connection):
        pipeline = Pipeline(fake_connection, app_config="does_not_exist", app_directory="app")
        assert pipeline.module is None

    def test_load_module_success_sets_module(self, fake_connection, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        assert pipeline.module is sys.modules["app.dummy_app"]
        assert hasattr(pipeline.module, "process_image")

    def test_wrong_app_directory_fails_to_import(self, fake_connection, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="wrong")
        assert pipeline.module is None


# ---------------------------------------------------------------------------
# test of pipeline.images_selector()
# ---------------------------------------------------------------------------
class TestImageSelector:

    def test_images_selector_filter_magnitude_only(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        mag = make_image(image_type=ismrmrd.IMTYPE_MAGNITUDE)
        phase = make_image(image_type=ismrmrd.IMTYPE_PHASE)
        arr = build_image_array([mag, phase])

        result = pipeline.images_selector(arr, configJSON={"parameters":{"ImageType": "Magnitude"}})

        assert flatten(result) == [mag]

    def test_images_selector_first_echo(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [make_image(contrast=c) for c in range(3)]
        arr = build_image_array(images)

        result = pipeline.images_selector(arr, configJSON={"parameters":{"SelectEcho": "FirstEcho"}})

        assert flatten(result) == [images[0]]

    def test_images_selector_last_echo(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [make_image(contrast=c) for c in range(3)]
        arr = build_image_array(images)

        result = pipeline.images_selector(arr, configJSON={"parameters":{"SelectEcho": "LastEcho"}})

        assert flatten(result) == [images[-1]]
    
    def test_images_selector_defaults_to_all_when_no_config(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [make_image(contrast=c) for c in range(3)]
        arr = build_image_array(images)

        result = pipeline.images_selector(arr, configJSON=None)

        images_list = flatten(result)
        assert len(images_list) == len(images)
        for i in range(len(images)):
            assert images_list[i] == images[i]


# ---------------------------------------------------------------------------
# test of pipeline.run()
# ---------------------------------------------------------------------------
class TestRun:
    def test_run_with_empty_images_list_send_nothing(self, fake_connection, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        result = pipeline.run([], configJSON=None, metadata=None)

        assert result == []
        assert fake_connection.sent_images == []
    
    def test_save_original_first_by_default(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [make_image(slice=0, image_series_index=0)]

        pipeline.run(images, configJSON=None, metadata=None)

        assert fake_connection.sent_images[0] is images[0]

    def test_run_does_not_send_original_when_save_original_false(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [make_image(slice=0, image_series_index=0)]

        pipeline.run(images, configJSON={"parameters":{"SaveOriginal": False}}, metadata=None)

        assert images[0] not in fake_connection.sent_images

    


