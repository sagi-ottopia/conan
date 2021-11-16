import logging
import os
import textwrap

from jinja2 import Template
from configparser import ConfigParser, NoSectionError

from conans.errors import ConanException
from conans.model.env_info import unquote
from conans.paths import DEFAULT_PROFILE_NAME, CACERT_FILE
from conans.util.dates import timedelta_from_text
from conans.util.env import get_env
from conans.util.files import load

_t_default_settings_yml = textwrap.dedent("""
    os:
        Windows:
            subsystem: [None, cygwin, msys, msys2, wsl]
        WindowsStore:
            version: ["8.1", "10.0"]
        WindowsCE:
            platform: ANY
            version: ["5.0", "6.0", "7.0", "8.0"]
        Linux:
        Macos:
            version: [None, "10.6", "10.7", "10.8", "10.9", "10.10", "10.11", "10.12", "10.13", "10.14", "10.15", "11.0", "12.0", "13.0"]
            sdk: [None, "macosx"]
            subsystem: [None, catalyst]
        Android:
            api_level: ANY
        iOS:
            version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3",
                      "11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1", "12.2", "12.3", "12.4",
                      "13.0", "13.1", "13.2", "13.3", "13.4", "13.5", "13.6", "13.7",
                      "14.0", "14.1", "14.2", "14.3", "14.4", "14.5", "14.6", "14.7", "14.8", "15.0", "15.1"]
            sdk: [None, "iphoneos", "iphonesimulator"]
        watchOS:
            version: ["4.0", "4.1", "4.2", "4.3", "5.0", "5.1", "5.2", "5.3", "6.0", "6.1", "6.2",
                      "7.0", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "8.0", "8.1"]
            sdk: [None, "watchos", "watchsimulator"]
        tvOS:
            version: ["11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1", "12.2", "12.3", "12.4",
                      "13.0", "13.2", "13.3", "13.4", "14.0", "14.2", "14.3", "14.4", "14.5", "14.6", "14.7",
                      "15.0", "15.1"]
            sdk: [None, "appletvos", "appletvsimulator"]
        FreeBSD:
        SunOS:
        AIX:
        Arduino:
            board: ANY
        Emscripten:
        Neutrino:
            version: ["6.4", "6.5", "6.6", "7.0", "7.1"]
    arch: [x86, x86_64, ppc32be, ppc32, ppc64le, ppc64, armv4, armv4i, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x, asm.js, wasm, sh4le, e2k-v2, e2k-v3, e2k-v4, e2k-v5, e2k-v6, e2k-v7, xtensalx6, xtensalx106]
    compiler:
        sun-cc:
            version: ["5.10", "5.11", "5.12", "5.13", "5.14", "5.15"]
            threads: [None, posix]
            libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
        gcc: &gcc
            version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
                      "5", "5.1", "5.2", "5.3", "5.4", "5.5",
                      "6", "6.1", "6.2", "6.3", "6.4", "6.5",
                      "7", "7.1", "7.2", "7.3", "7.4", "7.5",
                      "8", "8.1", "8.2", "8.3", "8.4",
                      "9", "9.1", "9.2", "9.3",
                      "10", "10.1", "10.2", "10.3",
                      "11", "11.1", "11.2"]
            libcxx: [libstdc++, libstdc++11]
            threads: [None, posix, win32] #  Windows MinGW
            exception: [None, dwarf2, sjlj, seh] # Windows MinGW
            cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20, 23, gnu23]
        Visual Studio: &visual_studio
            runtime: [MD, MT, MTd, MDd]
            version: ["8", "9", "10", "11", "12", "14", "15", "16", "17"]
            toolset: [None, v90, v100, v110, v110_xp, v120, v120_xp,
                      v140, v140_xp, v140_clang_c2, LLVM-vs2012, LLVM-vs2012_xp,
                      LLVM-vs2013, LLVM-vs2013_xp, LLVM-vs2014, LLVM-vs2014_xp,
                      LLVM-vs2017, LLVM-vs2017_xp, v141, v141_xp, v141_clang_c2, v142,
                      llvm, ClangCL, v143]
            cppstd: [None, 14, 17, 20, 23]
        msvc:
            version: ["19.0",
                      "19.1", "19.10", "19.11", "19.12", "19.13", "19.14", "19.15", "19.16",
                      "19.2", "19.20", "19.21", "19.22", "19.23", "19.24", "19.25", "19.26", "19.27", "19.28", "19.29",
                      "19.3", "19.30"]
            runtime: [static, dynamic]
            runtime_type: [Debug, Release]
            cppstd: [14, 17, 20, 23]
        clang:
            version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0",
                      "5.0", "6.0", "7.0", "7.1",
                      "8", "9", "10", "11", "12", "13"]
            libcxx: [None, libstdc++, libstdc++11, libc++, c++_shared, c++_static]
            cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20, 23, gnu23]
            runtime: [None, MD, MT, MTd, MDd]
        apple-clang: &apple_clang
            version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1", "9.0", "9.1", "10.0", "11.0", "12.0", "13.0"]
            libcxx: [libstdc++, libc++]
            cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
        intel:
            version: ["11", "12", "13", "14", "15", "16", "17", "18", "19", "19.1"]
            update: [None, ANY]
            base:
                gcc:
                    <<: *gcc
                    threads: [None]
                    exception: [None]
                Visual Studio:
                    <<: *visual_studio
                apple-clang:
                    <<: *apple_clang
        intel-cc:
            version: ["2021.1", "2021.2", "2021.3"]
            update: [None, ANY]
            mode: ["icx", "classic", "dpcpp"]
            libcxx: [None, libstdc++, libstdc++11, libc++]
            cppstd: [None, 98, gnu98, 03, gnu03, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20, 23, gnu23]
            runtime: [None, static, dynamic]
            runtime_type: [None, Debug, Release]
        qcc:
            version: ["4.4", "5.4", "8.3"]
            libcxx: [cxx, gpp, cpp, cpp-ne, accp, acpp-ne, ecpp, ecpp-ne]
            cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17]
        mcst-lcc:
            version: ["1.19", "1.20", "1.21", "1.22", "1.23", "1.24", "1.25"]
            base:
                gcc:
                    <<: *gcc
                    threads: [None]
                    exceptions: [None]

    build_type: [None, Debug, Release, RelWithDebInfo, MinSizeRel]
    """)


