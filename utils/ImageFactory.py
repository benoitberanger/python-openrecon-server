#!/bin/python3

import ismrmrd
import logging
import numpy as np
import xml.dom.minidom

# import ants

class ImageFactory:
    
    def __init__(self, mrdHeader: list[ismrmrd.ImageHeader], mrdMeta: list[ismrmrd.Meta]) -> None:
        self.image_series_index_offset      : int                       = 0
        self.ImageProcessingHistory         : list[str]                 = []
        self.SequenceDescriptionAdditional  : list[str]                 = []
        self.mrdHeader                      : list[ismrmrd.ImageHeader] = mrdHeader
        self.mrdMeta                        : list[ismrmrd.Meta]        = mrdMeta
    
    @staticmethod
    def MRD5Dto3D(data_mrd5D: np.array) -> np.array:
        """Convert MRD-5D data into 3D array """
        # Reformat data to [y x z cha img], i.e. [row col] for the first two dimensions
        data_mrd5D = data_mrd5D.transpose((3, 4, 2, 1, 0))

        logging.debug("Original image data is size %s" % (data_mrd5D.shape,))

        data_5d = data_mrd5D.astype(np.float64)

        # Reformat data from [y x z cha img] to [y x img]
        data_3d = data_5d[:,:,0,0,:]
        
        return data_3d
    
    # def ANTsImageToMRD(self, ants_image: ants.ants_image.ANTsImage, history: str|list[str] = '', seq_descrip_add: str = '') -> list[ismrmrd.Image]:
    #     """Convert ANTs Image to MRD format"""
    #     if   type(history) is list:
    #         self.ImageProcessingHistory += history
    #     elif type(history) is str and len(history)>0:
    #         self.ImageProcessingHistory.append(history)
    #     else:
    #         TypeError('bad `history` type')

    #     if len(seq_descrip_add)>0:
    #         self.image_series_index_offset += 1
    #         self.SequenceDescriptionAdditional.append(seq_descrip_add)

    #     # Reformat data from [y x img] to [y x z cha img]
    #     data = ants_image.numpy()[:,:,np.newaxis,np.newaxis,:].astype(np.int16)

    #     # Re-slice back into 2D images
    #     imagesOut = [None] * data.shape[-1]
    #     for iImg in range(data.shape[-1]):

    #         # Create new MRD instance for the inverted image
    #         # Transpose from convenience shape of [y x z cha] to MRD Image shape of [cha z y x]
    #         # from_array() should be called with 'transpose=False' to avoid warnings, and when called
    #         # with this option, can take input as: [cha z y x], [z y x], or [y x]
    #         imagesOut[iImg] = ismrmrd.Image.from_array(data[...,iImg].transpose((3, 2, 0, 1)), transpose=False)

    #         # Create a copy of the original fixed header and update the data_type
    #         # (we changed it to int16 from all other types)
    #         oldHeader = self.mrdHeader[iImg]
    #         oldHeader.data_type = imagesOut[iImg].data_type

    #         # Set the image_type to match the data_type for complex data
    #         if (imagesOut[iImg].data_type == ismrmrd.DATATYPE_CXFLOAT) or (imagesOut[iImg].data_type == ismrmrd.DATATYPE_CXDOUBLE):
    #             oldHeader.image_type = ismrmrd.IMTYPE_COMPLEX

    #         oldHeader.image_series_index += self.image_series_index_offset

    #         imagesOut[iImg].setHead(oldHeader)

    #         # Create a copy of the original ISMRMRD Meta attributes and update
    #         tmpMeta = self.mrdMeta[iImg]
    #         tmpMeta['DataRole']                       = 'Image'
    #         if len(self.ImageProcessingHistory       ) > 0: tmpMeta['ImageProcessingHistory'       ] = self.ImageProcessingHistory
    #         if len(self.SequenceDescriptionAdditional) > 0: tmpMeta['SequenceDescriptionAdditional'] = '_'.join(self.SequenceDescriptionAdditional)
    #         tmpMeta['Keep_image_geometry']            = 1

    #         metaXml = tmpMeta.serialize()
    #         logging.debug("Image MetaAttributes: %s", xml.dom.minidom.parseString(metaXml).toprettyxml())
    #         logging.debug("Image data has %d elements", imagesOut[iImg].data.size)

    #         imagesOut[iImg].attribute_string = metaXml

    #     logging.info(f'ImageFactory: {self.image_series_index_offset=}')
    #     logging.info(f'ImageFactory: {self.ImageProcessingHistory=}')
    #     logging.info(f'ImageFactory: {self.SequenceDescriptionAdditional=}')

    #     return imagesOut
    