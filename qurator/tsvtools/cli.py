import glob
import re
import os
from io import StringIO
from pathlib import Path

import numpy as np
import click
import pandas as pd
import requests
from lxml import etree as ET

import xml.etree.ElementTree as ElementTree
import unicodedata

from ocrd_models.ocrd_page import parse
from ocrd_utils import bbox_from_points

from qurator.utils.tsv import read_tsv, write_tsv, extract_doc_links
from .ocr import get_conf_color

from qurator.utils.ner import ner
from qurator.utils.ned import ned


@click.command()
@click.argument('tsv-file', type=click.Path(exists=True), required=True, nargs=1)
@click.argument('url-file', type=click.Path(exists=False), required=True, nargs=1)
def extract_document_links(tsv_file, url_file):

    parts = extract_doc_links(tsv_file)

    urls = [part['url'] for part in parts]

    urls = pd.DataFrame(urls, columns=['url'])

    urls.to_csv(url_file, sep="\t", quoting=3, index=False)


@click.command()
@click.argument('tsv-file', type=click.Path(exists=True), required=True, nargs=1)
@click.argument('annotated-tsv-file', type=click.Path(exists=False), required=True, nargs=1)
def annotate_tsv(tsv_file, annotated_tsv_file):

    parts = extract_doc_links(tsv_file)

    annotated_parts = []

    for part in parts:

        part_data = StringIO(part['header'] + part['text'])

        df = pd.read_csv(part_data, sep="\t", comment='#', quoting=3)

        df['url_id'] = len(annotated_parts)

        annotated_parts.append(df)

    df = pd.concat(annotated_parts)

    df.to_csv(annotated_tsv_file, sep="\t", quoting=3, index=False)


def alto_iterate_textblocks(xml_file=None, root=None):

    if root is None:
        tree = ElementTree.parse(xml_file)
        root = tree.getroot()

    for idx, block_elem in enumerate(root.iter('{http://www.loc.gov/standards/alto/ns-v2#}TextBlock')):

        id = str(idx)
        if 'ID' in block_elem.attrib:
            id = block_elem.attrib['ID']

        yield id, block_elem


def alto_iterate_lines(root):

    for idx, line_elem in enumerate(root.iter('{http://www.loc.gov/standards/alto/ns-v2#}TextLine')):

        left, top, right, bottom = -1, -1, -1, -1

        if 'HPOS' in line_elem.attrib:
            left = int(line_elem.attrib['HPOS'])

        if 'VPOS' in line_elem.attrib:
            top = int(line_elem.attrib['VPOS'])

        if 'HPOS' in line_elem.attrib and 'WIDTH' in line_elem.attrib:
            right = int(line_elem.attrib['HPOS']) + int(line_elem.attrib['WIDTH'])

        if 'VPOS' in line_elem.attrib and 'HEIGHT' in line_elem.attrib:
            bottom = int(line_elem.attrib['VPOS']) + int(line_elem.attrib['HEIGHT'])

        yield line_elem, str(idx), left, right, top, bottom


def alto_iterate_string_elements(root):

    for string_elem in root.iter('{http://www.loc.gov/standards/alto/ns-v2#}String'):

        if 'CONTENT' in string_elem.attrib:
            content = string_elem.attrib['CONTENT']
        else:
            content = str(np.NAN)

        left, top, right, bottom = -1, -1, -1, -1

        if 'HPOS' in string_elem.attrib:
            left = int(string_elem.attrib['HPOS'])

        if 'VPOS' in string_elem.attrib:
            top = int(string_elem.attrib['VPOS'])

        if 'HPOS' in string_elem.attrib and 'WIDTH' in string_elem.attrib:
            right = int(string_elem.attrib['HPOS']) + int(string_elem.attrib['WIDTH'])

        if 'VPOS' in string_elem.attrib and 'HEIGHT' in string_elem.attrib:
            bottom = int(string_elem.attrib['VPOS']) + int(string_elem.attrib['HEIGHT'])

        yield unicodedata.normalize('NFC', content), left, top, right, bottom


