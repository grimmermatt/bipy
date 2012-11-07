""" tool to run fastqc on FASTQ/SAM/BAM files from HTS experiments """
import subprocess
from bipy.utils import flatten, remove_suffix
from bcbio.utils import safe_makedir
import os
import logging
import abc
from mako.template import Template
from bipy.toolbox.reporting import LatexReport, safe_latex
from bipy.pipeline import AbstractRunner
import sh

logger = logging.getLogger("bipy")

_FASTQ_RANGES = {"sanger": [33, 73],
                 "solexa": [59, 104],
                 "illumina_1.3+": [64, 104],
                 "illumina_1.5+": [66, 104],
                 "illumina_1.8+": [33, 74]}


def detect_fastq_format(in_file, MAX_RECORDS=1000000):
    """
    detects the format of a fastq file
    will return multiple formats if it could be more than one
    """
    logger.info("Detecting FASTQ format on %s." % (in_file))
    kept = list(_FASTQ_RANGES.keys())
    with open(in_file) as in_handle:
        records_read = 0
        for i, line in enumerate(in_handle):
            # get the quality line
            if records_read >= MAX_RECORDS:
                break
            if i % 4 is 3:
                records_read += 1
                for c in line:
                    formats = kept
                    if len(formats) == 1:
                        return formats
                    for form in formats:
                        if (_FASTQ_RANGES[form][0] > ord(c) or
                            _FASTQ_RANGES[form][1] < ord(c)):
                            kept.remove(form)

    return formats


# list of module names for parsing the output files from fastqc
MODULE_NAMES = ["Basic Statistics", "Per base sequence quality",
                "Per sequence quality scores",
                "Per base sequence content",
                "Per base GC content",
                "Per sequence GC content",
                "Per base N content",
                "Sequence Length Distribution",
                "Overrepresented sequences"]


def _make_outdir(config):
    """ make the output directory "fastqc" where the data files live """
    outdir = os.path.join(config["dir"]["results"], "fastqc")
    safe_makedir(outdir)
    return outdir


def _make_outfile(input_file, config):
    outdir = _make_outdir(config)
    #outfile = "".join([os.path.basename(input_file), "_fastqc.zip"])
    outfile = "".join([remove_suffix(os.path.basename(input_file)),
                       "_fastqc.zip"])
    return os.path.join(outdir, outfile)


def _build_command(input_file, fastqc_config, config):
    program = fastqc_config["program"]
    options = list(flatten(fastqc_config["options"]))
    outdir = _make_outdir(config)
    options += ["--outdir", outdir]
    cmd = list(flatten([program, options, input_file]))
    return cmd


def run(input_file, fastqc_config, config):
    outfile = _make_outfile(input_file, config)
    # if it is already done skip it
    if os.path.exists(outfile):
        return outfile

    cmd = _build_command(input_file, fastqc_config, config)
    subprocess.check_call(cmd)

    return outfile





