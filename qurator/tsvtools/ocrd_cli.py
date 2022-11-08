import click
from ocrd.decorators import ocrd_cli_options, ocrd_cli_wrap_processor

from .ocrd_processors import OcrdNeatExportProcessor, OcrdNeatImportProcessor

@click.command()
@ocrd_cli_options
def export_cli(*args, **kwargs):
    return ocrd_cli_wrap_processor(OcrdNeatExportProcessor, *args, **kwargs)

@click.command()
@ocrd_cli_options
def import_cli(*args, **kwargs):
    return ocrd_cli_wrap_processor(OcrdNeatImportProcessor, *args, **kwargs)
