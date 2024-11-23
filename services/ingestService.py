from typing import BinaryIO, Sequence
from zipfile import ZipFile

def read_files_from_zip(zipArchive: BinaryIO , file_types: list[str] = []) -> list[tuple[str,bytes]]:
    output = []
    with ZipFile(zipArchive, 'r') as zip_handle:
        for file in zip_handle.filelist:
            if file_types and check_filetype(file.filename) in file_types:
                with zip_handle.open(file, 'r') as file_handle:
                    output.append((file.filename, file_handle.read()))
    return output

def check_filetype(filename: str):
    return filename.split('.')[-1]
