# utils/output_series.py

import copy
import logging

import ismrmrd
import numpy as np

# Return Type of process_image
ProcessImageResult = list[tuple[np.ndarray, list[ismrmrd.ImageHeader], list[ismrmrd.Meta]]]

class OutputSeries:
    """
    Manages a collection of output image series to send back to the client.

    Each series is an independent group of images with its own pixel data,
    headers, metadata, processing history, and series label. Series are
    accumulated via add() and consumed by Pipeline.run() which calls
    send_volume_as_2Dslices() for each one in insertion order.

    The series_index_offset is managed automatically, each new series
    gets a unique offset so they appear as distinct series in the client UI.

    Typical usage:

    .. code-block:: python

        series = OutputSeries(head, meta)

        # Main result
        series.add(
            data             = processed_volume,
            process_history  = ["PYTHON", "N4"],
            sequence_description = "N4",
        )

        # Optional intermediate result in a separate series
        series.add(
            data             = mask_volume,
            process_history  = ["PYTHON", "SynthstripMask"],
            sequence_description = "Brainmask",
        )

        return series.get()

    Attributes
    ----------
    base_head : list of ismrmrd.ImageHeader
        Original headers used as template for all series.
    base_meta : list of ismrmrd.Meta
        Original Meta objects used as template for all series.
    """

    def __init__(self, head: list[ismrmrd.ImageHeader], meta: list[ismrmrd.Meta]) -> None:
        """
        Initialise the output series manager.

        Parameters
        ----------
        head : list of ismrmrd.ImageHeader
            Reference headers from the source images. Copied for each
            series so the originals are never modified.
        meta : list of ismrmrd.Meta
            Reference Meta objects from the source images. Copied for
            each series so the originals are never modified.
        """
        self.base_head   = head
        self.base_meta   = meta
        self.series:  list[tuple[np.ndarray, list, list]] = []
        self.n_series = 0


    def add(
        self,
        data:                 np.ndarray,
        process_history:      list[str] | str | None = None,
        sequence_description: list[str] | str | None = None,
    ) -> "OutputSeries":
        """
        Add an output series.

        Headers and Meta are deep-copied from the reference originals
        so each series is fully independent. The series_index_offset is
        incremented automatically for each new series.

        Parameters
        ----------
        data : np.ndarray
            Processed pixel data, shape [img, cha, z, y, x], dtype int16.
        process_history : list of str, str, or None, optional
            Processing steps to record in ImageProcessingHistory.
            Appended to any history already present in the base Meta.
            If str, wrapped in a list automatically. If None, left unchanged.
        sequence_description : list of str, str, or None, optional
            Series label shown in the client UI. If a list, joined with
            '_' (e.g. ['N4', 'Dn'] → 'N4_Dn'). If None, left unchanged.

        Returns
        -------
        OutputSeries
            Returns self to allow method chaining.
        """
        # Deep copy head and meta so series are fully independent
        head = [copy.deepcopy(h) for h in self.base_head]
        meta = [ismrmrd.Meta.deserialize(m.serialize()) for m in self.base_meta]

        # Normalise process_history
        if isinstance(process_history, str):
            process_history = [process_history]

        # Normalise sequence_description
        if isinstance(sequence_description, list):
            sequence_description = "_".join(sequence_description)

        for h, m in zip(head, meta):

            m["DataRole"]            = "Image"

            if process_history is not None:
                existing = m.get("ImageProcessingHistory") or []
                if isinstance(existing, str):
                    existing = [existing]
                m["ImageProcessingHistory"] = existing + process_history

            if sequence_description is not None:
                m["SequenceDescriptionAdditional"] = sequence_description

            # Incremente image_series_index
            logging.info(f"serie index before : {h.image_series_index}")
            h.image_series_index += self.n_series
            logging.info(f"serie index after : {h.image_series_index}")

        self.series.append((data, head, meta))
        self.n_series += 1

        logging.info(
            "OutputSeries: added series %d | description='%s' history=%s",
            self.n_series, sequence_description, process_history,
        )

        return self


    def get(self) -> ProcessImageResult:
        """
        Return all accumulated series as a list of (data, head, meta) tuples.

        Returns
        -------
        list of tuple (np.ndarray, list, list)
            All series in insertion order, ready to be consumed by
            Pipeline.run().
        """
        return self.series


    def __len__(self) -> int:
        return self.n_series


    def __repr__(self) -> str:
        return f"OutputSeries({self.n_series} series)"