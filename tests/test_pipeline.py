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

    def test_run_sends_one_slice_per_input_image(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [
            make_image(slice=0, image_series_index=0),
            make_image(slice=1, image_series_index=0),
            make_image(slice=2, image_series_index=0)
        ]

        pipeline.run(images, configJSON={"parameters":{"SaveOriginal": False}}, metadata=None)

        assert len(fake_connection.sent_images) == 3
    
    def test_run_increments_image_series_index_for_processed_slice(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [make_image(slice=0, image_series_index=5)]

        pipeline.run(images, configJSON={"parameters":{"SaveOriginal": False}}, metadata=None)

        sent = fake_connection.sent_images[0]
        assert sent.image_series_index == 11

    def test_run_tracks_max_image_series_index_across_multiple_series(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = [
            make_image(slice=0, image_series_index=2),
            make_image(slice=1, image_series_index=7),
        ]

        pipeline.run(images, configJSON={"parameters":{"SaveOriginal": False}}, metadata=None)

        assert pipeline.max_image_series_index == 7
        offset = pipeline.max_image_series_index + 1  # 8
        sent_indexes = sorted(img.image_series_index for img in fake_connection.sent_images)
        assert sent_indexes == sorted([2 + offset, 7 + offset])


# ---------------------------------------------------------------------------
# test of pipeline.send_volume_as_2Dslices()
# ---------------------------------------------------------------------------
class TestSendVolumeAs2DSlices:

    def test_send_volume_as_2D_slices_sets_keep_image_geometry(self, fake_connection, make_image, dummy_app):
        pipeline = Pipeline(fake_connection, app_config=dummy_app, app_directory="app")
        images = make_image(slice=0, image_series_index=0, shape=(2, 1, 4, 4))

        data = images.data.astype(np.float32)
        head = [images.getHead()] * 2
        meta = [ismrmrd.Meta.deserialize(images.attribute_string)] * 2

        pipeline.send_volume_as_2Dslices(data, head, meta)

        assert len(fake_connection.sent_images) == 2
        for sent in fake_connection.sent_images:
            sent_meta = ismrmrd.Meta.deserialize(sent.attribute_string)
            assert sent_meta["Keep_image_geometry"] == "1"
