#!/bin/python3

import argparse
from collections import defaultdict
import logging
import os
import re

import h5py
import ismrmrd
import numpy as np
import nibabel as nib

# Candidate extra dimensions, in priority order
CANDIDATE_DIMS = ["contrast", "phase", "repetition", "set", "average"]

IMTYPE_LABEL = {
    ismrmrd.IMTYPE_MAGNITUDE: "M",
    ismrmrd.IMTYPE_PHASE    : "P",
    ismrmrd.IMTYPE_REAL     : "R",
    ismrmrd.IMTYPE_IMAG     : "I",
    ismrmrd.IMTYPE_COMPLEX  : "C"
}


def _slice_pos(img: ismrmrd.image.Image) -> float:
    h = img.getHead()
    return float(np.dot(
        np.array(h.position,  dtype=float),
        np.array(h.slice_dir, dtype=float),
    ))


def _detect_stack_dir(images: list) -> float:
    first = min(images, key=_slice_pos)
    last  = max(images, key=_slice_pos)
    h0    = first.getHead()

    # single slice case
    if first is last:
        return 1.0

    disp      = np.array(last.getHead().position, dtype=float) - np.array(h0.position, dtype=float)
    slice_dir = np.array(h0.slice_dir, dtype=float)
    
    if np.dot(disp, slice_dir) >= 0:
        return 1.0
    else:
        return -1.0


def build_affine(first_img: ismrmrd.Image, stack_dir: float) -> np.ndarray:
    """
    TO-DO
    """

    img_header = first_img.getHead()

    fov        = np.array(img_header.field_of_view[:3])    # [x, y, z] in mm
    matrix     = np.array(img_header.matrix_size[:3])      # [x, y, z]
    voxel_size = fov / matrix                              # mm per voxel

    # --- Affine : LPS (MRD) to RAS (NIfTI) -------------------------------
    def lps_to_ras(v):
        return np.array([-v[0], -v[1], v[2]])

    read_dir  = lps_to_ras(img_header.read_dir)
    phase_dir = lps_to_ras(img_header.phase_dir)
    slice_dir = lps_to_ras(img_header.slice_dir)
    position  = lps_to_ras(img_header.position)

    # Construct rotation-scaling matrix
    rotation_scaling_matrix = np.column_stack([
        voxel_size[0] * np.array(read_dir),
        voxel_size[1] * np.array(phase_dir),
        voxel_size[2] * np.array(slice_dir) * stack_dir
    ])

    affine         = np.eye(4)
    affine[:3, :3]  = rotation_scaling_matrix
    affine[:3, 3]  = position
    
    return affine


def detect_extra_dims(images: list) -> list:
    possible_dims = ["contrast", "phase", "repetition", "set", "average"]
    active = []

    for dim in possible_dims:
        values = {int(getattr(img.getHead(), dim, 0)) for img in images}
        if len(values) > 1:
            active.append(dim)
    return active


def assemble_volume(images: list, extra_dims: list) :
    if not images: 
        raise ValueError("Empty image list")
    
    slice_positions = sorted({_slice_pos(img) for img in images})
    n_slices   = len(slice_positions)
    pos_to_idx = {p: i for i, p in enumerate(slice_positions)}

    extra_value_sets = []
    for dim in extra_dims:
        vals = sorted({int(getattr(img.getHead(), dim, 0)) for img in images})
        extra_value_sets.append(vals)

    extra_sizes  = [len(v) for v in extra_value_sets]
    extra_to_idx = [{v: i for i, v in enumerate(vals)} for vals in extra_value_sets]

    # Allocate volume
    sample = np.squeeze(images[0].data)
    ny, nx = sample.shape
    dtype  = images[0].data.dtype

    vol = np.zeros((n_slices, ny, nx, *extra_sizes), dtype=dtype)

    # Determine stack direction before building the affine
    stack_dir  = _detect_stack_dir(images)
    first_img  = min(images, key=_slice_pos)
    affine     = build_affine(first_img, stack_dir)

    for img in images:
        s_idx      = pos_to_idx[_slice_pos(img)]
        slice_data = np.squeeze(img.data)   # [y, x]
        e_idxs     = tuple(
            extra_to_idx[k][int(getattr(img.getHead(), dim, 0))]
            for k, dim in enumerate(extra_dims)
        )
        vol[(s_idx, slice(None), slice(None), *e_idxs)] = slice_data

    n_extra = len(extra_dims)
    perm    = (2, 1, 0, *range(3, 3 + n_extra))
    vol     = np.transpose(vol, perm)

    h = first_img.getHead()
    meta = {
        "image_type"  : IMTYPE_LABEL.get(int(h.image_type), "M"),
        "series_index": int(h.image_series_index),
        "extra_dims"  : extra_dims,
        "extra_values": extra_value_sets,
        "stack_dir"   : stack_dir,
    }
    try:
        attr = ismrmrd.Meta.deserialize(images[0].attribute_string)
        for key in ("EchoTime", "InversionTime", "RepetitionTime",
                    "SeriesDescription", "SequenceDescription", 
                    "WindowCenter", "WindowWidth"):
            if attr.get(key) is not None:
                meta[key] = attr[key]
    except Exception:
        pass

    return vol, affine, meta


