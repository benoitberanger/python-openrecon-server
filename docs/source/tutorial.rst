========
Tutorial
========


Bundled examples
################

`python-openrecon-server`_ packakge bundles currently two example applications:

* `demo`_
* `echo_sum`_ 


`demo`_
*******
Equivalent of `invertcontrast` from `python-ismrmd-server`_, with `image_type` selection (magnitude, phase, real, imaginary) and `series` manipulation.


`echo_sum`_
***********
The application will perform `echo` averaging on each series. This demonstrates the manipulation of the `image_type`, selection of `echo` and fetching OpenRecon UI parameter.


Creation of a new app: `ANTs <openrecon-ants_>`_
################################################
In this section, we will go though the modifications of the `demo`_ application to produce `openrecon-ants`_.


Context
*******

The objective of the :abbr:`OR (OpenRecon)` app is to perform classic neuroimaging pre-processing steps online on the MRI machine itself, while these steps are usually done offline.

:abbr:`ANTs (Advanced Normalization Tools)` (https://github.com/antsx/ants) is a library with :abbr:`CLI (Command Line Inputs)` programs performing processing steps on Nifti files.
The two tools we are interested to port into :abbr:`OR (OpenRecon)` are:

* `N4BiasFieldCorrection` (:abbr:`N4 (N4BiasFieldCorrection)`)
    N4 is a variant of the popular N3 (nonparameteric nonuniform normalization) retrospective bias correction algorithm.
    Based on the assumption that the corruption of the low frequency bias field can be modeled as a convolution of the intensity histogram by a Gaussian,
    the basic algorithmic protocol is to iterate between deconvolving the intensity histogram by a Gaussian,
    remapping the intensities, and then spatially smoothing this result by a B-spline modeling of the bias field itself.
    The modifications from and improvements obtained over the original N3 algorithm are described in the following paper:
    N. Tustison et al., N4ITK: Improved N3 Bias Correction, IEEE Transactions on Medical Imaging, 29(6):1310-1320, June 2010.
* `DenoiseImage` (:abbr:`DN (DenoiseImage)`)
    Denoise an image using a spatially adaptive filter originally described in J. V. Manjon, P. Coupe, Luis Marti-Bonmati, D. L. Collins, and M. Robles.
    Adaptive Non-Local Means Denoising of MR Images With Spatially Varying Noise Levels, Journal of Magnetic Resonance Imaging, 31:192-203, June 2010. 

To reduce computation time of both processing steps and to improve :abbr:`N4 (N4BiasFieldCorrection)` bias field estimation, we can use a *BrainMask*.
A *BrainMask* from a 3D whole head MRI image typicly represents around 20-25% of the voxels, resulting in a a 4-5 fold computation time reduction.

`SynthStrip <syntstrip_>`_
    SynthStrip is a skull-stripping tool that extracts brain voxels from a landscape of image types, ranging across imaging modalities, resolutions, and subject populations.
    It leverages a deep learning strategy to synthesize arbitrary training images from segmentation maps, yielding a robust model agnostic to acquisition specifics.
    Andrew Hoopes, Jocelyn S. Mora, Adrian V. Dalca, Bruce Fischl\*, Malte Hoffmann\* (\*equal contribution) NeuroImage, 260, p 119474, 2022


Objectives
**********
Since `python-openrecon-server`_ is in *Python*, we will use the *Python* version of :abbr:`ANTs (Advanced Normalization Tools)`: `AntsPy <antspy_>`_.
This packages wraps the C++ code to make it easily scriptable in *Python*, while keep the fast multi-threaded computation.

The user will have the possibility to apply :abbr:`N4 (N4BiasFieldCorrection)` and/or :abbr:`DN (DenoiseImage)` on the image,
within a *BrainMask* computed via *SynthStrip* or not.


Creation of application files
*****************************
The app directory will be called ``ants``.
It will contain:

* ``ants_synthstrip.py``: our main processing script, containing ``process_image`` function.
* ``__init__.py``: the app directory must be a *Python* module.
* ``application.Dockerfile`` : *Dockerfile* containing the instructions specific to your application.
* ``ants_synthstrip_json_ui.json``: This JSON file is described on the `magnetom.net`_ forum. It contains both application metadata and the UI displayed on the magnet
* ``OpenReconSchema_1.1.0.json``: Provided by Siemens, and found on `magnetom.net`_.

::

    apps/ants/
    ├── ants_synthstrip_json_ui.json
    ├── ants_synthstrip.py
    ├── application.Dockerfile
    ├── __init__.py
    └── OpenReconSchema_1.1.0.json


Required content
****************


``ants_synthstrip.py``
----------------------

The mandatory content of the application file is the ``process_image`` function. We fill the file ``ants_synthstrip.py`` with scaffold code:

.. code-block:: python

    import ismrmrd
    import numpy as np

    from utils.OutputSeries import OutputSeries, ProcessImageResult

    def process_image(
            img_array: np.ndarray[ismrmrd.Image],
            configJSON: dict | None,
            metadata: ismrmrd.xsd.ismrmrdHeader | str
            )-> ProcessImageResult:

        series = OutputSeries()

        return series.get()

This application do nothing.


``application.Dockerfile``
--------------------------

Also, an ``application.Dockerfile`` is required to build our :abbr:`OR (OpenRecon)` app.

.. code-block:: Dockerfile

    # import python-openrecon-server as starting point
    FROM python-openrecon-server AS base

    COPY . .

    # Label with version of the app will be set automatically by the build.py script

    # Command line will be added automatically by the build.py script

    # Docker image metadata label `com.siemens-healthineers.magneticresonance.OpenRecon.metadata:1.1.0`
    # will also be set automatically by the build.py script with the base64-encoded JSON text load from
    # the json file provided in the app directory

The ``build.py`` script will build the `python-openrecon-server` docker image, that serves as starting point here.


``ants_synthstrip_json_ui.json``
--------------------------------

This file is a bit cryptic at first sight. 
Briefly, it defines: 

* the general :abbr:`OR (OpenRecon)` app information,
* the minimal hardware required for reconstruction,
* then the UI parameters set on the magnet, that will be passed to the Docker at runtime.

For a complete description, please refer to the official documentation in `magnetom.net`_.

In the example below, we will start from the `demo`_, and modify the `general` part.

.. code-block:: json

    {
    "general": {
        "name": { "en": "ANTs" },
        "version": "4.0.0",
        "vendor": "ICM",
        "information": { "en": "Apply ANTs transformations, such as N4BiasFieldCorrection DenoiseImage. Can be in a BrainMask" },
        "id": "ANTs",
        "regulatory_information":{
            "device_trade_name":"ANTs",
            "production_identifier":"4.0.0",
            "manufacturer_address":"https://github.com/benoitberanger/openrecon-ants",
            "made_in":"CENIR, ICM, Paris, France",
            "manufacture_date":"2026-09-08",
            "material_number":"ANTs_4.0.0",
            "gtin":"",
            "udi":"",
            "safety_advices":"",
            "special_operating_instructions":"",
            "additional_relevant_information":""
    }
    },
    "reconstruction": {
        "transfer_protocol": {
        "protocol": "ISMRMRD",
        "version": "1.4.1"
        },
        "port": 9002,
        "emitter": "image",
        "injector": "image",
        "can_process_adjustment_data": false,
        "can_use_gpu": false,
        "min_count_required_gpus": 0,
        "min_required_gpu_memory": 2048,
        "min_required_memory": 32768,
        "min_count_required_cpu_cores": 1,
        "content_qualification_type": "RESEARCH"
    },
    "parameters": [
        {
        "id": "SaveOriginal",
        "label": { "en": "Save original images" },
        "type": "boolean",
        "information": { "en": "This option will send both original (no suffix) and processed images (with suffix)" },
        "default": true
        },
        {
        "id": "Debug",
        "label": { "en": "Enabled Debug mode" },
        "type": "boolean",
        "information": { "en": "This option will enabled debug mode, which return only the original images while display infos about them in the logs" },
        "default": false
        },
        {
        "id": "ImageType",
        "type": "choice",
        "label": { "en": "Image Type" },
        "values": [
            {
            "id": "All",
            "name": { "en": "All" }
            },
            {
            "id": "Magnitude",
            "name": { "en": "Magnitude only" }
            },
            {
            "id": "Phase",
            "name": { "en": "Phase only" }
            }
        ],
        "default": "All",
        "information": { "en": "Select image type on which apply the process" }
        },
        {
        "id": "SelectEcho",
        "type": "choice",
        "label": { "en": "Select Echo" },
        "values": [
            {
            "id": "All",
            "name": { "en": "All" }
            },
            {
            "id": "FirstEcho",
            "name": { "en": "First Echo" }
            },
            {
            "id": "LastEcho",
            "name": { "en": "Last Echo" }
            }
        ],
        "default": "All",
        "information": { "en": "Select echo on which apply the process" }
        },
        {
        "id": "SelectSerie",
        "type": "choice",
        "label": { "en": "Select Series" },
        "values": [
            {
            "id": "All",
            "name": { "en": "All" }
            },
            {
            "id": "FirstSerie",
            "name": { "en": "First Series" }
            },
            {
            "id": "LastSerie",
            "name": { "en": "Last Series" }
            }
        ],
        "default": "All",
        "information": { "en": "Select series on which apply the process" }
        }
    ]
    }

.. caution::

    Still it is **highly** recomanded to run it offline first in order to check the whole processing pipeline is working as expected.
    To do so, we will modify the *Makefile*.


*Makefile*
**********
The `Makefile`_ is the entry point to test your application during development.
After defining a few variables, it will help starting several operations, such as building the :abbr:`OR (OpenRecon)` app,
start a local Server listening to a Client, or visualizing output data.

.. code-block:: makefile

    # --- Default parameters for server (main.py) ---------------------------------
    CONFIG  ?= ants_synthstrip # name of the python file (.py), which contains `process_image` function
    APP_DIR ?= ants


The *Makefile* contains serval "rules".

.. code-block:: makefile

    ## ----------------------------------------------------------------------
    ## Local execution (server / client)
    ## ----------------------------------------------------------------------

    server:
        @echo "Starting server locally"
        python main.py -v --config ${CONFIG} --dirname $(APP_DIR) $(if $(LOGFILE),-l $(LOGFILE),)

    client:
        @echo "Starting Client"
        rm -f ${OUT_DIR}/*dcm ${OUT_DIR}/*h5
        python client.py -c openrecon.json -o ${OUT_DIR}/OR_${DATASET_NAME}.h5 ${IN_DIR}/${DATASET_NAME}.h5
        python -m converter.mrd2dicom -o ${OUT_DIR}/ ${OUT_DIR}/OR_${DATASET_NAME}.h5

    view:
        mrview ${OUT_DIR} -mode 2 # mrview is a multi-purpose image viewer, from MRTrix3


Testing dataset must be set. Create the corresponding directories and add your testing data.

.. code-block:: makefile

    # --- Parameters for local test -----------------------------------------------
    IN_DIR=data/in
    OUT_DIR=data/out

    DATASET_NAME=gre_1e_mag


In one terminal, start the *Server*.

.. code-block:: bash

    make server 

In another terminal, start a *Client*.

.. code-block:: bash

    make client

Then you can visualize your output data.

.. code-block:: bash

    make view


Build the app
*************

The `build.py <build_>`_ script will build the Docker image of the :abbr:`OR (OpenRecon)` application and all the necessary files to upload it on the magnet.

.. code-block:: bash

    make build


.. _python-openrecon-server: https://github.com/benoitberanger/python-openrecon-server
.. _demo: https://github.com/benoitberanger/python-openrecon-server/tree/main/apps/demo
.. _echo_sum: https://github.com/benoitberanger/python-openrecon-server/tree/main/apps/echo_sum
.. _python-ismrmd-server: https://github.com/kspaceKelvin/python-ismrmrd-server
.. _openrecon-ants: https://github.com/benoitberanger/openrecon-ants
.. _ants: https://github.com/antsx/ants
.. _antspy: https://github.com/antsx/antspy
.. _syntstrip: https://surfer.nmr.mgh.harvard.edu/docs/synthstrip
.. _Makefile: https://github.com/benoitberanger/python-openrecon-server/blob/main/Makefile
.. _build: https://github.com/benoitberanger/python-openrecon-server/blob/main/main.py
.. _magnetom.net: https://www.magnetom.net/