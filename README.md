# TSV - Processing Tools

Create .tsv files that can be viewed and edited with [neat](https://github.com/qurator-spk/neat).

## Installation:

Clone this project and the [SBB-utils](https://github.com/qurator-spk/sbb_utils).

Setup virtual environment:
```
virtualenv --python=python3.6 venv
```

Activate virtual environment:
```
source venv/bin/activate
```

Upgrade pip:
```
pip install -U pip
```

Install package together with its dependencies in development mode:
```
pip install -e sbb_utils
pip install -e page2tsv
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
page2tsv [OPTIONS] PAGE_XML_FILE TSV_OUT_FILE

Options:
  --purpose [NERD|OCR]      Purpose of output tsv file.
                            
                            NERD: NER/NED application/ground-truth creation.
                            
                            OCR: OCR application/ground-truth creation.
                            
                            default: NERD.
  --image-url TEXT
  --ner-rest-endpoint TEXT  REST endpoint of sbb_ner service. See
                            https://github.com/qurator-spk/sbb_ner for
                            details. Only applicable in case of NERD.
  --ned-rest-endpoint TEXT  REST endpoint of sbb_ned service. See
                            https://github.com/qurator-spk/sbb_ned for
                            details. Only applicable in case of NERD.
  --noproxy                 disable proxy. default: enabled.
  --scale-factor FLOAT      default: 1.0
  --ned-threshold FLOAT
  --min-confidence FLOAT
  --max-confidence FLOAT
  --ned-priority INTEGER
  --help                    Show this message and exit.

```