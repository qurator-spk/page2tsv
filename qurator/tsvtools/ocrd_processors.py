from json import loads
from pathlib import Path
from pkg_resources import resource_string
from re import sub as re_sub

import pandas as pd
from PIL import Image

from ocrd import Processor
from ocrd_utils import getLogger, make_file_id, assert_file_grp_cardinality, MIMETYPE_PAGE
from ocrd_models import OcrdExif
from ocrd_models.constants import NAMESPACES as NS
from ocrd_models.ocrd_page import TextEquivType, to_xml
from ocrd_modelfactory import page_from_file

from .cli import page2tsv

OCRD_TOOL = loads(resource_string(__name__, 'ocrd-tool.json'))

class OcrdNeatExportProcessor(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-neat-export']
        kwargs['version'] = OCRD_TOOL['version']
        super().__init__(*args, **kwargs)

    def process(self):
        """
        Convert PAGE-XML to TSV loadable by the neat GT editor.
        """
        log = getLogger('ocrd_neat.export')
        assert_file_grp_cardinality(self.input_file_grp, 1)
        assert_file_grp_cardinality(self.output_file_grp, 1)
        iiif_url_template = self.parameter['iiif_url_template']
        noproxy = self.parameter['noproxy']

        ppn_found = self.workspace.mets._tree.find('//mods:recordIdentifier[@source="gbv-ppn"]', NS)
        if ppn_found is not None:
            ppn = ppn_found.text
        else:
            ppn = ''
        for n, input_file in enumerate(self.input_files):
            page_id = input_file.pageId or input_file.ID
            log.info('Processing: %d / %s of %d', n, page_id, len(list(self.input_files)))
            file_id = make_file_id(input_file, self.output_file_grp)
            pcgts = page_from_file(self.workspace.download_file(input_file))
            page = pcgts.get_Page()

            iiif_url = iiif_url_template\
                    .replace('{{ unique_identifier }}', self.workspace.mets.unique_identifier)\
                    .replace('{{ PPN }}', ppn)\
                    .replace('{{ page_id }}', page_id)\
                    .replace('{{ page_no }}', re_sub('[^0-9]', '', page_id))
            Path(self.output_file_grp).mkdir(exist_ok=True)
            tsv_filepath = Path(self.output_file_grp, file_id + '.tsv')
            page2tsv(input_file.local_filename, tsv_filepath, 'OCR', iiif_url, None, None, noproxy, 1.0, None, None, None, 1)

            self.workspace.add_file(
                file_id=file_id,
                file_grp=self.output_file_grp,
                page_id=page_id,
                mimetype='text/tab-separated-values',
                local_filename=str(tsv_filepath))

class OcrdNeatImportProcessor(Processor):

    def __init__(self, *args, **kwargs):
        kwargs['ocrd_tool'] = OCRD_TOOL['tools']['ocrd-neat-import']
        kwargs['version'] = OCRD_TOOL['version']
        super().__init__(*args, **kwargs)

    def process(self):
        """
        Merge neat TSV results back into PAGE-XML.
        """
        log = getLogger('ocrd_neat.import')
        assert_file_grp_cardinality(self.input_file_grp, 2)
        assert_file_grp_cardinality(self.output_file_grp, 1)
        keep_words = self.parameter['keep_words']
        for n, (page_in_file, tsv_file) in enumerate(self.zip_input_files()):
            page_id = page_in_file.pageId or page_in_file.ID
            log.info('Processing: %d / %s of %d', n, page_id, len(list(self.zip_input_files())))
            file_id = make_file_id(page_in_file, self.output_file_grp)
            pcgts = page_from_file(self.workspace.download_file(page_in_file))
            page = pcgts.get_Page()

            tsv = pd.read_csv(tsv_file.local_filename, sep='\t', comment='#', quoting=3)
            id_to_text = {}
            for _, row in tsv.iterrows():
                if str(row.TEXT).strip():
                    id_to_text[row.line_id] = row.TEXT
            for textline in page.get_AllTextLines():
                if textline.id in id_to_text:
                    textline.set_TextEquiv([TextEquivType(Unicode=id_to_text[textline.id])])
                if not keep_words:
                    textline.set_Word([])

            self.add_metadata(pcgts)
            pcgts.set_pcGtsId(file_id)
            self.workspace.add_file(
                file_id=file_id,
                file_grp=self.output_file_grp,
                page_id=page_id,
                mimetype=MIMETYPE_PAGE,
                local_filename="%s/%s.xml" % (self.output_file_grp, file_id),
                content=to_xml(pcgts)
            )
