#!/bin/python3

import logging
import os

import ismrmrd
import numpy as np
import nibabel as nib

def mrd2nifti(
    data:        np.ndarray,
    head:        list[ismrmrd.ImageHeader],
    output_path: str,
) -> nib.Nifti1Image:
    """
    Convert an MRD image series to a NIfTI file for debug visualisation.

    Reconstructs the 3D or 4D volume from the stacked MRD slices and
    computes the NIfTI affine from the image geometry stored in the first
    header (position, orientation, voxel size). The affine follows the
    RAS convention used by NIfTI, converted from the LPS convention used
    by MRD/DICOM.

    The output volume has shape (x, y, z) for single-channel data or
    (x, y, z, img) for multi-frame data.

    Parameters
    ----------
    data : np.ndarray
        Stacked MRD pixel data, shape [img, cha, z, y, x].
        Only the first channel (cha=0) is used, multi-channel data
        is not supported by standard NIfTI.
    head : list of ismrmrd.ImageHeader
        Image headers. Only the first header is used to compute the
        affine (position, orientation, voxel size). All slices in the
        series are assumed to share the same geometry.
    output_path : str
        Destination path for the .nii or .nii.gz file.
        The parent directory is created if it does not exist.

    Returns
    -------
    nib.Nifti1Image
        The NIfTI image object, also saved to output_path.

    Raises
    ------
    ValueError
        If data has fewer than 3 dimensions or head is empty.

    Notes
    -----
    The affine is computed from the first header using the MRD geometry
    fields (position, read_dir, phase_dir, slice_dir, field_of_view,
    matrix_size). The LPS → RAS conversion negates the x and y components
    of position and direction vectors.

    Examples
    --------
    >>> data, head, meta = stack_images(get_magnitude_images(img_array))
    >>> mrd_series_to_nifti(data, head, "/tmp/share/debug/magnitude.nii.gz")
    """
    if not head:
        raise ValueError("head list is empty, cannot compute NIfTI affine.")
    if data.ndim < 3:
        raise ValueError("data must have at least 3 dimensions [img, cha, z, y, x].")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # --- Voxel size from field of view and matrix size -------------------
    fov        = np.array(head[0].field_of_view[:])    # [x, y, z] in mm
    matrix     = np.array(head[0].matrix_size[:])      # [x, y, z]
    voxel_size = fov / matrix                          # mm per voxel

    affine = compute_nifti_affine(head[0], voxel_size)

    # --- Reformat data to NIfTI convention [x, y, z] or [x, y, z, img] ---
    # MRD : [img, cha, z, y, x] (take first channel only)
    # NIfTI: [x, y, z] or [x, y, z, img]
    volume = data[:, 0, 0, :, :]     # [img, y, x] (single channel, single z)
    volume = volume.transpose(2, 1, 0)  # [x, y, img]

    if volume.shape[-1] == 1:
        volume = volume[..., 0]       # [x, y] → squeeze single frame
    # else: [x, y, img] → 4D NIfTI

    nifti_image = nib.Nifti1Image(volume.astype(np.float32), affine)

    # --- NIfTI header ----------------------------------------------------
    nifti_image.header.set_xyzt_units(xyz='mm', t='sec')
    nifti_image.header['pixdim'][1:4] = voxel_size

    nib.save(nifti_image, output_path)
    logging.info("NIfTI saved: %s  shape=%s  voxel_size=%s mm",
                 output_path, volume.shape, voxel_size)

    return nifti_image


def compute_nifti_affine(image_header, voxel_size):

    # --- Affine : LPS (MRD) → RAS (NIfTI) -------------------------------
    # MRD stores directions in LPS — negate x and y to convert to RAS
    def lps_to_ras(v):
        return np.array([-v[0], -v[1], v[2]])

    read_dir  = lps_to_ras(image_header.read_dir)
    phase_dir = lps_to_ras(image_header.phase_dir)
    slice_dir = lps_to_ras(image_header.slice_dir)
    position  = lps_to_ras(image_header.position)

    # Construct rotation-scaling matrix
    rotation_scaling_matrix = np.column_stack([
        voxel_size[0] * np.array(read_dir),
        voxel_size[1] * np.array(phase_dir),
        voxel_size[2] * np.array(slice_dir)
    ])

    affine         = np.eye(4)
    affine[:3, :3]  = rotation_scaling_matrix
    affine[:3, 3]  = position
    
    return affine