#### NIfTI construction #######################################################

def make_nifti(data: np.ndarray, affine: np.ndarray, meta: dict) -> nib.Nifti1Image:
    img = nib.Nifti1Image(data, affine)
    hdr = img.header

    if data.ndim > 3:
        base_zooms  = list(hdr.get_zooms()[:3])
        extra_zooms = []
        for dim in meta.get("extra_dims", []):
            if dim == "repetition":
                extra_zooms.append(float(meta.get("RepetitionTime", 1.0)))
            elif dim == "contrast":
                extra_zooms.append(float(meta.get("EchoTime", 1.0)))
            else:
                extra_zooms.append(1.0)
        hdr.set_zooms(base_zooms + extra_zooms)

    hdr.set_xyzt_units("mm", "sec")

    desc_parts = []
    if meta.get("SeriesDescription"):
        desc_parts.append(str(meta["SeriesDescription"]))
    if meta.get("extra_dims"):
        desc_parts.append("+".join(meta["extra_dims"]))
    hdr["descrip"] = ", ".join(desc_parts)[:80].encode()

    return img

#### CLI ######################################################################

def check_MRDfile(filename: str, in_group: str, out_folder: str) -> str | None:
    # Check file and get group name
    dset = h5py.File(filename, 'r')
    if not dset:
        print(f"Not a valid dataset: {filename}")
        return None

    dsetNames = list(dset.keys())
    print(f"File {filename} contains {len(dsetNames)} groups:")
    print(" ", "\n  ".join(dsetNames))

    if not in_group:
        if len(dsetNames) > 1:
            print("Input group not specified -- selecting most recent")
        in_group = dsetNames[-1]

    if not out_folder:
        out_folder = re.sub('.h5$', '', filename)
        print(f"Output folder not specified -- using {out_folder}")

    if in_group not in dset:
        print(f"Could not find group {in_group}")
        return None

    if not os.path.exists(out_folder):
        os.makedirs(out_folder)

    group = dset.get(in_group)

    print(f"Reading data from group '{in_group}' in file '{filename}'")

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
        return None

    return in_group


def main(args):
    
    in_group = check_MRDfile(args.filename, args.in_group, args.out_folder)
    if not in_group :
        return

    # Iterate over image sub-group
    dset = ismrmrd.Dataset(args.filename, in_group, False)
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

        n_images = dset.number_of_images(group)
        print(f"Reading images from '{in_group}' ({n_images} images)")

        #  --- Read all images in a group -------------------------------------
        images = []
        for imgNum in range(n_images):
            mrdImg = dset.read_image(group, imgNum)
            meta = ismrmrd.Meta.deserialize(mrdImg.attribute_string)
        
            # Skip unsupported (multi-channel, multi-slice per header, RGB data)
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
            
            images.append(mrdImg)
        
        if not images:
            print("No usable images. Skipping group")
            continue

        # --- Separate by image_type if multiple types coexist in this group --
        type_buckets: dict[int, list] = defaultdict(list)
        for img in images:
            type_buckets[int(img.getHead().image_type)].append(img)

        for img_type, type_images in sorted(type_buckets.items()):
            type_label = IMTYPE_LABEL.get(img_type, "X")

            if args.no_auto:
                extra_dims = []
            else:
                extra_dims = detect_extra_dims(type_images)

            try:
                data, affine, meta = assemble_volume(type_images, extra_dims)
            except Exception as e:
                print(f"  ERROR: {e}")
                continue

            nifti_image = make_nifti(data, affine, meta)

            # Build filename
            sequence_desc = str(meta.get("SequenceDescription", "")).strip()

            if sequence_desc:
                outfile = "%s_%s_%s.nii.gz" % (filesWritten, sequence_desc, type_label)
            else:
                outfile = "%s_%s.nii.gz" % (filesWritten, type_label)

            out_path = os.path.join(args.out_folder, outfile)
            nib.save(nifti_image, out_path)
            print(f"{outfile} - shape={str(data.shape)}")
            filesWritten += 1

    dset.close()
    print(f"Wrote {filesWritten} NIfTI file(s) to {args.out_folder}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert MRD image file to NIfTI files",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename',                                         help="Input MRD (.h5) file")
    parser.add_argument('-g', '--in-group',                                 help="Input data group (default: last group)")
    parser.add_argument('-o', '--out-folder',                               help="Output folder")
    parser.add_argument('--no-auto', action='store_true', default=False,    help="Disable automatic extra-dimension detection, write a single 3D volume per series")

    args = parser.parse_args()
    main(args)
