import os
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from itertools import chain

__all__ = ['this_dir', 'test_data_dir', 'test_stage_dir', 'stage_dir', 'pushd',
           'copytree', 'check_call_silent', 'check_output', 'git_config',
           'git_init', 'commit_files', 'match_redir', 'assertDirectory']

this_dir = os.path.abspath(os.path.dirname(__file__))
test_data_dir = os.path.join(this_dir, 'data')
test_stage_dir = os.path.join(this_dir, 'stage')

# Clear the stage directory for this test run.
if os.path.exists(test_stage_dir):
    shutil.rmtree(test_stage_dir)
os.makedirs(test_stage_dir)


def stage_dir(name):
    stage = tempfile.mkdtemp(prefix=name + '-', dir=test_stage_dir)
    os.chdir(stage)
    return stage


@contextmanager
def pushd(dirname):
    old = os.getcwd()
    os.chdir(dirname)
    try:
        yield
    finally:
        os.chdir(old)


def copytree(src, dst, ignore_hidden=True):
    def accumulate(path):
        for i in os.listdir(os.path.join(src, path)):
            if ignore_hidden and i[0] == '.':
                continue

            curr_path = os.path.join(path, i)
            if os.path.isdir(os.path.join(src, curr_path)):
                yield (curr_path, True)
                yield from accumulate(curr_path)
            else:
                yield (curr_path, False)

    # Make a list of files to copy *before* starting to copy, so that we can
    # put our copy inside the src directory.
    to_copy = list(accumulate(''))
    seen_dirs = set()

    os.makedirs(dst, exist_ok=True)
    for path, isdir in to_copy:
        curr_src = os.path.join(src, path)
        curr_dst = os.path.join(dst, path)

        if isdir:
            if path not in seen_dirs:
                seen_dirs.add(path)
                os.makedirs(curr_dst, exist_ok=True)
        else:
            shutil.copy2(curr_src, curr_dst)


def check_output(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          universal_newlines=True).stdout


def check_call_silent(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def git_config():
    check_call_silent(['git', 'config', 'user.name', 'username'])
    check_call_silent(['git', 'config', 'user.email', 'user@site.tld'])


def git_init():
    check_call_silent(['git', 'init',  '--initial-branch=master'])
    git_config()


def commit_files(filenames, message='add file'):
    for f in filenames:
        dirname = os.path.dirname(f)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        open(f, 'w').close()
        check_call_silent(['git', 'add', f])
    check_call_silent(['git', 'commit', '-m', message])


def remove_in_place(x, func):
    for i in reversed(range(len(x))):
        if func(x[i]):
            del x[i]


def walk(top, include_hidden):
    for base, dirs, files in os.walk(top):
        if not include_hidden:
            remove_in_place(dirs, lambda x: x[0] == '.')
            remove_in_place(files, lambda x: x[0] == '.')
        yield base, dirs, files


def relpaths(paths, base):
    return [os.path.relpath(i, base) for i in paths]


def match_redir(url):
    return r'window\.location\.replace\(\s*"{}"'.format(re.escape(url))


def assertDirectory(path, contents, include_hidden=False, allow_extra=False):
    path = os.path.normpath(path)
    actual = set(os.path.normpath(os.path.join(base, f))
                 for base, dirs, files in walk(path, include_hidden)
                 for f in chain(files, dirs))
    expected = set(os.path.normpath(os.path.join(path, i)) for i in contents)
    extra = actual - expected

    if allow_extra:
        missing = expected - actual
        if missing:
            raise unittest.TestCase.failureException(
                'missing: {}'.format(relpaths(missing, path))
            )
    else:
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise unittest.TestCase.failureException(
                'missing: {}, extra: {}'.format(relpaths(missing, path),
                                                relpaths(extra, path))
            )
