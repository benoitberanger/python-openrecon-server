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
    Andrew Hoopes, Jocelyn S. Mora, Adrian V. Dalca, Bruce Fischl*, Malte Hoffmann* (*equal contribution) NeuroImage, 260, p 119474, 2022


Objectives
**********
Since `python-openrecon-server`_ is in *Python*, we will use the *Python* version of :abbr:`ANTs (Advanced Normalization Tools)`: `AntsPy <antspy_>`_.
This packages wraps the C++ code to make it easily scriptable in *Python*, while keep the fast multi-threaded computation.

The user will have the possibility to apply :abbr:`N4 (N4BiasFieldCorrection)` and/or :abbr:`DN (DenoiseImage)` on the image,
within a *BrainMask* computed via *SynthStrip* or not.


.. _python-openrecon-server: https://github.com/benoitberanger/python-openrecon-server
.. _demo: https://github.com/benoitberanger/python-openrecon-server/tree/main/apps/demo
.. _echo_sum: https://github.com/benoitberanger/python-openrecon-server/tree/main/apps/echo_sum
.. _python-ismrmd-server: https://github.com/kspaceKelvin/python-ismrmrd-server
.. _openrecon-ants: https://github.com/benoitberanger/openrecon-ants
.. _ants: https://github.com/antsx/ants
.. _antspy: https://github.com/antsx/antspy
.. _syntstrip: https://surfer.nmr.mgh.harvard.edu/docs/synthstrip
