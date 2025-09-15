from typing import Any

import msgspec
import numpy as np


class BaseStruct(msgspec.Struct):
    def to_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in self.__struct_fields__ if getattr(self, f, None) != msgspec.UNSET}


class CamelizedBaseStruct(BaseStruct, rename="camel"):
    """Camelized Base Struct"""


class Message(CamelizedBaseStruct):
    message: str


class SerializedEmbedding(msgspec.Struct, array_like=True, kw_only=True):
    """Msgspec-compatible wrapper for numpy arrays used in embeddings.

    Provides pack/unpack methods to serialize numpy arrays through msgspec
    """

    dtype: str
    shape: tuple[int, ...]
    data: memoryview

    @classmethod
    def pack(cls, arr: np.ndarray) -> "SerializedEmbedding":
        """Pack a numpy array into a serializable format.

        Args:
            arr: Numpy array to pack

        Returns:
            SerializedEmbedding instance
        """
        return cls(data=arr.data, dtype=str(arr.dtype), shape=arr.shape)

    def unpack(self) -> np.ndarray:
        """Unpack back to numpy array.

        Returns:
            Numpy array with original shape and dtype
        """
        return np.frombuffer(self.data, dtype=self.dtype).reshape(self.shape)
