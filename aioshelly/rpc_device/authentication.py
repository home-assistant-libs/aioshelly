"""Authentication code for Shelly RPC devices."""
import hashlib
import time
from dataclasses import dataclass
from typing import Any


def hex_hash(message: str) -> str:
    """Get hex representation of sha256 hash of string."""
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


HA2 = hex_hash("dummy_method:dummy_uri")


@dataclass
class AuthData:
    """RPC Auth data class."""

    realm: str
    username: str
    password: str

    def __post_init__(self) -> None:
        """Call after initialization."""
        self.ha1 = hex_hash(f"{self.username}:{self.realm}:{self.password}")

    def get_auth(self, nonce: int | None = None, n_c: int = 1) -> dict[str, Any]:
        """Get auth for RPC calls."""
        cnonce = int(time.time())
        if nonce is None:
            nonce = cnonce - 1800

        # https://shelly-api-docs.shelly.cloud/gen2/Overview/CommonDeviceTraits/#authentication-over-websocket
        hashed = hex_hash(f"{self.ha1}:{nonce}:{n_c}:{cnonce}:auth:{HA2}")

        return {
            "realm": self.realm,
            "username": self.username,
            "nonce": nonce,
            "cnonce": cnonce,
            "response": hashed,
            "algorithm": "SHA-256",
        }


# def get_gen2_auth(
#     auth: AuthData, nonce: int | None = None, n_c: int = 1
# ) -> dict[str, Any]:
#     """Get auth for RPC calls."""
#     cnonce = int(time.time())
#     if nonce is None:
#         nonce = cnonce - 1800

#     # https://shelly-api-docs.shelly.cloud/gen2/Overview/CommonDeviceTraits/#authentication-over-websocket
#     hashed = hex_hash(f"{auth.ha1}:{nonce}:{n_c}:{cnonce}:auth:{HA2}")

#     return {
#         "realm": auth.realm,
#         "username": auth.username,
#         "nonce": nonce,
#         "cnonce": cnonce,
#         "response": hashed,
#         "algorithm": "SHA-256",
#     }
