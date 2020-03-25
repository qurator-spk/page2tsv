import re
import click
import pandas as pd
from io import StringIO
import os
import xml.etree.ElementTree as ET
import requests
import unicodedata
import json


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


def extract_doc_links(tsv_file):

    parts = []

    header = None

    with open(tsv_file, 'r') as f:
        
        text = []
        url = None

        for line in f:

            if header is None:
                header = "\t".join(line.split()) + '\n'
                continue

            urls = [url for url in
                    re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', line)]

            if len(urls) > 0:
                if url is not None:
                    parts.append({"url": url, 'header': header, 'text': "".join(text)})
                    text = []

                url = urls[-1]
            else:
                if url is None:
                    continue

                line = '\t'.join(line.split())

                if line.count('\t') == 2:

                    line = "\t" + line

                if line.count('\t') >= 3:

                    text.append(line + '\n')

                    continue

                if line.startswith('#'):
                    continue

                if len(line) == 0:
                    continue

                print('Line error: |', line, '|Number of Tabs: ', line.count('\t'))

        if url is not None:
            parts.append({"url": url, 'header': header, 'text': "".join(text)})

    return parts


def ner(tsv, ner_rest_endpoint):

    resp = requests.post(url=ner_rest_endpoint, json={'text': " ".join(tsv.TOKEN.tolist())})

    resp.raise_for_status()

    def iterate_ner_results(result_sentences):

        for sen in result_sentences:

            for token in sen:

                yield unicodedata.normalize('NFC', token['word']), token['prediction'], False

            yield '', '', True

    ner_result = json.loads(resp.content)

    result_sequence = iterate_ner_results(ner_result)

    tsv_result = []
    for idx, row in tsv.iterrows():

        row_token = unicodedata.normalize('NFC', row.TOKEN.replace(' ', ''))

        ner_token_concat = ''
        while row_token != ner_token_concat:

            ner_token, ner_tag, sentence_break = next(result_sequence)
            ner_token_concat += ner_token

            assert len(row_token) >= len(ner_token_concat)

            if sentence_break:
                tsv_result.append((0, '', 'O', 'O', '-', row.url_id, row.left, row.right, row.top, row.bottom))
            else:
                tsv_result.append((0, ner_token, ner_tag, 'O', '-', row.url_id, row.left, row.right, row.top,
                                   row.bottom))

    return pd.DataFrame(tsv_result, columns=['No.', 'TOKEN', 'NE-TAG', 'NE-EMB', 'ID', 'url_id',
                                             'left', 'right', 'top', 'bottom']), ner_result


def ned(tsv, ner_result, ned_rest_endpoint):

    resp = requests.post(url=ned_rest_endpoint + '/parse', json=ner_result)

    resp.raise_for_status()

    ner_parsed = json.loads(resp.content)

    resp = requests.post(url=ned_rest_endpoint + '/ned', json=ner_parsed, timeout=3600000)

    resp.raise_for_status()

    ned_result = json.loads(resp.content)

    rids = []
    entity = ""
    entity_type = None
    for rid, row in tsv.iterrows():

        if (entity != "") and ((row['NE-TAG'] == 'O') or (row['NE-TAG'].startswith('B-'))):

            eid = entity + "-" + entity_type

            if eid in ned_result:
                candidates = ned_result[eid]

                tsv.loc[rids, 'ID'] = candidates[0][1]['wikidata']

            rids = []
            entity = ""
            entity_type = None

        if row['NE-TAG'] != 'O':

            entity_type = row['NE-TAG'][2:]

            entity += " " if entity != "" else ""

            entity += row['TOKEN']

            rids.append(rid)

    return tsv


@click.command()
@click.argument('page-xml-file', type=click.Path(exists=True), required=True, nargs=1)
@click.argument('tsv-out-file', type=click.Path(), required=True, nargs=1)
@click.option('--image-url', type=str, default='http://empty')
@click.option('--ner-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ner service. See https://github.com/qurator-spk/sbb_ner for details.")
@click.option('--ned-rest-endpoint', type=str, default=None,
              help="REST endpoint of sbb_ned service. See https://github.com/qurator-spk/sbb_ned for details.")
@click.option('--noproxy', type=bool, is_flag=True, help='disable proxy. default: enabled.')
@click.option('--scale-factor', type=float, default=0.5685, help='default: 0.5685')
def page2tsv(page_xml_file, tsv_out_file, image_url, ner_rest_endpoint, ned_rest_endpoint, noproxy, scale_factor):

    out_columns = ['No.', 'TOKEN', 'NE-TAG', 'NE-EMB', 'ID', 'url_id', 'left', 'right', 'top', 'bottom']

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
    line_number = 0
    rgn_number = 0
    for region in tree.findall('.//{%s}TextRegion' % xmlns):
        rgn_number += 1
        for text_line in region.findall('.//{%s}TextLine' % xmlns):
            line_number += 1

            for words in text_line.findall('./{%s}Word' % xmlns):

                for word in words.findall('./{%s}TextEquiv/{%s}Unicode' % (xmlns, xmlns)):
                    text = word.text
                    for coords in words.findall('./{%s}Coords' % xmlns):

                        # transform OCR coordinates using `scale_factor` to derive
                        # correct coordinates for the web presentation image
                        points = [int(scale_factor * float(pos))
                                  for p in coords.attrib['points'].split(' ') for pos in p.split(',')]

                        x_points = [points[i] for i in range(0, len(points), 2)]
                        y_points = [points[i] for i in range(1, len(points), 2)]

                        left = min(x_points)
                        right = max(x_points)
                        top = min(y_points)
                        bottom = max(y_points)

                        tsv.append((rgn_number, line_number, left + (right-left)/2.0,
                                    0, text, 'O', 'O', '-', len(urls), left, right, top, bottom))

    with open(tsv_out_file, 'a') as f:

        f.write('# ' + image_url + '\n')

    tsv = pd.DataFrame(tsv, columns=['rid', 'line', 'hcenter'] + out_columns)

    vlinecenter = pd.DataFrame(tsv[['line', 'top']].groupby('line', sort=False).mean().top +
                               (tsv[['line', 'bottom']].groupby('line', sort=False).mean().bottom -
                                tsv[['line', 'top']].groupby('line', sort=False).mean().top) / 2, columns=['vlinecenter'])

    tsv = tsv.merge(vlinecenter, left_on='line', right_index=True)

    regions = [region.sort_values(['vlinecenter', 'hcenter']) for rid, region in tsv.groupby('rid', sort=False)]

    tsv = pd.concat(regions)

    tsv = tsv[out_columns].reset_index(drop=True)

    try:
        if ner_rest_endpoint is not None:

            tsv, ner_result = ner(tsv, ner_rest_endpoint)

            if ned_rest_endpoint is not None:

                tsv = ned(tsv, ner_result, ned_rest_endpoint)

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
def find_entities(tsv_file, tsv_out_file, ner_rest_endpoint, ned_rest_endpoint):

    tsv = pd.read_csv(tsv_file, sep='\t', comment='#', quoting=3)

    try:
        if ner_rest_endpoint is not None:

            tsv, ner_result = ner(tsv, ner_rest_endpoint)

            if ned_rest_endpoint is not None:

                tsv = ned(tsv, ner_result, ned_rest_endpoint)

        tsv.to_csv(tsv_out_file, sep="\t", quoting=3, index=False, mode='a', header=False)
    except requests.HTTPError as e:
        print(e)
