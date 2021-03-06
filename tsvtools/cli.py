import click
import pandas as pd
from io import StringIO
import os
import xml.etree.ElementTree as ET
import requests
import json

from .ned import ned
from .ner import ner
from .tsv import read_tsv, write_tsv, extract_doc_links


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
@click.option('--scale-factor', type=float, default=0.5685, help='default: 0.5685')
@click.option('--ned-threshold', type=float, default=None)
def page2tsv(page_xml_file, tsv_out_file, purpose, image_url, ner_rest_endpoint, ned_rest_endpoint, noproxy, scale_factor,
             ned_threshold):

    if purpose == "NERD":
        out_columns = ['No.', 'TOKEN', 'NE-TAG', 'NE-EMB', 'ID', 'url_id', 'left', 'right', 'top', 'bottom']
    elif purpose == "OCR":
        out_columns = ['TEXT', 'url_id', 'left', 'right', 'top', 'bottom']
    else:
        raise RuntimeError("Unknown purpose.")

    if noproxy:
        os.environ['no_proxy'] = '*'

    tree = ET.parse(page_xml_file)
    xmlns = tree.getroot().tag.split('}')[0].strip('{')

    urls = []
    if os.path.exists(tsv_out_file):
        parts = extract_doc_links(tsv_out_file)

        urls = [part['url'] for part in parts]
    else:
        pd.DataFrame([], columns=out_columns). to_csv(tsv_out_file, sep="\t", quoting=3, index=False)

    tsv = []
    line_info = []
    line_number = 0
    rgn_number = 0
    for region in tree.findall('.//{%s}TextRegion' % xmlns):
        rgn_number += 1
        for text_line in region.findall('.//{%s}TextLine' % xmlns):
            line_number += 1

            points = [int(scale_factor * float(pos)) for coords in text_line.findall('./{%s}Coords' % xmlns) for p in
                      coords.attrib['points'].split(' ') for pos in p.split(',')]

            x_points, y_points = points[0::2], points[1::2]

            left, right, top, bottom = min(x_points), max(x_points), min(y_points), max(y_points)

            line_info.append((line_number, len(urls), left, right, top, bottom))

            for word in text_line.findall('./{%s}Word' % xmlns):

                for text_equiv in word.findall('./{%s}TextEquiv/{%s}Unicode' % (xmlns, xmlns)):
                    text = text_equiv.text

                    for coords in word.findall('./{%s}Coords' % xmlns):

                        # transform OCR coordinates using `scale_factor` to derive
                        # correct coordinates for the web presentation image
                        points = [int(scale_factor * float(pos))
                                  for p in coords.attrib['points'].split(' ') for pos in p.split(',')]

                        x_points, y_points = points[0::2], points[1::2]

                        left, right, top, bottom = min(x_points), max(x_points), min(y_points), max(y_points)

                        tsv.append((rgn_number, line_number, left + (right - left) / 2.0, text,
                                    len(urls), left, right, top, bottom))

    line_info = pd.DataFrame(line_info, columns=['line', 'url_id', 'left', 'right', 'top', 'bottom'])

    tsv = pd.DataFrame(tsv, columns=['rid', 'line', 'hcenter'] + ['TEXT', 'url_id', 'left', 'right', 'top', 'bottom'])

    if len(tsv) == 0:
        return

    with open(tsv_out_file, 'a') as f:

        f.write('# ' + image_url + '\n')

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

        tsv = tsv.rename(columns={'TEXT': 'TOKEN'})
    elif purpose == 'OCR':

        tsv = pd.DataFrame([(line, " ".join(part.TEXT.to_list())) for line, part in tsv.groupby('line')],
                           columns=['line', 'TEXT'])

        tsv = tsv.merge(line_info, left_on='line', right_on='line')

    tsv = tsv[out_columns].reset_index(drop=True)

    try:
        if purpose == 'NERD' and ner_rest_endpoint is not None:

            tsv, ner_result = ner(tsv, ner_rest_endpoint)

            if ned_rest_endpoint is not None:

                tsv, _ = ned(tsv, ner_result, ned_rest_endpoint, threshold=ned_threshold)

        tsv.to_csv(tsv_out_file, sep="\t", quoting=3, index=False, mode='a', header=False)
    except requests.HTTPError as e:
        print(e)


@click.command()
@click.argument('tsv-file', type=click.Path(exists=True), required=True, nargs=1)
@click.argument('tsv-out-file', type=click.Path(), required=True, nargs=1)
@click.option('--ner-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ner service. See https://github.com/qurator-spk/sbb_ner for details.")
@click.option('--ned-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ned service. See https://github.com/qurator-spk/sbb_ned for details.")
@click.option('--ned-json-file', type=str, default=None)
@click.option('--noproxy', type=bool, is_flag=True, help='disable proxy. default: proxy is enabled.')
@click.option('--ned-threshold', type=float, default=None)
def find_entities(tsv_file, tsv_out_file, ner_rest_endpoint, ned_rest_endpoint, ned_json_file, noproxy, ned_threshold):

    if noproxy:
        os.environ['no_proxy'] = '*'

    tsv, urls = read_tsv(tsv_file)

    try:
        if ner_rest_endpoint is not None:

            tsv, ner_result = ner(tsv, ner_rest_endpoint)

        elif os.path.exists(tsv_file):

            print('Using NER information that is already contained in file: {}'.format(tsv_file))

            tmp = tsv.copy()
            tmp['sen'] = (tmp['No.'] == 0).cumsum()
            tmp.loc[~tmp['NE-TAG'].isin(['O', 'B-PER', 'B-LOC', 'B-ORG', 'I-PER', 'I-LOC', 'I-ORG']), 'NE-TAG'] = 'O'

            ner_result = [[{'word': str(row.TOKEN), 'prediction': row['NE-TAG']} for _, row in sen.iterrows()]
                          for _, sen in tmp.groupby('sen')]
        else:
            raise RuntimeError("Either NER rest endpoint or NER-TAG information within tsv_file required.")

        if ned_rest_endpoint is not None:

            tsv, ned_result = ned(tsv, ner_result, ned_rest_endpoint, json_file=ned_json_file, threshold=ned_threshold)

            if ned_json_file is not None and not os.path.exists(ned_json_file):

                with open(ned_json_file, "w") as fp_json:
                    json.dump(ned_result, fp_json, indent=2, separators=(',', ': '))

        write_tsv(tsv, urls, tsv_out_file)

    except requests.HTTPError as e:
        print(e)


@click.command()
@click.argument('xls-file', type=click.Path(exists=True), required=True, nargs=1)
@click.option('--purpose', type=click.Choice(['NERD', 'OCR'], case_sensitive=False), default="NERD",
              help="Purpose of output tsv file. "
                   "\n\nNERD: NER/NED application/ground-truth creation. "
                   "\n\nOCR: OCR application/ground-truth creation. "
                   "\n\ndefault: NERD.")
def make_page2tsv_commands(xls_file, purpose):

    df = pd.read_excel(xls_file)

    for _, row in df.iterrows():
        print('page2tsv $(OPTIONS) {}.xml {}.tsv --image-url={} --scale-factor={} --purpose={}'.
              format(row.Filename, row.Filename, row.iiif_url.replace('/full/full', '/left,top,width,height/full'),
                     row.scale_factor, purpose))
