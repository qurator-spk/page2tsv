# TSV - Processing Tools

Create .tsv files that can be viewed and edited with [neat](https://github.com/qurator-spk/neat).

## Installation:

Required python version is 3.11. 
Consider use of [pyenv](https://github.com/pyenv/pyenv) if that python version is not available on your system. 

Activate virtual environment (virtualenv):
```
source venv/bin/activate
```
or (pyenv):
```
pyenv activate my-python-3.11-virtualenv
```

Update pip:
```
pip install -U pip
```
Install sbb_images:
```
pip install git+https://github.com/qurator-spk/page2tsv.git
```

## PAGE-XML to TSV Transformation:

Create a TSV file from OCR in PAGE-XML format (with word segmentation):

```
page2tsv PAGE1.xml PAGE.tsv --image-url=http://link-to-corresponding-image-1
```

In order to create a TSV file for multiple PAGE XML files just perform successive calls
of the tool using the same TSV file:

```
page2tsv PAGE1.xml PAGE.tsv --image-url=http://link-to-corresponding-image-1
page2tsv PAGE2.xml PAGE.tsv --image-url=http://link-to-corresponding-image-2
page2tsv PAGE3.xml PAGE.tsv --image-url=http://link-to-corresponding-image-3
page2tsv PAGE4.xml PAGE.tsv --image-url=http://link-to-corresponding-image-4
page2tsv PAGE5.xml PAGE.tsv --image-url=http://link-to-corresponding-image-5
...
...
...
```

For instance, for the file [example.xml](https://github.com/qurator-spk/page2tsv/blob/master/example.xml):

```
page2tsv example.xml example.tsv --image-url=http://content.staatsbibliothek-berlin.de/zefys/SNP27646518-18800101-0-3-0-0/left,top,width,height/full/0/default.jpg
```

---

## Processing of already existing TSV files:

Create a URL-annotated TSV file from an existing TSV file:

```
annotate-tsv enp_DE.tsv enp_DE-annotated.tsv
```

# Command-line interface:

```
page2tsv --help
Usage: page2tsv [OPTIONS] PAGE_XML_FILE TSV_OUT_FILE

  Converts a page-XML file into a TSV file that can be edited with neat.
  Optionally the tool also accepts NER and Entitiy Linking API-Endpoints as
  parameters and performs NER and EL and the document if these are provided.

  PAGE_XML_FILE: The source page-XML file. TSV_OUT_FILE: Resulting TSV file.

Options:
  --purpose [NERD|OCR]       Purpose of output tsv file.
                             
                             NERD: NER/NED application/ground-truth creation.
                             
                             OCR: OCR application/ground-truth creation.
                             
                             default: NERD.
  --image-url TEXT           An image retrieval link that enables neat to show
                             the scan images corresponding to the text tokens.
                             Example: https://content.staatsbibliothek-berlin.
                             de/zefys/SNP26824620-18371109-0-1-0-0/left,top,wi
                             dth,height/full/0/default.jpg
  --ner-rest-endpoint TEXT   REST endpoint of sbb_ner service. See
                             https://github.com/qurator-spk/sbb_ner for
                             details. Only applicable in case of NERD.
  --ned-rest-endpoint TEXT   REST endpoint of sbb_ned service. See
                             https://github.com/qurator-spk/sbb_ned for
                             details. Only applicable in case of NERD.
  --noproxy                  disable proxy. default: enabled.
  --scale-factor FLOAT       default: 1.0
  --ned-threshold FLOAT
  --min-confidence FLOAT
  --max-confidence FLOAT
  --ned-priority INTEGER
  --normalization-file PATH
  --help                     Show this message and exit.
```

```
tsv2tsv --help
Usage: tsv2tsv [OPTIONS] TSV_IN_FILE

Options:
  --tsv-out-file PATH          Write modified TSV to this file.
  --ner-rest-endpoint TEXT     REST endpoint of sbb_ner service. See
                               https://github.com/qurator-spk/sbb_ner for
                               details.
  --noproxy                    disable proxy. default: enabled.
  --num-tokens                 Print number of tokens in input/output file.
  --sentence-count             Print sentence count in input/output file.
  --max-sentence-len           Print maximum sentence len for input/output
                               file.
  --keep-tokenization          Keep the word tokenization exactly as it is.
  --sentence-split-only        Do only sentence splitting.
  --show-urls                  Print contained visualization URLs.
  --just-zero                  Process only files that have max sentence
                               length zero,i.e., that do not have sentence
                               splitting.
  --sanitize-sentence-numbers  Sanitize sentence numbering.
  --show-columns               Show TSV columns.
  --drop-column TEXT           Drop column
  --help                       Show this message and exit.
```

```
alto2tsv --help
Usage: alto2tsv [OPTIONS] ALTO_XML_FILE TSV_OUT_FILE

  Converts a ALTO-XML file into a TSV file that can be edited with neat.
  Optionally the tool also accepts NER and Entitiy Linking API-Endpoints as
  parameters and performs NER and EL and the document if these are provided.

  ALTO_XML_FILE: The source ALTO-XML file. 
  TSV_OUT_FILE: Resulting TSV file.

Options:
  --purpose [NERD|OCR]      Purpose of output tsv file.
                            
                            NERD: NER/NED application/ground-truth creation.
                            
                            OCR: OCR application/ground-truth creation.
                            
                            default: NERD.
  --image-url TEXT          An image retrieval link that enables neat to show
                            the scan images corresponding to the text tokens.
                            Example: https://content.staatsbibliothek-berlin.d
                            e/zefys/SNP26824620-18371109-0-1-0-0/left,top,widt
                            h,height/full/0/default.jpg
  --ner-rest-endpoint TEXT  REST endpoint of sbb_ner service. See
                            https://github.com/qurator-spk/sbb_ner for
                            details. Only applicable in case of NERD.
  --ned-rest-endpoint TEXT  REST endpoint of sbb_ned service. See
                            https://github.com/qurator-spk/sbb_ned for
                            details. Only applicable in case of NERD.
  --noproxy                 disable proxy. default: enabled.
  --scale-factor FLOAT      default: 1.0
  --ned-threshold FLOAT
  --ned-priority INTEGER
  --help                    Show this message and exit.
```
