# list.py
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

import logging
from datetime import datetime
from gi.repository import Gtk, GLib, Handy

from ..runner_utilities import RunnerUtilities


@Gtk.Template(resource_path='/com/usebottles/bottles/list-entry.ui')
class BottlesListEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesListEntry'

    Handy.init()

    '''Get widgets from template'''
    btn_details = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_repair = Gtk.Template.Child()
    btn_run_executable = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    icon_damaged = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    icon_environment = Gtk.Template.Child()

    def __init__(self, window, configuration, arg_executable, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration[1]
        self.arg_executable = arg_executable

        env_icons = {
            'gaming': 'applications-games-symbolic',
            'software': 'applications-engineering-symbolic',
            'custom': 'applications-science-symbolic'
        }

        '''Format update date'''
        update_date = "N/A"
        if self.configuration.get("Update_Date"):
            update_date = datetime.strptime(
                self.configuration.get("Update_Date"),
                "%Y-%m-%d %H:%M:%S.%f"
            )
            update_date = update_date.strftime("%b %d %Y %H:%M:%S")

        '''Signal connections'''
        self.btn_details.connect('pressed', self.show_details)
        self.btn_details.connect('activate', self.show_details)
        self.btn_run.connect('pressed', self.run_executable)
        self.btn_repair.connect('pressed', self.repair)
        self.btn_run_executable.connect('pressed', self.run_executable)

        '''Populate widgets'''
        self.set_title(self.configuration.get("Name"))
        self.grid_versioning.set_visible(self.configuration.get("Versioning"))
        self.label_state.set_text(str(self.configuration.get("State")))

        if self.window.settings.get_boolean("update-date"):
            self.set_subtitle(update_date)

        self.icon_environment.set_from_icon_name(
            env_icons.get(self.configuration.get("Environment").lower()),
            Gtk.IconSize.MENU
        )

        '''If configuration is broken'''
        if self.configuration.get("Broken"):
            for w in [self.btn_repair, self.icon_damaged]:
                w.set_visible(True)

            for w in [self.btn_details, self.btn_run]:
                w.set_sensitive(False)
        else:
            '''Check for arguments from configuration'''
            if self.arg_executable:
                logging.info(
                    f"Arguments found for executable: [{self.arg_executable}].")

                for w in [self.btn_details, self.btn_run]:
                    w.set_visible(False)

                self.btn_run_executable.set_visible(True)

    '''Repair bottle'''

    def repair(self, widget):
        self.runner.repair_bottle(self.configuration)

    '''Display file dialog for executable'''

    def run_executable(self, widget):
        if not self.arg_executable:
            '''If executable is not Bottles argument'''
            file_dialog = Gtk.FileChooserNative.new(
                _("Choose a Windows executable file"),
                self.window,
                Gtk.FileChooserAction.OPEN,
                _("Run"),
                _("Cancel")
            )

            response = file_dialog.run()

            if response == -3:
                RunnerUtilities().run_executable(
                    configuration=self.configuration,
                    file_path=file_dialog.get_filename()
                )

            file_dialog.destroy()
        else:
            '''Use executable provided as bottles argument'''
            RunnerUtilities().run_executable(
                configuration=self.configuration, 
                file_path=self.arg_executable
            )

            if self.window.settings.get_boolean("auto-close-bottles"):
                self.window.proper_close()

            self.arg_executable = False
            self.runner.update_bottles()

    '''Show details page'''

    def show_details(self, widget):
        self.window.page_details.update_combo_components()
        self.window.show_details_view(configuration=self.configuration)


@Gtk.Template(resource_path='/com/usebottles/bottles/list.ui')
class BottlesList(Gtk.Box):
    __gtype_name__ = 'BottlesList'

    '''Get widgets from template'''
    list_bottles = Gtk.Template.Child()
    clamp_list = Gtk.Template.Child()
    hdy_status = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()

    def __init__(self, window, arg_executable, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.arg_executable = arg_executable

        '''Connect signals'''
        self.btn_create.connect("pressed", self.window.show_add_view)

        '''Populate list_bottles'''
        self.update_bottles()

    '''Find and append bottles to list_bottles'''

    def idle_update_bottles(self):
        for bottle in self.list_bottles.get_children():
            bottle.destroy()

        bottles = self.window.runner.local_bottles.items()

        if len(bottles) == 0:
            self.clamp_list.set_visible(False)
            self.hdy_status.set_visible(True)
        else:
            self.clamp_list.set_visible(True)
            self.hdy_status.set_visible(False)

        for bottle in bottles:
            self.list_bottles.add(
                BottlesListEntry(
                    self.window,
                    bottle,
                    self.arg_executable
                )
            )
        self.arg_executable = False

    def update_bottles(self):
        GLib.idle_add(self.idle_update_bottles)
