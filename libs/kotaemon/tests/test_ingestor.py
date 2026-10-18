from pathlib import Path

from kotaemon.indices.ingests import DocumentIngestor
from kotaemon.indices.ingests.files import KH_DEFAULT_FILE_EXTRACTORS
from kotaemon.indices.splitters import TokenSplitter
from kotaemon.loaders import PandasExcelReader, PptxReader


def test_ingestor_include_src():
    dirpath = Path(__file__).parent
    ingestor = DocumentIngestor(
        pdf_mode="normal",
        text_splitter=TokenSplitter(chunk_size=200, chunk_overlap=10),
    )
    nodes = ingestor(dirpath / "resources" / "table.pdf")
    assert type(nodes) is list
    assert nodes[0].relationships


def test_xls_is_read_locally_by_pandas():
    """The old BIFF `.xls` format must not be routed to unstructured.

    unstructured opens `.xls` through pandas/xlrd and, on this platform, its
    converter additionally expects LibreOffice. Without xlrd the upload came back
    as failed ("Missing optional dependency 'xlrd'") and indexed nothing, so the
    file showed up in the list with an empty loader and every question about it
    answered with "no evidence found". Both excel formats share the local pandas
    reader now.
    """
    assert isinstance(KH_DEFAULT_FILE_EXTRACTORS[".xls"], PandasExcelReader)


def test_pptx_is_read_locally():
    """`.pptx` must not fall back to unstructured (libmagic + a first-use download).

    The same failure left `.docx` (§2.8) and `.xls` (§2.9) silently unindexed: the
    upload reported an error, the file stayed in the list, and questions about it
    answered "no evidence found".
    """
    assert isinstance(KH_DEFAULT_FILE_EXTRACTORS[".pptx"], PptxReader)
