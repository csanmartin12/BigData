"""Fracción de cada archivo que está en la caché de páginas de Linux (``mincore``).

Sirve para documentar qué tan "fría" está la caché antes de una medición. Solo mide la caché
de la VM de WSL2; la caché de archivos de Windows (detrás de 9P) no es visible desde aquí.
No lee el contenido: ``mmap`` + ``mincore`` no traen páginas a memoria.

Uso:
    python src/cache_residencia.py /mnt/c/Bases/*.zip
"""
from __future__ import annotations

import ctypes
import mmap
import os
import sys

_libc = ctypes.CDLL("libc.so.6", use_errno=True)
_libc.mmap.restype = ctypes.c_void_p
_libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
_libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
_libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
_MAP_FAILED = ctypes.c_void_p(-1).value


def residencia(ruta: str) -> tuple[int, int]:
    """``(bytes_en_cache, bytes_totales)``."""
    tam = os.path.getsize(ruta)
    if tam == 0:
        return 0, 0
    pagina = mmap.PAGESIZE
    n = (tam + pagina - 1) // pagina
    fd = os.open(ruta, os.O_RDONLY)
    try:
        addr = _libc.mmap(None, tam, mmap.PROT_READ, mmap.MAP_SHARED, fd, 0)
        if addr in (None, _MAP_FAILED):
            raise OSError(ctypes.get_errno(), f"mmap falló: {ruta}")
        try:
            vec = (ctypes.c_ubyte * n)()
            if _libc.mincore(addr, tam, vec) != 0:
                raise OSError(ctypes.get_errno(), f"mincore falló: {ruta}")
            residentes = sum(b & 1 for b in vec)
        finally:
            _libc.munmap(addr, tam)
    finally:
        os.close(fd)
    return min(residentes * pagina, tam), tam


def main() -> None:
    total_c = total = 0
    for ruta in sys.argv[1:]:
        c, t = residencia(ruta)
        total_c, total = total_c + c, total + t
        print(f"{os.path.basename(ruta)}: {c / 1e6:9.1f} / {t / 1e6:9.1f} MB en caché ({100 * c / t:5.1f} %)")
    if total:
        print(f"TOTAL: {total_c / 1e6:.1f} / {total / 1e6:.1f} MB ({100 * total_c / total:.1f} %)")


if __name__ == "__main__":
    main()
