#!/bin/python3

import argparse
import logging
import os
import re

import h5py
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
    """
    TO-DO
    """

    # --- Affine : LPS (MRD) to RAS (NIfTI) -------------------------------
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


def assemble_volume(images: list, extra_dims: list) :
    if not images: 
        raise ValueError("Empty image list")
    

def detect_extra_dims(images: list) -> list:
    possible_dims = ["contrast", "phase", "repetition", "set", "average"]
    active = []

    for dim in possible_dims:
        values = {int(getattr(img.getHead(), dim, 0)) for img in images}
        if len(values) > 1:
            active.append(dim)
    return active


def make_nifti(data: np.ndarray, affine: np.ndarray, meta: dict) -> nib.Nifti1Image:
    img = nib.Nifti1Image(data, affine)
    hdr = img.header

def main(args):
    dset = h5py.File(args.filename, 'r')
    if not dset:
        print(f"Not a valid dataset: {args.filename}")
        return

    dsetNames = list(dset.keys())
    print(f"File {args.filename} contains {len(dsetNames)} groups:")
    print(" ", "\n  ".join(dsetNames))

    if not args.in_group:
        if len(dsetNames) > 1:
            print("Input group not specified -- selecting most recent")
        args.in_group = dsetNames[-1]

    if not args.out_folder:
        args.out_folder = re.sub('.h5$', '', args.filename)
        print(f"Output folder not specified -- using {args.out_folder}")

    if args.in_group not in dset:
        print(f"Could not find group {args.in_group}")
        return

    if not os.path.exists(args.out_folder):
        os.makedirs(args.out_folder)

    group = dset.get(args.in_group)

    print(f"Reading data from group '{args.in_group}' in file '{args.filename}'")

    # mrdImg data is stored as:
    #   /group/config              text of recon config parameters (optional)
    #   /group/xml                 text of ISMRMRD flexible data header (optional)
    #   /group/image_0/data        array of IsmrmrdImage data
    #   /group/image_0/header      array of ImageHeader
    #   /group/image_0/attributes  text of mrdImg MetaAttributes

    isImage = True
    imageNames = group.keys()
    print(f"Found {len(imageNames)} mrdImg sub-groups: {", ".join(imageNames)}")

    for imageName in imageNames:
        if imageName in ("config", "config_file", "xml", "configAdditional"):
            continue

        mrdImg = group[imageName]
        if not (('data' in mrdImg) and ('header' in mrdImg) and ('attributes' in mrdImg)):
            isImage = False

    dset.close()

    if (isImage is False):
        print("File does not contain properly formatted MRD raw or mrdImg data")
        return

    dset = ismrmrd.Dataset(args.filename, args.in_group, False)
    groups = dset.list()

    if ('xml' in groups):
        xml_header = dset.read_xml_header()
        xml_header = xml_header.decode("utf-8")
        mrdHead = ismrmrd.xsd.CreateFromDocument(xml_header)
    else:
        mrdHead = ismrmrd.xsd.ismrmrdHeader()

    filesWritten = 0

    for group in groups:
        if group in ("config", "config_file", "xml", "configAdditional"):
            continue

        print("Reading images from '/" + args.in_group + "/" + group + "'")
        n_images = dset.number_of_images(group)

        for imgNum in range(n_images):
            mrdImg = dset.read_image(group, imgNum)
        
            if ((mrdImg.data.shape[0] == 3) and (mrdImg.getHead().image_type == 6)):
                # RGB images
                print("RGB data not yet supported")
                continue
            else:
                if (mrdImg.data.shape[1] != 1):
                    print("Multi-slice data not yet supported")
                    continue

                if (mrdImg.data.shape[0] != 1):
                    print("Multi-channel data not yet supported")
                    continue
            
            images = []
            images.append(mrdImg)
        
        if args.no_auto:
            extra_dims = []
        else:
            extra_dims = detect_extra_dims(images)

        try:
            volume, affine, meta = assemble_volume(images, extra_dims)

        except:
            print("Error during assembly")
            continue
        
        nifti_img = make_nifti(volume, affine, meta)

        sequence_desc = str(meta.get("SequenceDescription", "")).strip()
        extra_label = ("_" + "+".join(extra_dims)) if extra_dims else ""

        if sequence_desc:
            fname = "%02d_%s_%s%s.nii.gz" % (
                files_written, sequence_desc, type_label, extra_label)
        else:
            fname = "%02d_%s%s.nii.gz" % (files_written, type_label, extra_label)

        out_path = os.path.join(args.out_folder, fname)
        nib.save(nifti_img, out_path)
        files_written += 1




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert MRD image file to NIfTI files",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename',                                         help="Input MRD (.h5) file")
    parser.add_argument('-g', '--in-group',                                 help="Input data group (default: last group)")
    parser.add_argument('-o', '--out-folder',                               help="Output folder")
    parser.add_argument('--no-auto', action='store_true', default=False,    help="Disable automatic extra-dimension detection, write a single 3D volume per series")

    args = parser.parse_args()
    main(args)