def get_default_settings_yml():
    return _t_default_settings_yml


_t_default_client_conf = Template(textwrap.dedent("""
    [log]
    run_to_output = True        # environment CONAN_LOG_RUN_TO_OUTPUT
    run_to_file = False         # environment CONAN_LOG_RUN_TO_FILE
    level = critical            # environment CONAN_LOGGING_LEVEL
    # trace_file =              # environment CONAN_TRACE_FILE
    print_run_commands = False  # environment CONAN_PRINT_RUN_COMMANDS

    [general]
    default_profile = {{default_profile}}
    sysrequires_sudo = True               # environment CONAN_SYSREQUIRES_SUDO
    request_timeout = 60                  # environment CONAN_REQUEST_TIMEOUT (seconds)

    # sysrequires_mode = enabled          # environment CONAN_SYSREQUIRES_MODE (allowed modes enabled/verify/disabled)
    # verbose_traceback = False           # environment CONAN_VERBOSE_TRACEBACK
    # bash_path = ""                      # environment CONAN_BASH_PATH (only windows)
    # read_only_cache = True              # environment CONAN_READ_ONLY_CACHE

    # non_interactive = False
    # skip_broken_symlinks_check = False  # environment CONAN_SKIP_BROKEN_SYMLINKS_CHECK


    # cpu_count = 1             # environment CONAN_CPU_COUNT

    # Change the default location for building test packages to a temporary folder
    # which is deleted after the test.
    # temp_test_folder = True             # environment CONAN_TEMP_TEST_FOLDER

    # cacert_path                         # environment CONAN_CACERT_PATH

    # config_install_interval = 1h
    # required_conan_version = >=1.26

    [storage]
    # This is the default path, but you can write your own. It must be an absolute path or a
    # path beginning with "~" (if the environment var CONAN_USER_HOME is specified, this directory, even
    # with "~/", will be relative to the conan user home, not to the system user home)
    path = ./data

    [proxies]
    # Empty (or missing) section will try to use system proxies.
    # As documented in https://requests.readthedocs.io/en/master/user/advanced/#proxies - but see below
    # for proxies to specific hosts
    # http = http://user:pass@10.10.1.10:3128/
    # http = http://10.10.1.10:3128
    # https = http://10.10.1.10:1080
    # To specify a proxy for a specific host or hosts, use multiple lines each specifying host = proxy-spec
    # http =
    #   hostname.to.be.proxied.com = http://user:pass@10.10.1.10:3128
    # You can skip the proxy for the matching (fnmatch) urls (comma-separated)
    # no_proxy_match = *bintray.com*, https://myserver.*
    """))


