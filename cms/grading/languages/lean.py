#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Francesco Vercellesi <francesco@vercellesi.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Lean programming language definition."""

from cms.grading import Language
import os

__all__ = ["Lean"]


class Lean(Language):
    """This defines the Lean programming language, compiled with lake.

    """

    @property
    def name(self):
        """See Language.name."""
        return "Lean"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".lean"]

    @property
    def object_extensions(self):
        """See Language.object_extensions."""
        return [".olean"]

    @property
    def executable_extension(self):
        """See Language.executable.extension."""
        return ".lean.exe"
    
    @property
    def requires_multithreading(self):
        """See Language.requires_multithreading."""
        return True

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        assert len(source_filenames) == 1
        return [["/bin/mv", source_filenames[0], executable_filename]]

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        commands = [
            ["/bin/mkdir", ".lake"],
            ["/bin/mkdir", "Template"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/aesop"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/batteries"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/Cli"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/importGraph"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/LeanSearchClient"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/mathlib"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/plausible"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/proofwidgets"],
            ["/bin/git", "config", "--global", "--add", "safe.directory", "/home/cmsuser/template/.lake/packages/Qq"],
            ["/bin/ln", "-s", "/home/cmsuser/template/.lake/packages", ".lake/"], # Symlink the precompiled binaries from the template
            ["/bin/ln", "-s", "/home/cmsuser/template/lakefile.toml", "./"],      # Symlink lakefile.toml
            ["/bin/ln", "-s", "/home/cmsuser/template/lake-manifest.json", "./"], # Symlink lake-manifest.json
            ["/bin/ln", "-s", "/home/cmsuser/template/lean-toolchain", "./"],     # Symlink lean-toolchain
            ["/bin/ln", "-s", "/home/cmsuser/template/Template.lean", "./"],      # Symlink entrypoint
            ["/bin/ln", "-s", f"../{executable_filename}", "Template/Solution.lean"],
            ["/bin/ln", "-s", "../input.txt", "Template/Basic.lean"],
        ]

        # Compile
        commands.append(["/home/cmsuser/.elan/bin/lake", "build"])
        return commands