def alto2tsv(alto_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint,
             noproxy, scale_factor, ned_threshold, ned_priority):
    if purpose == "NERD":
        out_columns = ['No.', 'TOKEN', 'NE-TAG', 'NE-EMB', 'ID', 'url_id', 'left', 'right', 'top', 'bottom', 'conf']
    elif purpose == "OCR":
        out_columns = ['TEXT', 'url_id', 'left', 'right', 'top', 'bottom', 'conf', 'line_id']

    else:
        raise RuntimeError("Unknown purpose.")

    if noproxy:
        os.environ['no_proxy'] = '*'

    urls = []
    if os.path.exists(tsv_out_file):
        parts = extract_doc_links(tsv_out_file)
        urls = [part['url'] for part in parts]
    else:
        pd.DataFrame([], columns=out_columns).to_csv(tsv_out_file, sep="\t", quoting=3, index=False)

    tsv = []
    line_info = []

    for region_idx, region in alto_iterate_textblocks(alto_xml_file):

        for line, _, l_left, l_right, l_top, l_bottom in alto_iterate_lines(region):

            line_id = len(line_info)

            line_info.append((len(urls), l_left, l_right, l_top, l_bottom, line_id))

            for word_num, (word, left, top, right, bottom) in enumerate(alto_iterate_string_elements(line)):

                word = word.strip()

                if len(word) == 0:
                    continue

                if len(word.split()) > 1:
                    print(word)
                    continue

                left, top, right, bottom = [int(scale_factor * x) for x in [left, top, right, bottom]]

                tsv.append((region_idx, left + (right - left) / 2.0,
                            word, len(urls), left, right, top, bottom, line_id))

    line_info = pd.DataFrame(line_info, columns=['url_id', 'left', 'right', 'top', 'bottom', 'line_id'])

    tsv = pd.DataFrame(tsv, columns=['rid', 'hcenter'] +
                                    ['TEXT', 'url_id', 'left', 'right', 'top', 'bottom', 'line_id'])

    with open(tsv_out_file, 'a') as f:
        f.write('# ' + image_url + '\n')

    if len(tsv) == 0:
        return

    vlinecenter = pd.DataFrame(tsv[['line_id', 'top']].groupby('line_id', sort=False).mean().top +
                               (tsv[['line_id', 'bottom']].groupby('line_id', sort=False).mean().bottom -
                                tsv[['line_id', 'top']].groupby('line_id', sort=False).mean().top) / 2,
                               columns=['vlinecenter'])

    tsv = tsv.merge(vlinecenter, left_on='line_id', right_index=True)

    regions = [region.sort_values(['vlinecenter', 'hcenter']) for rid, region in tsv.groupby('rid', sort=False)]
    tsv = pd.concat(regions)

    if purpose == 'NERD':
        tsv['No.'] = 0
        tsv['NE-TAG'] = 'O'
        tsv['NE-EMB'] = 'O'
        tsv['ID'] = '-'
        tsv['conf'] = '-'
        tsv = tsv.rename(columns={'TEXT': 'TOKEN'})

    elif purpose == 'OCR':
        tsv = pd.DataFrame([(line_id, " ".join(part.TEXT.to_list())) for line_id, part in tsv.groupby('line_id')],
                           columns=['line_id', 'TEXT'])
        tsv = tsv.merge(line_info, left_on='line_id', right_index=True)
    tsv = tsv[out_columns].reset_index(drop=True)

    try:
        if purpose == 'NERD' and ner_rest_endpoint is not None:
            tsv, ner_result = ner(tsv, ner_rest_endpoint)
            if ned_rest_endpoint is not None:
                tsv, _ = ned(tsv, ner_result, ned_rest_endpoint, threshold=ned_threshold, priority=ned_priority)

        tsv.to_csv(tsv_out_file, sep="\t", quoting=3, index=False, mode='a', header=False)
    except requests.HTTPError as e:
        print(e)

