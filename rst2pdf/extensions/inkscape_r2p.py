# -*- coding: utf-8 -*-
# See LICENSE.txt for licensing terms

"""
inkscape.py is an rst2pdf extension (e.g. rst2pdf -e inkscape xxx xxxx)
which uses the inkscape program to convert an svg to a PDF, then uses
the vectorpdf code to process the PDF.

In order for this exention to work, you must ensure that inkscape is
on your PATH.

.. NOTE::

    The initial version is a proof of concept; uses subprocess in a naive way,
    and doesn't check return from inkscape for errors.
"""

import os
import shutil
import subprocess
import tempfile
from weakref import WeakKeyDictionary

import rst2pdf.image
from rst2pdf.log import log

try:
    from vectorpdf_r2p import VectorPdf
except Exception:
    from .vectorpdf_r2p import VectorPdf


class InkscapeImage(VectorPdf):

    # The filecache allows us to only read a given PDF file once
    # for every RstToPdf client object.  This allows this module
    # to usefully cache, while avoiding being the cause of a memory
    # leak in a long-running process.

    source_filecache = WeakKeyDictionary()

    def __init__(
        self,
        filename,
        width=None,
        height=None,
        kind='direct',
        mask=None,
        lazy=True,
        srcinfo=None,
    ):
        client, uri = srcinfo
        cache = self.source_filecache.setdefault(client, {})
        pdffname = cache.get(filename)
        if pdffname is None:
            progname = shutil.which('inkscape')
            tmpf, pdffname = tempfile.mkstemp(suffix='.pdf')
            os.close(tmpf)
            client.to_unlink.append(pdffname)
            cache[filename] = pdffname

            # which version of inkscape?
            cmd = [progname, '--version']
            exitcode, out, err = InkscapeImage.run_cmd(cmd)
            if out.startswith('Inkscape 0.'):
                # Inkscape 0.x uses -A
                cmd = [progname, os.path.abspath(filename), '-A', pdffname]
            else:
                # Inkscape 1.x uses --export-filename
                cmd = [
                    progname,
                    os.path.abspath(filename),
                    '--export-filename',
                    pdffname,
                ]

            try:
                result = subprocess.call(cmd)
                if result != 0:
                    log.error("Failed to run command: %s", ' '.join(cmd))
            except OSError:
                log.error("Failed to run command: %s", ' '.join(cmd))
                raise

            self.load_xobj((client, pdffname))

        pdfuri = uri.replace(filename, pdffname)
        pdfsrc = client, pdfuri
        VectorPdf.__init__(self, pdfuri, width, height, kind, mask, lazy, pdfsrc)

    @classmethod
    def available(self):
        return True

    @classmethod
    def raster(self, filename, client):
        """Returns a URI to a rasterized version of the image."""
        filename_png = '_'.join([filename, 'raster'])
        cache = self.source_filecache.setdefault(client, {})
        pngfname = cache.get(filename_png)
        if pngfname is None:
            progname = shutil.which('inkscape')
            tmpf, pngfname = tempfile.mkstemp(suffix='.png')
            os.close(tmpf)
            client.to_unlink.append(pngfname)
            cache[filename_png] = pngfname

            # which version of inkscape?
            cmd = [progname, '--version']
            exitcode, out, err = InkscapeImage.run_cmd(cmd)
            if out.startswith('Inkscape 0.'):
                # Inkscape 0.x uses -A
                cmd = [
                    progname,
                    os.path.abspath(filename),
                    '-e',
                    pngfname,
                    '-d',
                    str(client.def_dpi),
                ]
            else:
                # Inkscape 1.x uses --export-filename
                cmd = [
                    progname,
                    os.path.abspath(filename),
                    '--export-filename',
                    pngfname,
                    '-d',
                    str(client.def_dpi),
                ]

            try:
                subprocess.call(cmd)
                return pngfname
            except OSError:
                log.error("Failed to run command: %s", ' '.join(cmd))
                raise

        return None

    @staticmethod
    def run_cmd(cmd):
        """Execute a command and return exitcode, stdout and stderr."""
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        exitcode = proc.returncode
        return exitcode, out.decode(), err.decode()


def install(createpdf, options):
    """Monkey-patch our class as a replacement class for SVGImage."""
    rst2pdf.image.SVGImage = InkscapeImage