def get_default_client_conf(force_v1=False):
    return _t_default_client_conf.render(default_profile=DEFAULT_PROFILE_NAME)


class ConanClientConfigParser(ConfigParser, object):

    # So keys are not converted to lowercase, we override the default optionxform
    optionxform = str

    _table_vars = {
        # Environment variable | conan.conf variable | Default value
        "log": [
            ("CONAN_LOG_RUN_TO_OUTPUT", "run_to_output", True),
            ("CONAN_LOG_RUN_TO_FILE", "run_to_file", False),
            ("CONAN_LOGGING_LEVEL", "level", logging.CRITICAL),
            ("CONAN_TRACE_FILE", "trace_file", None),
            ("CONAN_PRINT_RUN_COMMANDS", "print_run_commands", False),
        ],
        "general": [
            ("CONAN_SKIP_BROKEN_SYMLINKS_CHECK", "skip_broken_symlinks_check", False),
            ("CONAN_SYSREQUIRES_SUDO", "sysrequires_sudo", False),
            ("CONAN_SYSREQUIRES_MODE", "sysrequires_mode", None),
            ("CONAN_CPU_COUNT", "cpu_count", None),
            ("CONAN_VERBOSE_TRACEBACK", "verbose_traceback", None),
        ],
        "hooks": [
            ("CONAN_HOOKS", "", None),
        ]
    }

    def __init__(self, filename):
        super(ConanClientConfigParser, self).__init__(allow_no_value=True)
        self.read(filename)
        self.filename = filename
        self._non_interactive = None

    @property
    def env_vars(self):
        ret = {}
        for section, values in self._table_vars.items():
            for env_var, var_name, default_value in values:
                var_name = ".".join([section, var_name]) if var_name else section
                value = self._env_c(var_name, env_var, default_value)
                if value is not None:
                    ret[env_var] = str(value)
        return ret

    def _env_c(self, var_name, env_var_name, default_value):
        """ Returns the value Conan will use: first tries with environment variable,
            then value written in 'conan.conf' and fallback to 'default_value'
        """
        env = os.environ.get(env_var_name, None)
        if env is not None:
            return env
        try:
            return unquote(self.get_item(var_name))
        except ConanException:
            return default_value

    def get_item(self, item):
        """ Return the value stored in 'conan.conf' """
        if not item:
            return load(self.filename)

        tokens = item.split(".", 1)
        section_name = tokens[0]
        try:
            section = self.items(section_name)
        except NoSectionError:
            raise ConanException("'%s' is not a section of conan.conf" % section_name)
        if len(tokens) == 1:
            result = []
            if section_name == "hooks":
                for key, _ in section:
                    result.append(key)
                return ",".join(result)
            else:
                for section_item in section:
                    result.append(" = ".join(section_item))
                return "\n".join(result)
        else:
            key = tokens[1]
            try:
                value = dict(section)[key]
                if " #" in value:  # Comments
                    value = value[:value.find(" #")].strip()
            except KeyError:
                raise ConanException("'%s' doesn't exist in [%s]" % (key, section_name))
            return value

    def set_item(self, key, value):
        tokens = key.split(".", 1)
        if len(tokens) == 1:  # defining full section
            raise ConanException("You can't set a full section, please specify a section.key=value")

        section_name = tokens[0]
        if not self.has_section(section_name):
            self.add_section(section_name)

        key = tokens[1]
        try:
            super(ConanClientConfigParser, self).set(section_name, key, value)
        except ValueError:
            # https://github.com/conan-io/conan/issues/4110
            value = value.replace("%", "%%")
            super(ConanClientConfigParser, self).set(section_name, key, value)

        with open(self.filename, "w") as f:
            self.write(f)

    def rm_item(self, item):
        tokens = item.split(".", 1)
        section_name = tokens[0]
        if not self.has_section(section_name):
            raise ConanException("'%s' is not a section of conan.conf" % section_name)

        if len(tokens) == 1:
            self.remove_section(tokens[0])
        else:
            key = tokens[1]
            if not self.has_option(section_name, key):
                raise ConanException("'%s' doesn't exist in [%s]" % (key, section_name))
            self.remove_option(section_name, key)

        with open(self.filename, "w") as f:
            self.write(f)

    def _get_conf(self, varname):
        """Gets the section from config file or raises an exception"""
        try:
            return self.items(varname)
        except NoSectionError:
            raise ConanException("Invalid configuration, missing %s" % varname)

    @property
    def parallel_download(self):
        try:
            parallel = self.get_item("general.parallel_download")
        except ConanException:
            return None

        try:
            return int(parallel) if parallel is not None else None
        except ValueError:
            raise ConanException("Specify a numeric parameter for 'parallel_download'")

    @property
    def proxies(self):
        try:  # optional field, might not exist
            proxies = self._get_conf("proxies")
        except Exception:
            return None
        result = {}
        # Handle proxy specifications of the form:
        # http = http://proxy.xyz.com
        #   special-host.xyz.com = http://special-proxy.xyz.com
        # (where special-proxy.xyz.com is only used as a proxy when special-host.xyz.com)
        for scheme, proxy_string in proxies or []:
            if proxy_string is None or proxy_string == "None":
                result[scheme] = None
            else:
                for line in proxy_string.splitlines():
                    proxy_value = [t.strip() for t in line.split("=", 1)]
                    if len(proxy_value) == 2:
                        result[scheme+"://"+proxy_value[0]] = proxy_value[1]
                    elif proxy_value[0]:
                        result[scheme] = proxy_value[0]
        return result

    @property
    def hooks(self):
        hooks = get_env("CONAN_HOOKS", list())
        if not hooks:
            try:
                hooks = self._get_conf("hooks")
                hooks = [k for k, _ in hooks]
            except Exception:
                hooks = []
        return hooks

    @property
    def non_interactive(self):
        if self._non_interactive is None:
            try:
                non_interactive = get_env("CONAN_NON_INTERACTIVE")
                if non_interactive is None:
                    non_interactive = self.get_item("general.non_interactive")
                self._non_interactive = non_interactive.lower() in ("1", "true")
            except ConanException:
                self._non_interactive = False
        return self._non_interactive

    @non_interactive.setter
    def non_interactive(self, value):
        # Made this because uploads in parallel need a way to disable the interactive
        # FIXME: Can't we fail in the command line directly if no interactive?
        #        see uploader.py  if parallel_upload:
        self._non_interactive = value

    @property
    def logging_level(self):
        try:
            level = get_env("CONAN_LOGGING_LEVEL")
            if level is None:
                level = self.get_item("log.level")
            try:
                parsed_level = ConanClientConfigParser.get_log_level_by_name(level)
                level = parsed_level if parsed_level is not None else int(level)
            except Exception:
                level = logging.CRITICAL
            return level
        except ConanException:
            return logging.CRITICAL

    @property
    def logging_file(self):
        return get_env('CONAN_LOGGING_FILE', None)

    @property
    def print_commands_to_output(self):
        try:
            print_commands_to_output = get_env("CONAN_PRINT_RUN_COMMANDS")
            if print_commands_to_output is None:
                print_commands_to_output = self.get_item("log.print_run_commands")
            return print_commands_to_output.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def generate_run_log_file(self):
        try:
            generate_run_log_file = get_env("CONAN_LOG_RUN_TO_FILE")
            if generate_run_log_file is None:
                generate_run_log_file = self.get_item("log.run_to_file")
            return generate_run_log_file.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def log_run_to_output(self):
        try:
            log_run_to_output = get_env("CONAN_LOG_RUN_TO_OUTPUT")
            if log_run_to_output is None:
                log_run_to_output = self.get_item("log.run_to_output")
            return log_run_to_output.lower() in ("1", "true")
        except ConanException:
            return True

    @staticmethod
    def get_log_level_by_name(level_name):
        levels = {
            "critical": logging.CRITICAL,
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "warn": logging.WARNING,
            "info": logging.INFO,
            "debug": logging.DEBUG,
            "notset": logging.NOTSET
        }
        return levels.get(str(level_name).lower())

    @property
    def config_install_interval(self):
        item = "general.config_install_interval"
        try:
            interval = self.get_item(item)
        except ConanException:
            return None

        try:
            return timedelta_from_text(interval)
        except Exception:
            self.rm_item(item)
            raise ConanException("Incorrect definition of general.config_install_interval: {}. "
                                 "Removing it from conan.conf to avoid possible loop error."
                                 .format(interval))

    @property
    def required_conan_version(self):
        try:
            return self.get_item("general.required_conan_version")
        except ConanException:
            return None
