import os

import pytest
from dotenv import load_dotenv
from iagon import IagonAdapter
from iagon.base import ListSuccess

load_dotenv()


@pytest.fixture()
def folder_name():
    return "test_folder"


@pytest.fixture()
def subfolder_name():
    return "test_subfolder"


@pytest.fixture()
def file_name():
    return "test.txt", b"hello world!"


@pytest.fixture()
def seed():
    return os.environ["SEED"]


@pytest.mark.order(1)
@pytest.mark.asyncio()
async def test_session(seed):
    with IagonAdapter.session(seed):
        pass


@pytest.mark.order(2)
@pytest.mark.asyncio()
async def test_folders(seed, folder_name, subfolder_name):
    with IagonAdapter.session(seed) as adapter:
        # Create base folder
        folder = adapter.create_directory(folder_name)

        lsdir: ListSuccess = adapter.lsdir(private=True)

        assert folder_name in [d.directory_name for d in lsdir.data.directories]

        # Create subfolder
        subfolder = adapter.create_directory(
            name=subfolder_name, parent_id=folder.dir_id
        )

        lsdir = adapter.lsdir(path=[folder.dir_id], private=True)

        assert subfolder_name in [d.directory_name for d in lsdir.data.directories]

        # Cleanup the subfolder
        adapter.delete_directory(subfolder.dir_id)

        lsdir = adapter.lsdir(path=[folder.dir_id], private=True)

        assert subfolder_name not in [d.directory_name for d in lsdir.data.directories]

        # Cleanup the base folder
        adapter.delete_directory(folder.dir_id)

        lsdir = adapter.lsdir(private=True)

        assert folder_name not in [d.directory_name for d in lsdir.data.directories]


@pytest.mark.order(3)
@pytest.mark.asyncio()
async def test_file(seed, folder_name, file_name):
    with IagonAdapter.session(seed) as adapter:
        # Create base folder
        folder = adapter.create_directory(folder_name)

        lsdir: ListSuccess = adapter.lsdir(private=True)

        assert folder_name in [d.directory_name for d in lsdir.data.directories]

        name, data = file_name

        # Upload the file
        upload_file = adapter.upload(
            file=data,
            file_name=name,
            dir_id=folder.dir_id,
        )

        lsdir: ListSuccess = adapter.lsdir(path=[folder.dir_id], private=True)

        assert upload_file.file_id in [d.file_id for d in lsdir.data.files]

        # Download the file
        download_file = adapter.download(upload_file.file_id)

        assert download_file == data

        # Cleanup the base folder
        adapter.delete_directory(folder.dir_id)

        lsdir = adapter.lsdir(private=True)

        assert folder_name not in [d.directory_name for d in lsdir.data.directories]
