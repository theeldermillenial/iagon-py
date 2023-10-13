"""Low level functionality for Iagon."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

import requests
from pydantic import BaseModel
from pydantic import Field

from pycardano import Address  # type: ignore [attr-defined]
from pycardano import HDWallet  # type: ignore [attr-defined]
from pycardano import PaymentExtendedSigningKey  # type: ignore [attr-defined]
from pycardano import StakeExtendedSigningKey  # type: ignore [attr-defined]
from pycardano import sign  # type: ignore [attr-defined]


class BadRequestError(Exception):
    """Error when status code is 400, bad request error."""


class NotAuthenticatedError(Exception):
    """Error when status code is 401, not authenticated error."""


class NotFoundError(Exception):
    """Error when status code is 404, not found error."""


class DirectoryExistsError(Exception):
    """Error when status code is 409, not found error."""


class InternalServerError(Exception):
    """Error when status code is 500, not found error."""


class Success(BaseModel):
    """Base class to parse a successful call."""

    success: bool
    message: str | None = None


class FileId(BaseModel):
    """The unique id of a file."""

    file_id: str = Field(..., alias="id")


class CreateFileSuccess(Success):
    """Successful file creation reponse."""

    data: FileId


class FileInfo(BaseModel):
    """File or chunk information."""

    file_id: str = Field(..., alias="_id")
    wallet_id: str
    parent_directory_id: str | None = None
    file_hash: str | None = Field(None, alias="hash")
    name: str
    ext: str | None = None
    file_size_byte_native: int
    file_size_byte_encrypted: int | None = None
    encrypted_symmetric_key: str | None = None
    resource_provider_id: str | None = None
    created_at: datetime
    updated_at: datetime
    v: int = Field(..., alias="__v")


class DirectoryInfo(BaseModel):
    """Directory information."""

    dir_id: str = Field(..., alias="_id")
    directory_name: str
    parent_directory_id: str | None
    wallet_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    v: int = Field(..., alias="__v")


class ListResponse(BaseModel):
    """Directory list information. Contains both files and folders."""

    files: list[FileInfo]
    directories: list[DirectoryInfo]


class CreateDirectorySuccess(Success):
    """Successful directory creation response."""

    data: DirectoryInfo


class ListSuccess(Success):
    """Successful list directory response."""

    data: ListResponse


class IagonAdapter:
    """Low level Python interface to Python."""

    url = "https://gw.v109.iagon.com/api/v2"
    json_header: dict
    auth_header: dict

    def __init__(self, token: str | None = None) -> None:
        """Create an Iagon object with an active auth token.

        Args:
            token: Active auth token. Defaults to None.
        """
        self.token = token

        self.auth_header = {"Authorization": f"Bearer {token}"}
        self.json_header = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @classmethod
    def nonce(cls, address: str) -> str:
        """Request a nonce for authorization.

        Args:
            address: A bech32 address.

        Returns:
            A nonce.
        """
        response = requests.post(
            cls.url + "/public/nonce",
            data={"publicAddress": address},
            timeout=10,
        )

        if response.status_code != requests.codes["ok"]:
            msg = f"Error: {response.json()['message']}"
            raise BadRequestError(msg)

        return response.json()["nonce"]

    @classmethod
    def verify(cls, address: str, signature: str, key: str) -> str:
        """Verify CIP8 signed nonce and request auth token.

        Iagon generates an auth token based on verification of a signed nonce using
        the CIP8 message signing protocol. It returns an auth token that is then used
        in the header.

        More information on CIP8 can be found in the documentation.

        https://cips.cardano.org/cips/cip8/

        Args:
            address: A bech32 address.
            signature: A CIP8 signature.
            key: A CIP8 key.

        Returns:
            An auth token.
        """
        response = requests.post(
            cls.url + "/public/verify",
            data={"publicAddress": address, "signature": signature, "key": key},
            timeout=10,
        )
        if response.status_code != requests.codes["ok"]:
            msg = f"Error: {response.json()['message']}"
            raise BadRequestError(msg)

        return response.json()["session"]

    @classmethod
    @contextmanager
    def session(
        cls,
        seed: str,
    ) -> Generator[IagonAdapter, None, None]:
        """Create an Iagon session. Use in a context block.

        This is a convenience method to request an auth token from Iagon and initialize
        an IagonAdapter object for interacting with Iagon.

        This uses a seed phrase for a wallet to sign a nonce with CIP8 using the first
        address in the wallet. The session is valid within the context block, and then
        is properly cleaned up upon exit.

        Todo:
            See TODOs in code. A number of Iagon endpoints do not function correctly.
            Currently cannot verify or disconnect properly.

        Args:
            seed: A seed phrase for a wallet.

        Yields:
            An IagonAdapter with a live session token.
        """
        # Generate the wallet and first address
        hdwallet = HDWallet.from_mnemonic(seed)
        hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
        hdwallet_stake = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
        pay_key = PaymentExtendedSigningKey.from_hdwallet(hdwallet_spend)
        stake_key = StakeExtendedSigningKey.from_hdwallet(hdwallet_stake)
        address = Address(
            payment_part=pay_key.to_verification_key().hash(),
            staking_part=stake_key.to_verification_key().hash(),
        ).to_cbor_hex()[4:]

        # Sign the nonce with CIP8
        nonce = cls.nonce(address)
        signed_nonce = sign(
            message=nonce,
            signing_key=stake_key,
            attach_cose_key=True,
        )

        # Request an auth token
        token = cls.verify(
            address=address,
            signature=signed_nonce["signature"],
            key=signed_nonce["key"],
        )

        # Create the Iagon session adapter
        adapter = IagonAdapter(token)

        # TODO: Right now this endpoint times out. Uncomment when fixed.

        yield adapter

        # TODO: Right now this endpoint times out. Uncomment when fixed.

    def check_auth(self) -> bool:
        """Check if session is live. Currently does not work."""
        raw_response = requests.post(
            self.url + "/public/checkauth",
            headers=self.auth_header,
            timeout=10,
        )
        response = self.handle_response(raw_response)

        return Success.model_validate(response).success

    def disconnect(self) -> None:
        """Request auth token expiration. Currently does not work."""
        raw_response = requests.post(
            self.url + "/public/disconnect",
            headers=self.auth_header,
            timeout=10,
        )
        self.handle_response(raw_response)

    def handle_response(self, response: requests.Response) -> dict:
        """Response handler. Gateway for more informative error messaging."""
        if response.status_code == requests.codes["bad"]:
            raise BadRequestError(response.json()["message"])
        elif response.status_code == requests.codes["unauthorized"]:  # noqa: RET506
            raise NotAuthenticatedError(response.json()["message"])
        elif response.status_code == requests.codes["not_found"]:
            raise NotFoundError(response.json()["message"])
        elif response.status_code == requests.codes["conflict"]:
            raise DirectoryExistsError(response.text)
        elif response.status_code != requests.codes["ok"]:
            msg = f"Error {response.status_code}: {response.text}"
            raise BadRequestError(msg)

        return response.json()

    def create_directory(
        self,
        name: str,
        parent_id: str | None = None,
    ) -> DirectoryInfo:
        """Create a new directory.

        This creates a new directory, and if the `parent` is specified, makes a new
        subdirectory in `parent`.

        Args:
            name: Name of the new directory. Must be unique.
            parent_id: Id of the parent folder, if creating a subdirectory.
                Defaults to None.

        Returns:
            Information about the newly created directory.
        """
        raw_response = requests.post(
            self.url + "/storage/directory/create",
            data=json.dumps({"directory_name": name, "parent_directory_id": parent_id}),
            headers=self.json_header,
            timeout=10,
        )
        response = self.handle_response(raw_response)
        return CreateDirectorySuccess.model_validate(response).data

    def upload(  # noqa: PLR0913
        self,
        file_name: str,
        file: bytes,
        private: bool = True,
        password: str = "default",  # noqa: S107
        dir_id: str | None = None,
        region_id: str | None = None,
    ) -> FileId:
        """Upload a file.

        Upload a new file to Iagon. Can be public or private.

        Args:
            file_name: Name of file to upload.
            file: Byte stream of data to upload.
            private: If true, file is only visible to the wallet address.
                Defaults to True.
            password: Password for encrypting the file. This must be a valid string.
                Defaults to "default".
            dir_id: The directory id to place the file. If None, places in the
                root folder. Defaults to None.
            region_id: The region id for routing file upload. Defaults to None.

        Returns:
            The Id of the newly created file.
        """
        # Configure upload parameters
        visibility = "private" if private else "public"
        data = {"filename": file_name, "password": password, "visibility": visibility}
        if dir_id is not None:
            data.update(directoryId=dir_id)
        if region_id is not None:
            data.update(regionId=region_id)
        files = {"file": (file_name, file)}

        # Send the file
        raw_response = requests.post(
            self.url + "/storage/upload/",
            data=data,
            files=files,
            headers=self.auth_header,
            timeout=10,
        )

        # Validate the response
        response = self.handle_response(raw_response)

        return CreateFileSuccess.model_validate(response).data

    def download(self, file_id: str, password: str = "default") -> bytes:  # noqa: S107
        """Download a file.

        This downloads a file using the file id. It is critical that the `password`
        matches the `password` used to upload the file, since it is used to decrypt the
        file.

        Args:
            file_id: The id of the file to download.
            password: The password to decrypt the file. Must match the upload password.
                Defaults to "default".

        Returns:
            The raw bytes of the data.
        """
        raw_response = requests.post(
            self.url + "/storage/download/",
            data={"id": file_id, "password": password},
            headers=self.auth_header,
            timeout=10,
        )
        return raw_response.content

    def lsdir(
        self,
        path: list[str] | None = None,
        private: bool = False,
    ) -> ListSuccess:
        """List of files and folders int he directory.

        Args:
            path: A list of folder ids defining the path to the folder. If None, lists
                files and folders in the root directory. Defaults to None.
            private: If True, displays private files. Defaults to False.

        Returns:
            An object containing files and folders in the directory.
        """
        permission = "private" if private else "public"

        if path is None:
            raw_response = requests.get(
                self.url + f"/storage/list/{permission}",
                headers=self.json_header,
                timeout=10,
            )
        else:
            path_list = "/".join(path)
            raw_response = requests.get(
                self.url + f"/storage/directory/{path_list}/list",
                headers=self.json_header,
                timeout=10,
            )
        response = self.handle_response(raw_response)
        return ListSuccess.model_validate(response)

    def delete_directory(self, dir_id: str) -> Success:
        """Delete a directory.

        This deletes a directory and the contents of the directory.

        Args:
            dir_id: The directory id.

        Returns:
            A success message, or an error if deletion was unsuccessful.
        """
        raw_response = requests.delete(
            self.url + f"/storage/directory/{dir_id}",
            headers=self.json_header,
            timeout=10,
        )
        response = self.handle_response(raw_response)
        return Success.model_validate(response)
