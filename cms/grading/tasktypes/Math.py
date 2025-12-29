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

from collections.abc import Iterable
import logging
import os

from cms.db import Executable
from cms.grading.ParameterTypes import ParameterTypeCollection, \
    ParameterTypeChoice, ParameterTypeString
from cms.grading.language import Language
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.steps import compilation_step, evaluation_step, \
    human_evaluation_message
from . import TaskType, \
    check_executables_number, check_files_number, check_manager_present, \
    create_sandbox, delete_sandbox, eval_output, is_manager_for_compilation


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Math(TaskType):
    """Task type class for a Lean submission

    Parameters needs to be a list of three elements.

    No parameters are needed.
    """
    # Codename of the template.
    DEFAULT_INPUT_FILENAME = "input.txt"

    # Other constants to specify the task type behaviour and parameters.
    ALLOW_PARTIAL_SUBMISSION = False

    ACCEPTED_PARAMETERS = []

    @property
    def name(self) -> str:
        """See TaskType.name."""
        return "Math"

    def __init__(self, parameters):
        super().__init__(parameters)

        # Data in the parameters.
        self.compilation: str
        self.input_filename: str
        self.output_filename: str
        self.output_eval: str
        self._actual_input = self.DEFAULT_INPUT_FILENAME

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        codenames_to_compile = []
        codenames_to_compile.extend(
            [x for x in submission_format if x.endswith('.%l')])
        res = dict()
        for language in LANGUAGES:
            source_ext = language.source_extension
            executable_filename = self._executable_filename(submission_format,
                                                            language)
            res[language.name] = language.get_compilation_commands(
                [codename.replace(".%l", source_ext)
                 for codename in codenames_to_compile],
                executable_filename)
        return res

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    @staticmethod
    def _executable_filename(codenames: Iterable[str], language: Language) -> str:
        """Return the chosen executable name computed from the codenames.

        codenames: submission format or codename of submitted files,
            may contain %l.
        language: the programming language of the submission.

        return: a deterministic executable name.

        """
        name = "_".join(sorted(codename.replace(".%l", "")
                               for codename in codenames))
        return name + language.executable_extension

    def _do_compile(self, job, file_cacher):
        language = get_language(job.language)
        source_ext = language.source_extension

        # Create the list of filenames to be passed to the compiler. If we use
        # a grader, it needs to be in first position in the command line, and
        # we check that it exists.
        filenames_to_compile = []
        filenames_and_digests_to_get = {}
        # The grader, that must have been provided (copy and add to
        # compilation).
        # User's submitted file(s) (copy and add to compilation).
        for codename, file_ in job.files.items():
            if not codename.endswith(".%l"):
                continue
            filename = codename.replace(".%l", source_ext)
            filenames_to_compile.append(filename)
            filenames_and_digests_to_get[filename] = file_.digest
        # Any other useful manager (just copy).
        for filename, manager in job.managers.items():
            if is_manager_for_compilation(filename, language):
                filenames_and_digests_to_get[filename] = manager.digest

        # Prepare the compilation command.
        executable_filename = self._executable_filename(job.files.keys(),
                                                        language)
        commands = language.get_compilation_commands(
            filenames_to_compile, executable_filename)

        # Create the sandbox.
        sandbox = create_sandbox(file_cacher, name="compile")
        job.sandboxes.append(sandbox.get_root_path())

        # Copy required files in the sandbox (includes the grader if present).
        for filename, digest in filenames_and_digests_to_get.items():
            sandbox.create_file_from_storage(filename, digest)

        # Run the compilation.
        box_success, compilation_success, text, stats = \
            compilation_step(sandbox, commands)

        # Retrieve the compiled executables.
        job.success = box_success
        job.compilation_success = compilation_success
        job.text = text
        job.plus = stats
        if box_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                "Executable %s for %s" % (executable_filename, job.info))
            job.executables[executable_filename] = \
                Executable(executable_filename, digest)

        # Cleanup.
        delete_sandbox(sandbox, job)

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        if not check_files_number(job, 1, or_more=True):
            return

        self._do_compile(job, file_cacher)

    def _execution_step(self, job, file_cacher):
        # Prepare the execution
        executable_filename = next(iter(job.executables.keys()))
        language = get_language(job.language)
        commands = language.get_evaluation_commands(
            executable_filename,)# main=main)
        executables_to_get = {
            executable_filename: job.executables[executable_filename].digest
        }
        files_to_get = {
            self._actual_input: job.input
        }

        # Create the sandbox
        sandbox = create_sandbox(file_cacher, name="evaluate")
        sandbox.add_mapped_directory("/home/cmsuser/.elan")
        sandbox.add_mapped_directory("/home/cmsuser/template")
        sandbox.set_multiprocess(True)
        sandbox.set_env["ELAN_HOME"] = "/home/cmsuser/.elan"
        job.sandboxes.append(sandbox.get_root_path())

        # Put the required files into the sandbox
        for filename, digest in executables_to_get.items():
            sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in files_to_get.items():
            sandbox.create_file_from_storage(filename, digest)

        # Actually performs the execution
        box_success, evaluation_success, _, stats = \
            compilation_step(sandbox, commands, time_limit=job.time_limit, memory_limit=job.memory_limit)

        outcome = None
        text = None
        output_file_params = None

        # Error in the sandbox: nothing to do!
        if not box_success:
            pass

        # Contestant's error: the marks won't be good
        elif not evaluation_success:
            job.success = True
            job.outcome = "0.0"
            job.text = ["Incorrect solution"]
            job.plus = stats

        # Otherwise, full score is assigned
        else:
            job.success = True
            job.outcome = "1.0"
            job.text = ["Ok."]
            job.plus = stats

        if sandbox is not None:
            delete_sandbox(sandbox, job)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        if not check_executables_number(job, 1):
            return

        self._execution_step(job, file_cacher)
