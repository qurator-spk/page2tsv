from io import open
from json import load
from setuptools import find_packages, setup

with open('requirements.txt') as fp:
    install_requires = fp.read()
with open('ocrd-tool.json') as fj:
    version = load(fj)['version']

setup(
    name="qurator_tsvtools",
    version=version,
    author="Kai Labusch",
    author_email="qurator@sbb.spk-berlin.de",
    description="Working with QURATOR TSV, especially for neat",
    long_description=open("README.md", "r", encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    keywords='qurator',
    license='Apache License 2.0',
    url="https://github.com/qurator-spk/neath",
    packages=find_packages(exclude=["*.tests", "*.tests.*",
                                    "tests.*", "tests"]),
    install_requires=install_requires,
    namespace_packages=['qurator'],
    package_data={
        '': ['*.json']
    },
    entry_points={
      'console_scripts': [
        "extract-doc-links=qurator.tsvtools.cli:extract_document_links",
        "annotate-tsv=qurator.tsvtools.cli:annotate_tsv",
        "ocrd-neat-export=qurator.tsvtools.ocrd_cli:export_cli",
        "ocrd-neat-import=qurator.tsvtools.ocrd_cli:import_cli",
        "page2tsv=qurator.tsvtools.cli:page2tsv_cli",
        "tsv2page=qurator.tsvtools.cli:tsv2page_cli",
        "make-page2tsv-commands=qurator.tsvtools.cli:make_page2tsv_commands"
      ]
    },
    python_requires='>=3.6.0',
    tests_require=['pytest'],
    classifiers=[
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 3',
          'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ],
)