def unicode_normalize(text, normalization_map=None, use_combining_characters=True):

    if normalization_map is None:
        ret = "".join([c if unicodedata.category(c) != "Co" else '' for c in text])

        if ret != text:
            print("Warning: Due to unicode normalization possible loss of information: "
                  "{} => {} (normalization file missing?)".format(text, ret))

    elif use_combining_characters:
        ret = "".join([c if unicodedata.category(c) != "Co" else
                        "{}{}".format(normalization_map.loc[ord(c)].base,
                                      chr(int(normalization_map.loc[ord(c)].combining_character, base=16))
                                      if normalization_map.loc[ord(c)].combining_character != '' else '')
                        if ord(c) in normalization_map.index else '' for c in text])

        # do it again since the normalization map may again contain unicode private use chars
        ret = "".join([c if unicodedata.category(c) != "Co" else '' for c in ret])

        if ret != text:
            print("Warning: Due to unicode normalization possible loss of information: "
                  "{} => {}".format(text, ret))
    else:
        ret = "".join([c if unicodedata.category(c) != "Co" else
                       normalization_map.loc[ord(c)].base
                       if ord(c) in normalization_map.index else ''
                       for c in text])

        # do it again since the normalization map may again contain unicode private use chars
        ret = "".join([c if unicodedata.category(c) != "Co" else '' for c in ret])

        if ret != text:
            print("Warning: Due to unicode normalization possible loss of information: "
                  "{} => {}".format(text, ret))

    return unicodedata.normalize('NFC', ret)

def page2tsv(page_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint,
             noproxy, scale_factor, ned_threshold, min_confidence, max_confidence, ned_priority, normalization_file):

    print("page2tsv - processing file: {}".format(page_xml_file))

    if purpose == "NERD":
        out_columns = ['No.', 'TOKEN', 'NE-TAG', 'NE-EMB', 'ID', 'url_id', 'left', 'right', 'top', 'bottom', 'conf']
    elif purpose == "OCR":
        out_columns = ['TEXT', 'url_id', 'left', 'right', 'top', 'bottom', 'conf', 'line_id']
        if min_confidence is not None and max_confidence is not None:
            out_columns += ['ocrconf']
    else:
        raise RuntimeError("Unknown purpose.")

    if noproxy:
        os.environ['no_proxy'] = '*'

    urls = []
    if os.path.exists(tsv_out_file):
        parts = extract_doc_links(tsv_out_file)
        urls = [part['url'] for part in parts]
    else:
        pd.DataFrame([], columns=out_columns).to_csv(tsv_out_file, sep="\t", quoting=3, index=False)

    pcgts = parse(page_xml_file)
    tsv = []
    line_info = []

    _unicode_normalize = unicode_normalize

    if normalization_file is not None:
        normalization_map = pd.read_pickle(normalization_file)

        normalization_map = normalization_map.set_index('decimal')

        # import ipdb;ipdb.set_trace()

        _unicode_normalize = lambda s: unicode_normalize(s, normalization_map=normalization_map)

    for region_idx, region in enumerate(pcgts.get_Page().get_AllRegions(classes=['Text'], order='reading-order')):
        for text_line in region.get_TextLine():
            left, top, right, bottom = [int(scale_factor * x) for x in bbox_from_points(text_line.get_Coords().points)]

            if min_confidence is not None and max_confidence is not None:
                conf = np.max([textequiv.conf for textequiv in text_line.get_TextEquiv()])
            else:
                conf = np.nan

            line_info.append((len(urls), left, right, top, bottom, conf, text_line.id))

            words = [word for word in text_line.get_Word()]

            if len(words) <= 0:
                for text_equiv in text_line.get_TextEquiv():
                    # transform OCR coordinates using `scale_factor` to derive
                    # correct coordinates for the web presentation image
                    left, top, right, bottom = [int(scale_factor * x) for x in bbox_from_points(text_line.get_Coords().points)]

                    text = text_equiv.get_Unicode()

                    for text_part in text.split(" "):

                        tsv.append((region_idx, len(line_info) - 1, left + (right - left) / 2.0,
                                    _unicode_normalize(text_part), len(urls), left, right, top, bottom, text_line.id))
            else:
                for word in words:
                    # XXX TODO make this configurable
                    textequiv = ''
                    list_textequivs = word.get_TextEquiv()
                    if list_textequivs:
                        textequiv = list_textequivs[0].get_Unicode()
                    # transform OCR coordinates using `scale_factor` to derive
                    # correct coordinates for the web presentation image
                    left, top, right, bottom = [int(scale_factor * x) for x in bbox_from_points(word.get_Coords().points)]
                    tsv.append((region_idx, len(line_info) - 1, left + (right - left) / 2.0,
                                _unicode_normalize(textequiv), len(urls), left, right, top, bottom, text_line.id))

    line_info = pd.DataFrame(line_info, columns=['url_id', 'left', 'right', 'top', 'bottom', 'conf', 'line_id'])

    if min_confidence is not None and max_confidence is not None:
        line_info['ocrconf'] = line_info.conf.map(lambda x: get_conf_color(x, min_confidence, max_confidence))

    tsv = pd.DataFrame(tsv, columns=['rid', 'line', 'hcenter'] +
                                    ['TEXT', 'url_id', 'left', 'right', 'top', 'bottom', 'line_id'])

    # print(tsv)
    with open(tsv_out_file, 'a') as f:
        f.write('# ' + image_url + '\n')

    if len(tsv) == 0:
        return

    vlinecenter = pd.DataFrame(tsv[['line', 'top']].groupby('line', sort=False).mean().top +
                               (tsv[['line', 'bottom']].groupby('line', sort=False).mean().bottom -
                                tsv[['line', 'top']].groupby('line', sort=False).mean().top) / 2,
                               columns=['vlinecenter'])

    tsv = tsv.merge(vlinecenter, left_on='line', right_index=True)
    regions = [region.sort_values(['vlinecenter', 'hcenter']) for rid, region in tsv.groupby('rid', sort=False)]
    tsv = pd.concat(regions)

    if purpose == 'NERD':
        tsv['No.'] = 0
        tsv['NE-TAG'] = 'O'
        tsv['NE-EMB'] = 'O'
        tsv['ID'] = '-'
        tsv['conf'] = '-'
        tsv = tsv.rename(columns={'TEXT': 'TOKEN'})

    elif purpose == 'OCR':
        tsv = pd.DataFrame([(line, " ".join(part.TEXT.to_list())) for line, part in tsv.groupby('line')],
                           columns=['line', 'TEXT'])
        tsv = tsv.merge(line_info, left_on='line', right_index=True)
    tsv = tsv[out_columns].reset_index(drop=True)

    # import ipdb;ipdb.set_trace()

    try:
        if purpose == 'NERD' and ner_rest_endpoint is not None:
            tsv, ner_result = ner(tsv, ner_rest_endpoint)
            if ned_rest_endpoint is not None:
                tsv, _ = ned(tsv, ner_result, ned_rest_endpoint, threshold=ned_threshold, priority=ned_priority)

        # import ipdb;ipdb.set_trace()

        tsv.to_csv(tsv_out_file, sep="\t", quoting=3, index=False, mode='a', header=False, encoding='utf-8')
    except requests.HTTPError as e:
        print(e)


