# bottle_details.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import webbrowser
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, Adw

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.utils.common import open_doc_url

from bottles.backend.runner import Runner
from bottles.backend.managers.backup import BackupManager
from bottles.backend.utils.terminal import TerminalUtils
from bottles.backend.utils.manager import ManagerUtils

from bottles.widgets.program import ProgramEntry
from bottles.widgets.executable import ExecButton

from bottles.dialogs.runargs import RunArgsDialog
from bottles.dialogs.generic import MessageDialog
from bottles.dialogs.duplicate import DuplicateDialog

from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.winecfg import WineCfg
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.taskmgr import Taskmgr
from bottles.backend.wine.control import Control
from bottles.backend.wine.regedit import Regedit
from bottles.backend.wine.explorer import Explorer
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.wineserver import WineServer


@Gtk.Template(resource_path='/com/usebottles/bottles/details-bottle.ui')
class BottleView(Adw.PreferencesPage):
    __gtype_name__ = 'DetailsBottle'

    # region Widgets
    label_runner = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_arch = Gtk.Template.Child()
    btn_execute = Gtk.Template.Child()
    btn_run_args = Gtk.Template.Child()
    row_winecfg = Gtk.Template.Child()
    row_debug = Gtk.Template.Child()
    row_browse = Gtk.Template.Child()
    row_cmd = Gtk.Template.Child()
    row_taskmanager = Gtk.Template.Child()
    row_controlpanel = Gtk.Template.Child()
    row_uninstaller = Gtk.Template.Child()
    row_regedit = Gtk.Template.Child()
    btn_shutdown = Gtk.Template.Child()
    btn_reboot = Gtk.Template.Child()
    btn_killall = Gtk.Template.Child()
    btn_backup_config = Gtk.Template.Child()
    btn_backup_full = Gtk.Template.Child()
    btn_duplicate = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_flatpak_doc = Gtk.Template.Child()
    box_history = Gtk.Template.Child()
    check_terminal = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    group_programs = Gtk.Template.Child()
    list_programs = Gtk.Template.Child()
    extra_separator = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    row_no_programs = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.btn_execute.connect("clicked", self.run_executable)
        self.btn_run_args.connect("clicked", self.__run_executable_with_args)
        self.row_winecfg.connect("activated", self.run_winecfg)
        self.row_debug.connect("activated", self.run_debug)
        self.row_browse.connect("activated", self.run_browse)
        self.row_cmd.connect("activated", self.run_cmd)
        self.row_taskmanager.connect("activated", self.run_taskmanager)
        self.row_controlpanel.connect("activated", self.run_controlpanel)
        self.row_uninstaller.connect("activated", self.run_uninstaller)
        self.row_regedit.connect("activated", self.run_regedit)
        self.btn_delete.connect("clicked", self.__confirm_delete)
        self.btn_shutdown.connect("clicked", self.wineboot, 2)
        self.btn_reboot.connect("clicked", self.wineboot, 1)
        self.btn_killall.connect("clicked", self.wineboot, 0)
        self.btn_backup_config.connect("clicked", self.__backup, "config")
        self.btn_backup_full.connect("clicked", self.__backup, "full")
        self.btn_duplicate.connect("clicked", self.__duplicate)
        self.btn_flatpak_doc.connect(
            "clicked",
            open_doc_url,
            "flatpak/black-screen-or-silent-crash"
        )

        if "FLATPAK_ID" in os.environ:
            '''
            If Flatpak, show the btn_flatpak_doc widget to reach
            the documentation on how to expose directories
            '''
            self.btn_flatpak_doc.set_visible(True)

        self.__update_latest_executables()

    def set_config(self, config):
        self.config = config
        self.__update_by_env()

        # set update_date
        update_date = datetime.strptime(self.config.get("Update_Date"), "%Y-%m-%d %H:%M:%S.%f")
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")
        self.label_name.set_tooltip_text(_("Updated: %s" % update_date))

        # set arch
        self.label_arch.set_text(self.config.get("Arch", "n/a").capitalize())

        # set name and runner
        self.label_name.set_text(self.config.get("Name"))
        self.label_runner.set_text(self.config.get("Runner"))

        # set environment
        self.label_environment.set_text(_(self.config.get("Environment")))

        # set versioning
        self.grid_versioning.set_visible(self.config.get("Versioning"))
        self.label_state.set_text(str(self.config.get("State")))

        self.__set_steam_rules()

    def update_programs(self, widget=False, config=None):
        """
        This function update the programs lists. The list in the
        details' page is limited to 5 items.
        """
        if config:
            self.config = config

        wineserver_status = WineServer(self.config).is_alive()

        while self.list_programs.get_row_at_index(0) is not None:
            self.list_programs.remove(self.list_programs.get_row_at_index(0))

        if self.config.get("Environment") == "Steam":
            self.list_programs.append(ProgramEntry(
                self.window,
                self.config,
                {"name": self.config["Name"]},
                is_steam=True
            ))

        programs = self.manager.get_programs(self.config)
        hidden = len([x for x in programs if x.get("removed")])

        if (len(programs) == 0 or len(programs) == hidden) and self.config.get("Environment") != "Steam":
            self.group_programs.add(self.row_no_programs)
            self.row_no_programs.set_visible(True)
            self.list_programs.set_visible(False)
            return

        i = 0
        # append first 5 entries to group_programs
        for program in programs:
            if program.get("removed"):
                continue
            if i < 5:
                self.list_programs.append(
                    ProgramEntry(
                        window=self.window,
                        config=self.config,
                        program=program,
                        check_boot=wineserver_status
                    )
                )
            i = + 1
            if i == 5:
                break

    def __run_executable_with_args(self, widget):
        """
        This function pop up the dialog to run an executable with
        custom arguments.
        """
        new_window = RunArgsDialog(self)
        new_window.present()

    def run_executable(self, widget, args=False):
        """
        This function pop up the dialog to run an executable.
        The file will be executed by the runner after the
        user confirmation.
        """

        file_dialog = Gtk.FileChooserNative.new(
            _("Choose a Windows executable file"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Run"),
            _("Cancel")
        )

        # file_dialog.set_current_folder(ManagerUtils.get_bottle_path(self.config) + '/drive_c/')
        file_dialog.set_modal(True)
        file_dialog.set_transient_for(self.window)
        file_dialog.connect('response', self.__execute, file_dialog)
        file_dialog.show()

    def __execute(self, _dialog, response, file_dialog, args=""):
        def do_update_programs(result, error=False):
            self.window.page_details.update_programs()

        if response == -3:
            _execs = self.config.get("Latest_Executables", [])
            _file = file_dialog.get_file()
            executor = WineExecutor(
                self.config,
                exec_path=_file.get_path(),
                args=args,
                terminal=self.check_terminal.get_active(),
            )
            RunAsync(executor.run, do_update_programs)
            self.manager.update_config(
                config=self.config,
                key="Latest_Executables",
                value=_execs + [{
                    "name": _file.get_basename().split("/")[-1],
                    "file": _file.get_path(),
                    "args": args
                }]
            )

        self.__update_latest_executables()

    def __update_latest_executables(self):
        """
        This function update the latest executables list.
        """
        while self.box_history.get_first_child() is not None:
            self.box_history.remove(self.box_history.get_first_child())

        _execs = self.config.get("Latest_Executables", [])[-5:]
        for exe in _execs:
            self.box_history.append(ExecButton(
                parent=self,
                data=exe,
                config=self.config
            ))

    def __backup(self, widget, backup_type):
        """
        This function pop up the a file chooser where the user
        can select the path where to export the bottle backup.
        Use the backup_type param to export config or full.
        """
        title = _("Select the location where to save the backup config")
        hint = f"backup_{self.config.get('Path')}.yml"

        if backup_type == "full":
            title = _("Select the location where to save the backup archive")
            hint = f"backup_{self.config.get('Path')}.tar.gz"

        file_dialog = Gtk.FileChooserNative.new(
            title,
            self.window,
            Gtk.FileChooserAction.SAVE,
            _("Export"), _("Cancel")
        )
        file_dialog.set_current_name(hint)
        response = file_dialog.run()
        if response == -3:
            RunAsync(
                task_func=BackupManager.export_backup,
                window=self.window,
                config=self.config,
                scope=backup_type,
                path=file_dialog.get_filename()
            )

        file_dialog.destroy()

    def __duplicate(self, widget):
        """
        This function pop up the duplicate dialog, so the user can
        choose the new bottle name and perform duplication.
        """
        new_window = DuplicateDialog(self)
        new_window.present()

    def __confirm_delete(self, widget):
        """
        This function pop up to delete confirm dialog. If user confirm
        it will ask the manager to delete the bottle and will return
        to the bottles list.
        """
        def handle_response(_widget, response_id):
            if response_id == Gtk.ResponseType.OK:
                RunAsync(self.manager.delete_bottle, config=self.config)
                self.window.page_list.disable_bottle(self.config)
            _widget.destroy()

        widget.set_sensitive(False)

        dialog = MessageDialog(
            window=self.window,
            message=_("Are you sure you want to delete this Bottle and all files?")
        )
        dialog.connect("response", handle_response)
        dialog.show()

    def __update_by_env(self):
        widgets = [self.row_uninstaller, self.row_regedit, self.row_browse]
        if self.config.get("Environment") == "Layered":
            for widget in widgets:
                widget.set_visible(False)
        else:
            for widget in widgets:
                widget.set_visible(True)

    '''
    The following functions are used like wrappers for the
    runner utilities.
    '''

    def run_winecfg(self, widget):
        program = WineCfg(self.config)
        RunAsync(program.launch)

    def run_debug(self, widget):
        program = WineDbg(self.config)
        RunAsync(program.launch_terminal)

    def run_browse(self, widget):
        ManagerUtils.open_filemanager(self.config)

    def run_explorer(self, widget):
        program = Explorer(self.config)
        RunAsync(program.launch)

    def run_cmd(self, widget):
        program = CMD(self.config)
        RunAsync(program.launch_terminal)

    @staticmethod
    def run_snake(widget, event):
        if event.button == 2:
            RunAsync(TerminalUtils().launch_snake)

    def run_taskmanager(self, widget):
        program = Taskmgr(self.config)
        RunAsync(program.launch)

    def run_controlpanel(self, widget):
        program = Control(self.config)
        RunAsync(program.launch)

    def run_uninstaller(self, widget):
        program = Uninstaller(self.config)
        RunAsync(program.launch)

    def run_regedit(self, widget):
        program = Regedit(self.config)
        RunAsync(program.launch)

    def wineboot(self, widget, status):
        def reset(result=None, error=False):
            widget.set_sensitive(True)

        def handle_response(_widget, response_id):
            if response_id == Gtk.ResponseType.OK:
                RunAsync(wineboot.send_status, reset, status)
            else:
                reset()
            _widget.destroy()

        wineboot = WineBoot(self.config)
        widget.set_sensitive(False)

        if status == 0:
            dialog = MessageDialog(
                window=self.window,
                message=_("Are you sure you want to terminate all processes?\nThis can cause data loss.")
            )
            dialog.connect("response", handle_response)
            dialog.show()

    def __set_steam_rules(self):
        status = False if self.config.get("Environment") == "Steam" else True

        for w in [self.btn_delete, self.btn_backup_full, self.btn_duplicate]:
            w.set_visible(status)
            w.set_sensitive(status)
