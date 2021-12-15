from io import open
from setuptools import find_packages, setup

with open('requirements.txt') as fp:
    install_requires = fp.read()

setup(
    name="tsvtools",
    version="0.0.1",
    author="",
    author_email="qurator@sbb.spk-berlin.de",
    description="neath",
    long_description=open("README.md", "r", encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    keywords='qurator',
    license='Apache License 2.0',
    url="https://github.com/qurator-spk/neath",
    packages=find_packages(exclude=["*.tests", "*.tests.*",
                                    "tests.*", "tests"]),
    install_requires=install_requires,
    entry_points={
      'console_scripts': [
        "extract-doc-links=tsvtools.cli:extract_document_links",
        "annotate-tsv=tsvtools.cli:annotate_tsv",
        "page2tsv=tsvtools.cli:page2tsv",
        "tsv2page=tsvtools.cli:tsv2page",
        "make-page2tsv-commands=tsvtools.cli:make_page2tsv_commands"
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