class FastQCParser(object):
    """
    Parses the directory of FastQC output to prepare a report for
    output. Mostly lifted from Brad Chapman (bcbio).

    """

    GRAPHS = (("per_base_quality.png", "", 1.0),
              ("per_base_sequence_content.png", "", 0.85),
              ("per_sequence_gc_content.png", "", 0.85),
              ("kmer_profiles.png", "", 0.85),
              ("duplication_levels.png", "", 0.85),
              ("per_bases_n_content.png", "", 0.85),
              ("per_sequence_quality.png", "", 1.0),
              ("sequence_length_distribution.png", "", 1.0))

    def __init__(self, base_dir):
        self._dir = base_dir
        self._max_seq_size = 45
        self._max_overrep = 20

    def get_fastqc_graphs(self):
        final_graphs = []
        for f, caption, size in self.GRAPHS:
            full_f = os.path.join(self._dir, "Images", f)
            if os.path.exists(full_f):
                final_graphs.append((full_f, caption, size))
        return final_graphs

    def get_fastqc_summary(self):
        stats = {}
        for stat_line in self._fastqc_data_section("Basic Statistics")[1:]:
            k, v = [safe_latex(x) for x in stat_line.split("\t")[:2]]
            stats[k] = v
        over_rep = []
        for line in self._fastqc_data_section("Overrepresented sequences")[1:]:
            parts = [safe_latex(x) for x in line.split("\t")]
            over_rep.append(parts)
            over_rep[-1][0] = self._splitseq(over_rep[-1][0])
        return stats, over_rep[:self._max_overrep]

    def _splitseq(self, seq):
        pieces = []
        cur_piece = []
        for s in seq:
            if len(cur_piece) >= self._max_seq_size:
                pieces.append("".join(cur_piece))
                cur_piece = []
            cur_piece.append(s)
        pieces.append("".join(cur_piece))
        return " ".join(pieces)

    def _fastqc_data_section(self, section_name):
        out = []
        in_section = False
        data_file = os.path.join(self._dir, "fastqc_data.txt")
        if os.path.exists(data_file):
            with open(data_file) as in_handle:
                for line in in_handle:
                    if line.startswith(">>%s" % section_name):
                        in_section = True
                    elif in_section:
                        if line.startswith(">>END"):
                            break
                        out.append(line.rstrip("\r\n"))
        return out


class FastQCReport(LatexReport):

    CAPTIONS = {"per_base_quality.png": "",
                "per_base_sequence_content.png": "",
                "per_sequence_gc_content.png": "",
                "kmer_profiles.png": "",
                "duplication_levels.png": "",
                "per_bases_n_content.png": "",
                "per_sequence_quality.png": "",
                "sequence_length_distribution.png": ""}

    def __init__(self):
        pass

    def template(self):
        return self._template

    def _add_captions(self, figures):
        new_figures = []
        for figure in figures:
            filename = os.path.basename(figure)
            caption = self.CAPTIONS.get(filename, "")
            new_figures.append((figure[0], caption, figure[2]))
        return new_figures

    def generate_report(self, name, summary=None, figures=None, overrep=None):
        template = Template(self._template)
        section = template.render(name=name, summary=summary,
                                  summary_table=summary, figures=figures,
                                  overrep=overrep)
        return section

    _template = r"""
\subsection*{FastQC report for ${name}}

% if summary:
    \begin{table}[h]
    \centering
    \begin{tabular}{|l|r|}
    \hline
    % for k, v in summary.items():
        ${k} & ${v} \\\
    % endfor
    \hline
    \end{tabular}
    \caption{Summary of lane results}
    \end{table}
% endif

% if figures:
    % for i, (figure, caption, size) in enumerate(figures):
        \begin{figure}[htbp]
          \centering
          \includegraphics[width=${size}\linewidth] {${figure}}
          \caption{${caption}}
        \end{figure}
    % endfor
% endif

% if overrep:
    % if len(overrep) > 0:
        \begin{table}[htbp]
        \centering
        \begin{tabular}{|p{8cm}rrp{4cm}|}
        \hline
        Sequence & Count & Percent & Match \\\
        \hline
        % for seq, count, percent, match in overrep:
            \texttt{${seq}} & ${count} & ${"%.2f" % float(percent)} & ${match} \\\
        % endfor
        \hline
        \end{tabular}
        \caption{Overrepresented read sequences}
        \end{table}
    % endif
% endif
"""


class RNASeqFastQCReport(FastQCReport):
    """FastQCreport class for outputting information from RNASeq experiments"""

    CAPTIONS = {"per_base_quality.png": "",
                "per_base_sequence_content.png": "",
                "per_sequence_gc_content.png": "",
                "kmer_profiles.png": "",
                "duplication_levels.png": "",
                "per_bases_n_content.png": "",
                "per_sequence_quality.png": "",
                "sequence_length_distribution.png": ""}