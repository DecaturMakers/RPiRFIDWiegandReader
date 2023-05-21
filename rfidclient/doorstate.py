from struct import pack, unpack, calcsize
from multiprocessing.shared_memory import SharedMemory
from time import time


class DoorState:

    STRUCT_FMT: str = 'diddii'

    STRUCT_SIZE: int = calcsize(STRUCT_FMT)

    def __init__(self):
        self._process_start_time: float = time()
        self._door_is_open: int = -1
        self._door_open_time: float = -1
        self._door_close_time: float = -1
        self._num_authorized: int = 0
        self._num_unauthorized: int = 0

    @property
    def process_uptime_seconds(self) -> float:
        return time() - self._process_start_time

    @property
    def door_is_open(self) -> int:
        return self._door_is_open

    @property
    def seconds_since_opened(self) -> float:
        if self._door_open_time == -1:
            return -1
        return time() - self._door_open_time

    @property
    def seconds_since_closed(self) -> float:
        if self._door_close_time == -1:
            return -1
        return time() - self._door_close_time

    @property
    def unauthorized_scans(self) -> int:
        return self._num_unauthorized

    @property
    def authorized_scans(self) -> int:
        return self._num_authorized

    def set_door_open(self, shm: SharedMemory):
        self._door_is_open = 1
        self._door_open_time = time()
        self.write_to_shm(shm)

    def set_door_closed(self, shm: SharedMemory):
        self._door_is_open = 0
        self._door_close_time = time()
        self.write_to_shm(shm)

    def set_scan_authorized(self, shm: SharedMemory):
        self._num_authorized += 1
        self.write_to_shm(shm)

    def set_scan_unauthorized(self, shm: SharedMemory):
        self._num_unauthorized += 1
        self.write_to_shm(shm)

    @property
    def _value(self) -> list:
        return [
            self._process_start_time,
            self._door_is_open,
            self._door_open_time,
            self._door_close_time,
            self._num_authorized,
            self._num_unauthorized
        ]

    def __repr__(self) -> str:
        return f'<DoorState(' \
               f'process_start_time={self._process_start_time}, ' \
               f'door_is_open={self._door_is_open}, ' \
               f'door_open_time={self._door_open_time}, ' \
               f'door_close_time={self._door_close_time}, ' \
               f'num_authorized={self._num_authorized}, ' \
               f'num_unauthorized={self._num_unauthorized})>'

    def write_to_shm(self, shm: SharedMemory):
        shm.buf[:] = pack(self.STRUCT_FMT, *self._value)

    @classmethod
    def from_shm_buffer(cls, shm: SharedMemory) -> 'DoorState':
        vals = unpack(DoorState.STRUCT_FMT, shm.buf)
        c = DoorState()
        c._process_start_time = vals[0]
        c._door_is_open = vals[1]
        c._door_open_time = vals[2]
        c._door_close_time = vals[3]
        c._num_authorized = vals[4]
        c._num_unauthorized = vals[5]
        return c