def tsv2page(output_filename, keep_words, page_file, tsv_file):
    if not output_filename:
        output_filename = Path(page_file).stem + '.corrected.xml'
    ns = {'pc': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15'}
    tsv = pd.read_csv(tsv_file, sep='\t', comment='#', quoting=3)
    tree = ET.parse(page_file)
    for _, row in tsv.iterrows():
        el_textline = tree.find(f'//pc:TextLine[@id="{row.line_id}"]', namespaces=ns)
        el_textline.find('pc:TextEquiv/pc:Unicode', namespaces=ns).text = row.TEXT
        if not keep_words:
            for el_word in el_textline.findall('pc:Word', namespaces=ns):
                el_textline.remove(el_word)
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(ET.tostring(tree, pretty_print=True).decode('utf-8'))


@click.command()
@click.option('--output-filename', '-o', help="Output filename. "
                                              "If omitted, PAGE-XML filename with .corrected.xml extension")
@click.option('--keep-words', '-k', is_flag=True, help="Keep (out-of-date) Words of TextLines")
@click.argument('page-file')
@click.argument('tsv-file')
def tsv2page_cli(output_filename, keep_words, page_file, tsv_file):
    return tsv2page(output_filename, keep_words, page_file, tsv_file)


@click.command()
@click.option('--xls-file', type=click.Path(exists=True), default=None,
              help="Read parameters from xls-file. Expected columns:  Filename, iiif_url, scale_factor.")
@click.option('--directory', type=click.Path(exists=True), default=None,
              help="Search directory for PPN**/*.xml files. Extract PPN and file number into image-url.")
@click.option('--purpose', type=click.Choice(['NERD', 'OCR'], case_sensitive=False), default="NERD",
              help="Purpose of output tsv file. "
                   "\n\nNERD: NER/NED application/ground-truth creation. "
                   "\n\nOCR: OCR application/ground-truth creation. "
                   "\n\ndefault: NERD.")
def make_page2tsv_commands(xls_file, directory, purpose):
    if xls_file is not None:

        if xls_file.endswith(".xls"):
            df = pd.read_excel(xls_file)
        else:
            df = pd.read_excel(xls_file, engine='openpyxl')

        df = df.dropna(how='all')

        for _, row in df.iterrows():
            print('page2tsv $(OPTIONS) {}.xml {}.tsv --image-url={} --scale-factor={} --purpose={}'.
                  format(row.Filename, row.Filename, row.iiif_url.replace('/full/full', '/left,top,width,height/full'),
                         row.scale_factor, purpose))

    elif directory is not None:
        for file in glob.glob('{}/**/*.xml'.format(directory), recursive=True):

            ma = re.match('(.*/(PPN[0-9X]+)/.*?([0-9]+).*?).xml', file)

            if ma:
                print('page2tsv {} {}.tsv '
                      '--image-url=https://content.staatsbibliothek-berlin.de/dc/'
                      '{}-{:08d}/left,top,width,height/full/0/default.jpg --scale-factor=1.0 --purpose={}'.
                      format(file, ma.group(1), ma.group(2), int(ma.group(3)), purpose))


@click.command()
@click.argument('page-xml-file', type=click.Path(exists=True), required=True, nargs=1)
@click.argument('tsv-out-file', type=click.Path(), required=True, nargs=1)
@click.option('--purpose', type=click.Choice(['NERD', 'OCR'], case_sensitive=False), default="NERD",
              help="Purpose of output tsv file. "
                   "\n\nNERD: NER/NED application/ground-truth creation. "
                   "\n\nOCR: OCR application/ground-truth creation. "
                   "\n\ndefault: NERD.")
@click.option('--image-url', type=str, default='http://empty')
@click.option('--ner-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ner service. See https://github.com/qurator-spk/sbb_ner for details. "
                   "Only applicable in case of NERD.")
@click.option('--ned-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ned service. See https://github.com/qurator-spk/sbb_ned for details. "
                   "Only applicable in case of NERD.")
@click.option('--noproxy', type=bool, is_flag=True, help='disable proxy. default: enabled.')
@click.option('--scale-factor', type=float, default=1.0, help='default: 1.0')
@click.option('--ned-threshold', type=float, default=None)
@click.option('--min-confidence', type=float, default=None)
@click.option('--max-confidence', type=float, default=None)
@click.option('--ned-priority', type=int, default=1)
@click.option('--normalization-file', type=click.Path(exists=True), default=None)
def page2tsv_cli(page_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint,
             noproxy, scale_factor, ned_threshold, min_confidence, max_confidence, ned_priority, normalization_file):
    return page2tsv(page_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint,
             noproxy, scale_factor, ned_threshold, min_confidence, max_confidence, ned_priority, normalization_file)


@click.command()
@click.argument('alto-xml-file', type=click.Path(exists=True), required=True, nargs=1)
@click.argument('tsv-out-file', type=click.Path(), required=True, nargs=1)
@click.option('--purpose', type=click.Choice(['NERD', 'OCR'], case_sensitive=False), default="NERD",
              help="Purpose of output tsv file. "
                   "\n\nNERD: NER/NED application/ground-truth creation. "
                   "\n\nOCR: OCR application/ground-truth creation. "
                   "\n\ndefault: NERD.")
@click.option('--image-url', type=str, default='http://empty')
@click.option('--ner-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ner service. See https://github.com/qurator-spk/sbb_ner for details. "
                   "Only applicable in case of NERD.")
@click.option('--ned-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ned service. See https://github.com/qurator-spk/sbb_ned for details. "
                   "Only applicable in case of NERD.")
@click.option('--noproxy', type=bool, is_flag=True, help='disable proxy. default: enabled.')
@click.option('--scale-factor', type=float, default=1.0, help='default: 1.0')
@click.option('--ned-threshold', type=float, default=None)
@click.option('--ned-priority', type=int, default=1)
def alto2tsv_cli(alto_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint,
             noproxy, scale_factor, ned_threshold, ned_priority):
    return alto2tsv(alto_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint,
             noproxy, scale_factor, ned_threshold, ned_priority)
