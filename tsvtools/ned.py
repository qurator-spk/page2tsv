import os
import requests
import json


def ned(tsv, ner_result, ned_rest_endpoint, json_file=None, threshold=None, priority=None):

    if json_file is not None and os.path.exists(json_file):

        print('Loading {}'.format(json_file))

        with open(json_file, "r") as fp:
            ned_result = json.load(fp)

    else:

        resp = requests.post(url=ned_rest_endpoint + '/parse', json=ner_result)

        resp.raise_for_status()

        ner_parsed = json.loads(resp.content)

        ned_rest_endpoint = ned_rest_endpoint + '/ned?return_full=' + str(int(json_file is not None)).lower()

        if priority is not None:
            ned_rest_endpoint += "&priority=" + str(int(priority))

        resp = requests.post(url=ned_rest_endpoint, json=ner_parsed, timeout=3600000)

        resp.raise_for_status()

        ned_result = json.loads(resp.content)

    rids = []
    entity = ""
    entity_type = None
    tsv['ID'] = '-'
    tsv['conf'] = '-'

    def check_entity(tag):
        nonlocal entity, entity_type, rids

        if (entity != "") and ((tag == 'O') or tag.startswith('B-') or (tag[2:] != entity_type)):

            eid = entity + "-" + entity_type

            if eid in ned_result:
                if 'ranking' in ned_result[eid]:
                    ranking = ned_result[eid]['ranking']

                    # tsv.loc[rids, 'ID'] = ranking[0][1]['wikidata']
                    # if threshold is None or ranking[0][1]['proba_1'] >= threshold else ''

                    tmp = "|".join([ranking[i][1]['wikidata']
                                    for i in range(len(ranking))
                                    if threshold is None or ranking[i][1]['proba_1'] >= threshold])
                    tsv.loc[rids, 'ID'] = tmp if len(tmp) > 0 else '-'

                    tmp = ",".join([str(ranking[i][1]['proba_1'])
                                    for i in range(len(ranking))
                                    if threshold is None or ranking[i][1]['proba_1'] >= threshold])

                    tsv.loc[rids, 'conf'] = tmp if len(tmp) > 0 else '-'

            rids = []
            entity = ""
            entity_type = None

    ner_tmp = tsv.copy()
    ner_tmp.loc[~ner_tmp['NE-TAG'].isin(['O', 'B-PER', 'B-LOC', 'B-ORG', 'I-PER', 'I-LOC', 'I-ORG']), 'NE-TAG'] = 'O'

    for rid, row in ner_tmp.iterrows():

        check_entity(row['NE-TAG'])

        if row['NE-TAG'] != 'O':

            entity_type = row['NE-TAG'][2:]

            entity += " " if entity != "" else ""

            entity += str(row['TOKEN'])

            rids.append(rid)

    check_entity('O')

    return tsv, ned_result
