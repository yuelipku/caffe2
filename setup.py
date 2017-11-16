from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from distutils.spawn import find_executable
from distutils import sysconfig, log
import setuptools
import setuptools.command.build_py
import setuptools.command.develop
import setuptools.command.build_ext

from collections import namedtuple
import multiprocessing
import os
import shlex
import subprocess
import sys
from textwrap import dedent

TOP_DIR = os.path.realpath(os.path.dirname(__file__))
SRC_DIR = os.path.join(TOP_DIR, 'caffe2')
PROTOC = find_executable('protoc')

install_requires = set()
setup_requires = set()
test_requires = set()

################################################################################
# Pre Check
################################################################################

assert find_executable('cmake'), 'Could not find "cmake" executable!'
assert find_executable('make'), 'Could not find "make" executable!'

################################################################################
# Version
################################################################################

try:
    git_version = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                          cwd=TOP_DIR).decode('ascii').strip()
except subprocess.CalledProcessError:
    git_version = None

with open(os.path.join(TOP_DIR, 'VERSION_NUMBER')) as version_file:
    VersionInfo = namedtuple('VersionInfo', ['version', 'git_version'])(
        version=version_file.read().strip(),
        git_version=git_version
    )

################################################################################
# Customized commands
################################################################################

class Caffe2Command(setuptools.Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


class create_version(Caffe2Command):
    def run(self):
        with open(os.path.join(SRC_DIR, 'version.py'), 'w') as f:
            f.write(dedent('''
            version = '{version}'
            git_version = '{git_version}'
            '''.format(**dict(VersionInfo._asdict()))))


class build_py(setuptools.command.build_py.build_py):
    def run(self):
        self.run_command('create_version')
        setuptools.command.build_py.build_py.run(self)


class develop(setuptools.command.develop.develop):
    def run(self):
        raise RuntimeError('develop mode is not supported!')


class build_ext(setuptools.command.build_ext.build_ext):
    def _build_with_cmake(self):
        build_temp = os.path.realpath(self.build_temp)
        build_lib = os.path.realpath(self.build_lib)

        install_dir = os.environ.get('CMAKE_INSTALL_DIR',
                                     os.path.join(build_temp, 'cmake_install'))
        build_dir = os.environ.get('CMAKE_BUILD_DIR',
                                   os.path.join(build_temp, 'cmake_build'))
        if not os.path.exists(build_dir):
            self.compiler.mkpath(build_dir)

        py_exe = sys.executable
        py_inc = sysconfig.get_python_inc()
        cmake_args = shlex.split(os.environ.get('CMAKE_ARGS', ''))
        log.info('CMAKE_ARGS: {}'.format(cmake_args))

        cwd = os.getcwd()
        os.chdir(build_dir)
        self.compiler.spawn([
            'cmake',
            '-DBUILD_SHARED_LIBS=OFF',
            # TODO: Investigate why BUILD_SHARED_LIBS=OFF USE_GLOO=ON
            # will cause error 'target "gloo" that is not in the
            # export set' in cmake.
            '-DUSE_GLOO=OFF',
            '-DCMAKE_INSTALL_PREFIX:PATH={}'.format(install_dir),
            '-DPYTHON_EXECUTABLE:FILEPATH={}'.format(py_exe),
            '-DPYTHON_INCLUDE_DIR={}'.format(py_inc),
            '-DBUILD_TEST=OFF',
            '-BUILD_BENCHMARK=OFF',
            '-DBUILD_BINARY=OFF',
            TOP_DIR
        ] + cmake_args)
        self.compiler.spawn([
            'make',
            '-j{}'.format(multiprocessing.cpu_count() + 1)
        ])
        self.compiler.spawn(['make', 'install'])
        os.chdir(cwd)

        for py_dir in ['caffe', 'caffe2']:
            self.copy_tree(os.path.join(install_dir, py_dir),
                           os.path.join(build_lib, py_dir))

    def get_outputs(self):
        return [os.path.join(self.build_lib, d)
                for d in ['caffe', 'caffe2']]

    def build_extensions(self):
        assert len(self.extensions) == 1
        self._build_with_cmake()


cmdclass={
    'create_version': create_version,
    'build_py': build_py,
    'develop': develop,
    'build_ext': build_ext,
}

################################################################################
# Extensions
################################################################################

ext_modules = [setuptools.Extension(str('caffe2-ext'), [])]

################################################################################
# Packages
################################################################################

packages = []

install_requires.update(['protobuf',
                         'numpy',
                         'flask',
                         'future',
                         'graphviz',
                         'hypothesis',
                         'jupyter',
                         'matplotlib',
                         'pydot',
                         'python-nvd3',
                         'pyyaml',
                         'requests',
                         'scikit-image',
                         'scipy',
                         'setuptools',
                         'six',
                         'tornado'])

################################################################################
# Test
################################################################################

setup_requires.add('pytest-runner')
test_requires.update(['pytest-cov', 'hypothesis'])

################################################################################
# Final
################################################################################

setuptools.setup(
    name='caffe2',
    version=VersionInfo.version,
    description='Caffe2',
    ext_modules=ext_modules,
    cmdclass=cmdclass,
    packages=packages,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=test_requires,
    author='jiayq',
    author_email='jiayq@fb.com',
    url='https://github.com/caffe2/caffe2',
)