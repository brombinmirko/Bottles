# health.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
from bottles.backend.utils import yaml
import shutil
import contextlib

from bottles.backend.logger import Logger
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.utils.generic import is_glibc_min_available
from bottles.backend.utils.file import FileUtils
from bottles.backend.params import APP_VERSION

logging = Logger()


class HealthChecker:
    x11: bool = False
    x11_port: str = ""
    wayland: bool = False
    xwayland: bool = False
    desktop: str = ""
    gpus: dict = {}
    cabextract: bool = False
    p7zip: bool = False
    patool: bool = False
    icoextract: bool = False
    pefile: bool = False
    orjson: bool = False
    markdown: bool = False
    xdpyinfo: bool = False
    ImageMagick: bool = False
    FVS: bool = False
    glibc_min: str = ""
    kernel: str = ""
    kernel_version: str = ""
    bottles_envs: dict = {}

    def __init__(self):
        self.file_utils = FileUtils()
        self.x11 = self.check_x11()
        self.wayland = self.check_wayland()
        self.xwayland = self.check_xwayland()
        self.desktop = self.check_desktop()
        self.gpus = self.check_gpus()
        self.glibc_min = is_glibc_min_available()
        self.bottles_envs = self.get_bottles_envs()
        self.check_system_info()
        self.disk = self.get_disk_data()
        self.ram = {
            "MemTotal": "n/a",
            "MemAvailable": "n/a"
        }
        self.get_ram_data()

        self.cabextract = self.check_cabextract()
        self.p7zip = self.check_p7zip()
        self.patool = self.check_patool()
        self.icoextract = self.check_icoextract()
        self.pefile = self.check_pefile()
        self.orjson = self.check_orjson()
        self.markdown = self.check_markdown()
        self.xdpyinfo = self.check_xdpyinfo()
        self.ImageMagick = self.check_ImageMagick()
        self.FVS = self.check_FVS()

    @staticmethod
    def check_gpus():
        return GPUUtils().get_gpu()

    def check_x11(self):
        port = DisplayUtils.get_x_display()
        if port:
            self.x11_port = port
            return True
        return False

    @staticmethod
    def check_wayland():
        return "WAYLAND_DISPLAY" in os.environ

    def check_xwayland(self):
        return self.x11 and self.wayland

    def check_desktop(self):
        return os.environ.get("XDG_CURRENT_DESKTOP")

    @staticmethod
    # TODO: additional cleanup: don't have individual `check_*` methods, just one like this,
    # and iterate over them for the results.
    def check_executable(executable):
        return bool(shutil.which(executable))

    @staticmethod
    def check_cabextract():
        return check_executable("cabextract")

    @staticmethod
    def check_p7zip():
        return check_executable("7z")

    @staticmethod
    def check_patool():
        return check_executable("patool")

    @staticmethod
    def check_xdpyinfo():
        return check_executable("xdpyinfo")

    @staticmethod
    def check_ImageMagick():
        return check_executable("identify")

    @staticmethod
    def check_module(module):
        try:
            __import__(module)
        except ModuleNotFoundError:
            return False
        else:
            return True

    @staticmethod
    def check_icoextract():
        return check_module("icoextract")

    @staticmethod
    def check_pefile():
        return check_module("pefile")

    @staticmethod
    def check_markdown():
        return check_module("markdown")

    @staticmethod
    def check_orjson():
        return check_module("orjson")

    @staticmethod
    def check_FVS():
        return check_module("fvs")

    @staticmethod
    def get_bottles_envs():
        look = [
            "TESTING_REPOS",
            "LOCAL_INSTALLERS",
            "LOCAL_COMPONENTS",
            "LOCAL_DEPENDENCIES"
        ]

        for _look in look:
            if _look in os.environ:
                return {
                    _look: os.environ[_look]
                }

    def check_system_info(self):
        self.kernel = os.uname().sysname
        self.kernel_version = os.uname().release

    def get_disk_data(self):
        disk_data = self.file_utils.get_disk_size(False)
        return {
            "Total": disk_data["total"],
            "Free": disk_data["free"]
        }

    def get_ram_data(self):
        with contextlib.suppress(FileNotFoundError, PermissionError):
            with open('/proc/meminfo') as file:
                for line in file:
                    if 'MemTotal' in line:
                        self.ram["MemTotal"] = self.file_utils.get_human_size_legacy(float(line.split()[1])*1024.0)
                    if 'MemAvailable' in line:
                        self.ram["MemAvailable"] = self.file_utils.get_human_size_legacy(float(line.split()[1])*1024.0)

    def get_results(self, plain: bool = False):
        results = {
            "Official Package": "FLATPAK_ID" in os.environ,
            "Version": APP_VERSION,
            "DE/WM": self.desktop,
            "Display": {
                "X.org": self.x11,
                "X.org (port)": self.x11_port,
                "Wayland": self.wayland,
            },
            "Graphics": self.gpus,
            "Kernel": {
                "Type": self.kernel,
                "Version": self.kernel_version
            },
            "Disk": self.disk,
            "RAM": self.ram,
            "Bottles_envs": self.bottles_envs
        }

        if "FLATPAK_ID" not in os.environ:
            results["Tools and Libraries"] = {
                "cabextract": self.cabextract,
                "p7zip": self.p7zip,
                "patool": self.patool,
                "glibc_min": self.glibc_min,
                "icoextract": self.icoextract,
                "pefile": self.pefile,
                "orjson": self.orjson,
                "markdown": self.markdown,
                "ImageMagick": self.ImageMagick,
                "FVS": self.FVS,
                "xdpyinfo": self.xdpyinfo
            }

        if plain:
            _yaml = yaml.dump(results, sort_keys=False, indent=4)
            _yaml = _yaml.replace("&id", "&amp;id")
            return _yaml

        return results

    def has_core_deps(self):
        result = True

        for k, v in self.get_results()["Tools and Libraries"].items():
            if v is False:
                logging.error(f"Core dependency {k} not found, Bottles can't be started.")
                result = False

        return result
