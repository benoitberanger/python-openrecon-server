# python-openrecon-server

A Python template to help building MRD image processing pipelines for Siemens OpenRecon.
> [kspaceKelvin/python-ismrmrd-server](https://github.com/kspaceKelvin/python-ismrmrd-server) was used as a reference in the developpment of this project.


## Table of contents

- [Overview](#overview)
- [Getting started](#getting-started)
- [Writing a processing module](#writing-a-processing-module)
- [OpenRecon JSON Configuration](#openrecon-json-configuration)
- [Debug mode](#debug-mode)
- [Building and packaging](#building-and-packaging)
- [Converter](#converter)
- [Project structure](#project-structure)
- [Examples](#examples)


## Overview

The server receives MRD images, organises them into a structured 7D array,
calls your `process_image()` function, and sends the results back slice by
slice.

---

## Getting started

### Requirements

- [Docker](https://www.docker.com/products/docker-desktop) (version < 25)

For local test:
- Python 3.12
- Dependencies:

```bash
pip install jsonschema=4.26.0 ismrmrd=1.14.2 psutil=7.2.2 pydicom=3.0.2
```




## Testing locally

### Workflow

1. Run the main.py in a terminal :

```bash
python main.py --config your_module --dirname app
```
Available arguments:

| Argument | Default | Description |
|---|---|---|
| `--config` | `invertcontrast` | Processing module name (without `.py`) |
| `--dirname` | `app` | Directory containing the processing module |
| `-H` | `0.0.0.0` | Host address |
| `-p` | `9002` | TCP port |
| `-v` | — | Verbose logging |
| `--debug` | — | Enable debug mode (passthrough, no processing) |
| `-l` | — | Log file path |

2. Convert DICOMs or enhanced DICOMs images to MRD images .h5 file:

```bash
# DICOMs converter
python converter/dicom2mrd.py <folder of DICOMs> -o <outfile>

# Enhanced DICOMs converter
python converter/enhanceddicom2mrd.py <folder of DICOMs> -o <outfile>
```

3. Run the client.py to send the images :
```bash
python client.py -o <output.h5> <input.h5>
```

4. The output `.h5` file can be converted back to DICOM for visualisation :
```bash
python converter/mrd2dicom.py -o <outdir> <mrdfile>.h5
```

### Testing with Docker

Follow the same workflow than before but replace the first step by this one :

1. Run the `build.py`script with the name of your app directory:
```bash
# --nopackage option to skip the packaging part
python build.py --nopackage -d app
```

2. Run the Docker Image:
```bash
docker run -p 9002:9002 -t <image_name>:<image_version>
```


## Writing a processing module

Create a Python file in the `app/` directory. It must expose a single
function with this signature:

```python
def process_image(
    img_array:  MRDImageArray,
    configJSON: dict | None,
    metadata,
) -> tuple[np.ndarray, list, list] | list[tuple]:
    ...
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `img_array` | `MRDImageArray` | 7D structured array of MRD images |
| `configJSON` | `dict` or `None` | JSON configuration sent by the client |
| `metadata` | `ismrmrd.xsd.ismrmrdHeader` | MRD acquisition header |

### The image array

Images are organised in a 7D numpy array:

**`img_array[slice, contrast, average, phase, repetition, set, image_type]`**


Each cell contains an `ismrmrd.Image` object or `None`.
`image_type` uses MRD constants directly as indices:

| Constant | Value |
|---|---|
| `ismrmrd.IMTYPE_MAGNITUDE` | 1 |
| `ismrmrd.IMTYPE_PHASE` | 2 |
| `ismrmrd.IMTYPE_REAL` | 3 |
| `ismrmrd.IMTYPE_IMAG` | 4 |
| `ismrmrd.IMTYPE_COMPLEX` | 5 |
| `ismrmrd.IMTYPE_RGB` | 6 |

### Accessing images

To get the specific images that you need, you can use the following functions:
`get_subarray`, `get_magnitude_images`, `get_phase_images`, `get_contrast` from `utils.image_array`.

examples :
```python
from utils.image_array import get_magnitude_images, get_phase_images, get_subarray

# All magnitude images
mag_array = get_magnitude_images(img_array)

# Specific contrast
co0 = get_contrast(img_array, contrast=0)

# First 100 slices, magnitude only
subarray = get_subarray(img_array, img_slice=slice(0,100), img_image_type=ismrmrd.IMTYPE_MAGNITUDE)
```

### Stacking images

[MRD images](https://ismrmrd.readthedocs.io/en/latest/mrd_image_data.html)
are 2D slices. Use `stack_images()` to extract pixel data, headers, and
metadata in one call. Since MRD stores data as `[cha, z, y, x]`, the
stacked array has shape **`[img, cha, z, y, x]`**.

```python
from utils.image_array import stack_images

# All magnitude images
data, head, meta = stack_images(img_array, dtype=float32)
```

### Updating metadata

You can call `update_meta` from `utils.image_array` to update the label and process history of the images.

```python
from utils.image_array import update_meta

meta = update_meta(
    meta,
    process_history=["PYTHON", "MY_PROCESS"],  # shown in ImageProcessingHistory
    sequence_description="myprocess",           # shown as series label in the client
)
```

### Return value

`process_image` must return the processed volume with its headers and
updated metadata:

```python
return data, head, meta
# data shape: [img, cha, z, y, x], dtype int16
```

The pipeline calls `send_volume_as_slices()` on the result, which will re-slice back the processed volume into 2D MRD images and send them to the client one by one.

## OpenRecon JSON Configuration

Processing parameters can be passed at runtime via a JSON configuration
sent by the client. Use `check_OR_arguments()` to read them safely with
a default fallback:

```python
from utils.config import check_OR_arguments

# Read a string parameter, default to 'SimpleSum'
mode = check_OR_arguments(configJSON, "EchoSumConfig", str, "SimpleSum")

# Read a boolean parameter, default to False
save = check_OR_arguments(configJSON, "SaveOriginal", bool, False)
```

### Reserved keys

The following keys are handled by the pipeline and do not need to be
read manually in `process_image`. If they are not provided in the JSON configuration, they default value will be used :

| Key | Type | Default | Description |
|---|---|---|---|
| `"Debug"` | `bool` | `False` | Enable debug mode at runtime |
| `"SaveOriginal"` | `bool` | `True` | Send original images before processed ones |


## Debug mode

When debug mode is active, images are sent back to the client unmodified
and `process_image` is never called. Infos from each image's metadata is
logged (image type, orientation, all FIRST/LAST flags,...).

- Enable at startup:
```bash
python main.py --debug --config your_module --dirname app
```
_**Warning** : `--debug` at startupit overrun any JSON configuration. The processing module will never be called._

- Enable at runtime in the UI / via JSON:
```json
{ "Debug": true }
```

## Converter

The `converter/` directory provides tools to convert between DICOM and
MRD (`.h5`) format, which is required for local testing.

### DICOM to MRD

Convert a DICOM series to an MRD `.h5` file for use as input to `client.py`:

```bash
python converter/dicom_to_mrd.py --input <input_folder> --output <output.h5>
```

### MRD to DICOM

Convert a processed MRD `.h5` file back to DICOM for inspection in a
DICOM viewer (e.g. OsiriX, 3D Slicer, RadiAnt):

```bash
python converter/mrd_to_dicom.py --input <input.h5> --output <path/to/output/folder>
```

## Building and packaging

The `build.py` script automates the full build pipeline:

```bash
python build.py --dirname app
```
By default, it build the `app` directory. 
The name off the process is automaticaly get from the name of the `.py` file in the directory.

This script will build the Docker image of the OpenRecon application and all the necessary files to upload it on the magnet.
Meaning, the `.zip`file containing the image as a `.tar` and a minimalistic `.pdf`.

Steps performed:

1. Checks system dependencies (`docker`, `zip`, `git`) and Docker version.
2. Verifies required files in the application directory.
3. Builds the base `python-openrecon-server` Docker image if not present.
4. Validates the JSON UI file against its schema.
5. Generates the final Dockerfile with the OpenRecon metadata label.
6. Builds the application Docker image.
7. Exports the image as `.tar`, generates a PDF, and bundles both into a `.zip`.

### Build options

| Argument | Description |
|---|---|
| `--dirname` | Application directory name. Default: `app` |
| `--debug` | Embed `--debug` flag in the Dockerfile CMD |
| `--nopackage` | Skip `.zip` packaging (build image only) |

### Required files in the application directory

| File | Description |
|---|---|
| `<name>_json_ui.json` | OpenRecon UI parameter |
| `OpenReconSchema_*.json` | JSON schema for JSON validation |
| `<name>.py` | Processing module |
| `application.Dockerfile` | Application-specific Dockerfile |