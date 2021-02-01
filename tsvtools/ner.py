import pandas as pd
import requests
import unicodedata
import json


def ner(tsv, ner_rest_endpoint):

    resp = requests.post(url=ner_rest_endpoint, json={'text': " ".join(tsv.TOKEN.astype(str).tolist())})

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

        row_token = unicodedata.normalize('NFC', str(row.TOKEN).replace(' ', ''))

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


