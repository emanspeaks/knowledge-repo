from .._version import __git_uri__
from git import (
    Repo, InvalidGitRepositoryError, IndexFile, Commit, Actor, Git,
    HookExecutionError, safe_decode,
)
from git.types import Commit_ish
from git.index.fun import hook_path, _has_file_extension
from git.compat import is_win, is_posix, force_text, defenc
from git.cmd import PROC_CREATIONFLAGS, handle_process_output
from git.util import finalize_process
import os
import shutil
import tempfile
from typing import Union, List
from datetime import datetime
from pathlib import Path
from subprocess import Popen, PIPE, run, CalledProcessError


def bash_path():
    if not is_win:
        return 'bash'
    try:
        wheregit = run(['where', Git.GIT_PYTHON_GIT_EXECUTABLE], check=True,
                       stdout=PIPE).stdout
    except CalledProcessError:
        return 'bash.exe'
    gitpath = Path(wheregit.decode(defenc).splitlines()[0])
    gitroot = gitpath.parent.parent
    gitbash = gitroot/'bin'/'bash.exe'
    return str(gitbash) if gitbash.exists else 'bash.exe'


def run_commit_hook(name: str, index: "IndexFile", *args: str) -> None:
    """Run the commit hook of the given name. Silently ignores hooks that do not exist.

    :param name: name of hook, like 'pre-commit'
    :param index: IndexFile instance
    :param args: arguments passed to hook file
    :raises HookExecutionError:"""
    hp = hook_path(name, index.repo.git_dir)
    if not os.access(hp, os.X_OK):
        return None

    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = safe_decode(str(index.path))
    env["GIT_EDITOR"] = ":"
    cmd = [hp]
    try:
        if is_win and not _has_file_extension(hp):
            # Windows only uses extensions to determine how to open files
            # (doesn't understand shebangs). Try using bash to run the hook.
            relative_hp = Path(hp).relative_to(index.repo.working_dir).as_posix()
            cmd = [bash_path(), relative_hp]

        process = Popen(
            cmd + list(args),
            env=env,
            stdout=PIPE,
            stderr=PIPE,
            cwd=index.repo.working_dir,
            close_fds=is_posix,
            creationflags=PROC_CREATIONFLAGS,
        )
    except Exception as ex:
        raise HookExecutionError(hp, ex) from ex
    else:
        stdout_list: List[str] = []
        stderr_list: List[str] = []
        handle_process_output(process, stdout_list.append, stderr_list.append, finalize_process)
        stdout = "".join(stdout_list)
        stderr = "".join(stderr_list)
        if process.returncode != 0:
            stdout = force_text(stdout, defenc)
            stderr = force_text(stderr, defenc)
            raise HookExecutionError(hp, process.returncode, stderr, stdout)
    # end handle return code


class IndexFileWrapper(IndexFile):
    def commit(
        self,
        message: str,
        parent_commits: Union[Commit_ish, None] = None,
        head: bool = True,
        author: Union[None, Actor] = None,
        committer: Union[None, Actor] = None,
        author_date: Union[datetime, str, None] = None,
        commit_date: Union[datetime, str, None] = None,
        skip_hooks: bool = False,
    ) -> Commit:
        # see IndexFile.commit for details, copied from there
        if not skip_hooks:
            run_commit_hook("pre-commit", self)

            self._write_commit_editmsg(message)
            run_commit_hook("commit-msg", self, self._commit_editmsg_filepath())
            message = self._read_commit_editmsg()
            self._remove_commit_editmsg()
        tree = self.write_tree()
        rval = Commit.create_from_tree(
            self.repo,
            tree,
            message,
            parent_commits,
            head,
            author=author,
            committer=committer,
            author_date=author_date,
            commit_date=commit_date,
        )
        if not skip_hooks:
            run_commit_hook("post-commit", self)
        return rval


class RepoWrapper(Repo):
    @property
    def index(self):
        return IndexFileWrapper(self)


def clone_kr_to_directory(dir):
    dir = os.path.expanduser(dir)
    if not os.path.exists(dir):
        os.makedirs(dir)
    assert os.path.isdir(dir)

    try:
        repo = RepoWrapper(dir)
        repo.remote().fetch()
    except InvalidGitRepositoryError:
        repo = RepoWrapper.clone_from(__git_uri__, dir)


def checkout_revision_to_dir(repo_path, revision, dir):
    repo_path = os.path.expanduser(repo_path)
    dir = os.path.expanduser(dir)
    repo = RepoWrapper(repo_path)
    repo.remote().fetch()
    repo.git.checkout(revision)
    return repo.git.checkout_index('-a', '-f', prefix=dir)


class CheckedOutRevision(object):

    def __init__(self, repo_path, revision):
        self.repo_path = repo_path
        self.revision = revision

    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        checkout_revision_to_dir(self.repo_path, self.revision, self.dir + '/')
        return self.dir

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.dir)
