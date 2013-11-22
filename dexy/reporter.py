from dexy.utils import file_exists
import dexy.plugin
import os
import shutil
import sys

class Reporter(dexy.plugin.Plugin):
    """
    Base class for types of reporter.
    """
    __metaclass__ = dexy.plugin.PluginMeta

    _settings = {
            "default" : ("""Whether to run this report by default. Should be
            False for reports with side effects.""", True),
            "dir" : ("""Directory where report output will be written.""",
                None),
            'filename' : ("""Name of report file to generate (used when the
                report consists of just a single file).""", None),
            "in-cache-dir" : ("""Whether to create report dir in the cache
                directory (instead of project root).""", False),
            'no-delete' : ("""List of file names not to delete when resetting
                report dir (only effective if report dir is cleaned
                element-wise).""", ['.git', '.nojekyll']),
            'plugins' : ("""List of template plugin aliases which should be
                included in jinja environment.""",
                ['debug', 'inflection', 'builtins', 'operator', 'datetime', 'pprint']
                ),
            "run-for-wrapper-states" : ("""Wrapper states for which report is
                valid.""", ["ran"]),
            "readme-filename" : ("Name of README file, or None to omit." ,
                "README"),
            "safety-filename" : ("""Name of a file which will be created in
                generated dir to indicate it was created by dexy and is safe to
                auto-remove.""", ".dexy-generated"), }

    def is_active(self):
        return True

    def help(self):
        """
        Allow implementing custom help since reporters can have such different behavior.
        """
        pass

    def copy_template_files(self):
        # Copy template files (e.g. .css files)
        # TODO shouldn't need to copy this each time - can just overwrite files which change
        class_file = sys.modules[self.__module__].__file__
        template_parent_dir = os.path.dirname(class_file)
        template_dir = os.path.join(template_parent_dir, 'files')
        shutil.copytree(template_dir, self.report_dir())
        self.write_safety_file()

    def run_plugins(self):
        env = {}
        for alias in self.setting('plugins'):
            from dexy.filters.templating_plugins import TemplatePlugin
            plugin = TemplatePlugin.create_instance(alias)
            self.log_debug("Running template plugin %s" % plugin.__class__.__name__)

            try:
                new_env_vars = plugin.run()
            except Exception:
                print "error occurred processing template plugin '%s'" % alias
                raise

            if any(v in env.keys() for v in new_env_vars):
                new_keys = ", ".join(sorted(new_env_vars))
                existing_keys = ", ".join(sorted(env))
                msg = "plugin class '%s' is trying to add new keys '%s', already have '%s'"
                raise dexy.exceptions.InternalDexyProblem(msg % (plugin.__class__.__name__, new_keys, existing_keys))
            env.update(new_env_vars)
        return env

    def template_data(self):
        return dict((k, v[1]) for k, v in self.run_plugins().iteritems())

    def cache_reports_dir(self):
        return os.path.join(self.wrapper.artifacts_dir, "reports")

    def report_dir(self):
        """
        Returns path of report directory relative to dexy project root.
        """
        if not self.setting('dir'):
            return None
        elif self.setting('in-cache-dir'):
            return os.path.join(self.cache_reports_dir(), self.setting('dir'))
        else:
            return self.setting('dir')

    def report_file(self):
        if self.setting('dir'):
            return os.path.join(self.report_dir(), self.setting('filename'))
        else:
            if self.setting('in-cache-dir'):
                return os.path.join(self.cache_reports_dir(), self.setting('filename'))
            else:
                return self.setting('dir')

    def key_for_log(self):
        return "reporter:%s" % self.aliases[0]

    def log_debug(self, message):
        self.wrapper.log.debug("%s: %s" % (self.key_for_log(), message))

    def log_info(self, message):
        self.wrapper.log.info("%s: %s" % (self.key_for_log(), message))

    def log_warn(self, message):
        self.wrapper.log.warn("%s: %s" % (self.key_for_log(), message))

    def safety_filepath(self):
        return os.path.join(self.report_dir(), self.setting('safety-filename'))

    def readme_filepath(self):
        readme_filename = self.setting('readme-filename')
        if readme_filename and readme_filename != 'None':
            return os.path.join(self.report_dir(), readme_filename)

    def write_safety_file(self):
        with open(self.safety_filepath(), "w") as f:
            f.write("""
            This directory was generated by the %s Dexy Reporter and
            may be deleted without notice.\n\n""" % self.__class__.__name__)

    def write_readme_file(self):
        with open(self.readme_filepath(), "w") as f:
            f.write("""
            This directory was generated by the %s Dexy Reporter and
            may be deleted without notice.\n\n""" % self.__class__.__name__)

    def create_cache_reports_dir(self):
        if not file_exists(self.cache_reports_dir()):
            os.makedirs(self.cache_reports_dir())

    def create_reports_dir(self):
        if not self.report_dir():
            return False

        if not file_exists(self.report_dir()):
            os.makedirs(self.report_dir())

        self.write_safety_file()
        if self.readme_filepath():
            self.write_readme_file()

    def remove_reports_dir(self, wrapper, keep_empty_dir=False):
        self.wrapper = wrapper
        if not self.report_dir():
            return False

        if file_exists(self.report_dir()) and not file_exists(self.safety_filepath()):
            msg = "Please remove directory %s, Dexy wants to write a report here but there's already a file or directory in this location."
            msgargs = (os.path.abspath(self.report_dir()),)
            raise dexy.exceptions.UserFeedback(msg % msgargs)
        elif file_exists(self.report_dir()):
            if keep_empty_dir:
                # Does not remove the base directory, useful if you are running
                # a process (like 'dexy serve') from inside that directory
                for f in os.listdir(self.report_dir()):
                    if not f in self.setting('no-delete'):
                        path = os.path.join(self.report_dir(), f)
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                self.write_safety_file()
            else:
                shutil.rmtree(self.report_dir())

    def run(self, wrapper):
        pass
