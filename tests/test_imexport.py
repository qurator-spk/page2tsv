from pathlib import Path
from shutil import copytree
from pytest import fixture

from ocrd_utils import pushd_popd
from ocrd_models.ocrd_page import parse
from ocrd import Resolver

from tsvtools.ocrd_processors import OcrdNeatExportProcessor, OcrdNeatImportProcessor

@fixture
def testws(tmpdir):
    copytree('tests/testws', f'{tmpdir}/ws')
    return Resolver().workspace_from_url(f'{tmpdir}/ws/mets.xml')

def test_imexport(testws):
    wsdir = testws.directory
    exporter = OcrdNeatExportProcessor(workspace=testws, input_file_grp='TESS', output_file_grp='OUT')
    exporter.process()
    outfile = Path(wsdir, 'OUT/FILE_0005_OUT.tsv')
    assert outfile.exists()
    assert 'Ein Welt-Stantenbund	0	174	1116	169	280		region0000_line0001' in outfile.read_text()
    assert outfile.read_text().splitlines()[1] == '# https://content.staatsbibliothek-berlin.de/dc/PPN680203753-0005/left,top,width,height/full/0/default.jpg'

    outfile.write_text(outfile.read_text().replace('Stantenbund', 'Staatenbund'))

    importer = OcrdNeatImportProcessor(workspace=testws, input_file_grp='TESS,OUT', output_file_grp='TESS-CORRECTED')
    importer.process()

    origfile = Path(wsdir, 'TESS/FILE_0005_TESS.xml')
    corrfile = Path(wsdir, 'TESS-CORRECTED/FILE_0005_TESS-CORRECTED.xml')

    assert origfile.exists()
    assert corrfile.exists()

    origpage = parse(origfile)
    corrpage = parse(corrfile)

    origline = origpage.get_Page().get_TextRegion()[0].get_TextLine()[1].get_TextEquiv()[0].Unicode
    corrline = corrpage.get_Page().get_TextRegion()[0].get_TextLine()[1].get_TextEquiv()[0].Unicode

    assert 'Stantenbund' in origline
    assert 'Stantenbund' not in corrline

    assert 'Staatenbund' not in origline
    assert 'Staatenbund' in corrline
