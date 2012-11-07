import subprocess
from bipy.utils import (replace_suffix, which, flatten,
                         remove_suffix)
import os
import logging
from bcbio.utils import file_exists

logger = logging.getLogger(__name__)


def count_overlaps(in_file, bed, out_file=None):
    """ calculates coverage across the features in the bedfile
    bed """

    if not which("coverageBed"):
        logger.error("Cannot find coverageBed. Make sure it is in your "
                     "path or install bedtools.")
        exit(-1)

    if not out_file:
        out_file = replace_suffix(in_file, ".counts")

    if os.path.exists(out_file):
        return out_file

    cmd = ["coverageBed", "-abam", in_file, "-b", bed]

    with open(out_file, "w") as out_handle:
        subprocess.check_call(cmd, stdout=out_handle)
    return out_file


def multi_intersect(in_files, options=None, out_file=None):
    """ reports the intersection of multiple bed files """

    if options is None:
        options = []

    cmd = ["multiIntersectBed", options, "-i", in_files]
    cmd = flatten(cmd)
    cmd = map(str, cmd)

    out_file = _run_command(in_files, cmd, suffix=".intersect.bed",
                            out_file=out_file)
    return out_file


def _run_command(in_files, cmd, suffix="", out_file=None):
    if not out_file:
        out_file = "".join([remove_suffix(os.path.basename(x)) for x in
                            in_files]) + suffix
        out_file = os.path.join(os.path.dirname(in_files[0]), out_file)

    if file_exists(out_file):
        return out_file

    with open(out_file, "w") as out_handle:
        subprocess.check_call(cmd, stdout=out_handle)

    return out_file


def intersect(in_files, options=None, out_file=None):
    if options is None:
        options = []
    if len(in_files) != 2:
        logging.error("intersectBed needs two files")
        exit(1)
    cmd = ["intersectBed", options, "-a", in_files[0],
           "-b", in_files[1]]

    out_file = _run_command(in_files, cmd, suffix=".intersect.bed",
                            out_file=out_file)

    return out_file