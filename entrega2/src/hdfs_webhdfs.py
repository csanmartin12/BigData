"""Cliente WebHDFS mínimo (REST sobre HTTP) para subir y listar archivos en HDFS.

Se usa WebHDFS y no el cliente RPC de Hadoop porque las subidas ocurren en los workers de
Python de Spark, que no tienen acceso a la JVM. ``CREATE`` es de dos pasos: el namenode
responde 307 con la URL del datanode (``http://localhost:9864/...``, ver
infra/docker-compose.yml) y el contenido se envía a esa URL.
"""
from __future__ import annotations

import time

import requests

from config import HDFS_USUARIO, WEBHDFS_URL


class WebHDFS:
    def __init__(self, url: str = WEBHDFS_URL, usuario: str = HDFS_USUARIO, reintentos: int = 3):
        self.url = url.rstrip("/")
        self.usuario = usuario
        self.reintentos = reintentos
        self.s = requests.Session()

    def _params(self, op: str, **extra) -> dict:
        return {"op": op, "user.name": self.usuario, **extra}

    def _pedir(self, metodo: str, ruta: str, op: str, **extra) -> requests.Response:
        r = self.s.request(metodo, self.url + ruta, params=self._params(op, **extra), allow_redirects=False)
        if r.status_code >= 400:
            raise RuntimeError(f"WebHDFS {op} {ruta}: HTTP {r.status_code} {r.text[:300]}")
        return r

    def crear(self, ruta: str, datos: bytes, sobrescribir: bool = True) -> None:
        """Sube ``datos`` a ``ruta`` (crea los directorios padre)."""
        for intento in range(1, self.reintentos + 1):
            try:
                r = self._pedir("PUT", ruta, "CREATE", overwrite=str(sobrescribir).lower())
                if r.status_code != 307:
                    raise RuntimeError(f"CREATE {ruta}: se esperaba 307, llegó {r.status_code}")
                r2 = self.s.put(r.headers["Location"], data=datos)
                if r2.status_code != 201:
                    raise RuntimeError(f"CREATE {ruta} (datanode): HTTP {r2.status_code} {r2.text[:300]}")
                return
            except (requests.ConnectionError, RuntimeError):
                if intento == self.reintentos:
                    raise
                time.sleep(2 ** intento)

    def estado(self, ruta: str) -> dict | None:
        r = self.s.get(self.url + ruta, params=self._params("GETFILESTATUS"))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["FileStatus"]

    def listar(self, ruta: str) -> list[dict]:
        r = self._pedir("GET", ruta, "LISTSTATUS")
        return r.json()["FileStatuses"]["FileStatus"]

    def listar_recursivo(self, ruta: str) -> list[tuple[str, dict]]:
        """``(ruta_completa, FileStatus)`` de todos los archivos bajo ``ruta``."""
        if self.estado(ruta) is None:
            return []
        salida, pendientes = [], [ruta.rstrip("/")]
        while pendientes:
            d = pendientes.pop()
            for st in self.listar(d):
                hijo = f"{d}/{st['pathSuffix']}"
                if st["type"] == "DIRECTORY":
                    pendientes.append(hijo)
                else:
                    salida.append((hijo, st))
        return sorted(salida)

    def resumen(self, ruta: str) -> dict | None:
        r = self.s.get(self.url + ruta, params=self._params("GETCONTENTSUMMARY"))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["ContentSummary"]

    def borrar(self, ruta: str, recursivo: bool = True) -> bool:
        r = self._pedir("DELETE", ruta, "DELETE", recursive=str(recursivo).lower())
        return r.json().get("boolean", False)
