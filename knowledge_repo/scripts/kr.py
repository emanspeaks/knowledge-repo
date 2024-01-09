#!/usr/bin/env python

from typing import Sequence, Union, List
from argparse import Namespace, Action, ArgumentParser
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from git import GitError, ODBError
from tabulate import tabulate

# If this script is being run out of a checked out repository, we need to make
# sure the appropriate knowledge_repo is being used. To do this, we add the
# parent directory of the folder of the package if this package is named
# "knowledge_repo".
script_dir = Path(__file__).parent
if script_dir.parent.name == 'knowledge_repo':
    sys.path.insert(0, str(script_dir.parent.parent))

from knowledge_repo import KnowledgeRepository, __version__, KnowledgePost  # noqa: E402, E501
from knowledge_repo.repositories.gitrepository import GitKnowledgeRepository  # nopep8 # noqa: E402, E501
from knowledge_repo.app import KnowledgeFlask  # noqa: E402
from knowledge_repo.app.deploy import KnowledgeDeployer, get_app_builder  # noqa: E402, E501


# If there's a contrib folder, add this as well and import it
contrib_dir = str(script_dir.parent.parent / 'contrib')
if os.path.exists(os.path.join(contrib_dir, '__init__.py')):
    sys.path.insert(0, os.path.join(contrib_dir, '..'))


# We first check whether this script actually the one we are going to be using,
# or whether it should delegate tasks to a different script: namely the one
# hosted in a knowledge data repo (so that client and server both use the same
# version of the code, and updates can be done simultaneously and seamlessly).
# We do this by partially constructing the argument parser, and checking the
# provided repo. We do this before we finish constructing the entire parser so
# that the syntax and arguments can change from version to version of
# this script.

class ParseRepositories(Action):
    def __init__(self, **kwargs):
        super(ParseRepositories, self).__init__(**kwargs)
        pattern = re.compile(r'^(?:\{(?P<name>[a-zA-Z_0-9]*)\})?(?P<uri>.*)$')
        self.prefix_pattern = pattern

    def __call__(self, parser, namespace, values, option_string=None):
        nmspc = getattr(namespace, self.dest)
        if not nmspc or nmspc == self.default:
            self._repo_dict = {}
        repo = values
        prefix = self.prefix_pattern.match(repo)
        if not prefix:
            raise ValueError(
                "Be sure to specify repositories in form {name}uri when "
                "specifying more than one repository."
            )
        name, uri = prefix.groups()
        if name in self._repo_dict:
            raise ValueError(
                f"Multiple repositories with the name ({name}) have been "
                "specified. Please ensure all referenced repositories have a "
                "unique name."
            )

        self._repo_dict[name] = uri

        if None in self._repo_dict and len(self._repo_dict) > 1:
            raise ValueError(
                "Make sure you specify names for all repositories."
            )

        if None in self._repo_dict:
            setattr(namespace, self.dest, self._repo_dict[None])
        else:
            setattr(namespace, self.dest, self._repo_dict)


def create_args():
    parser = ArgumentParser(add_help=False,
                            description='Script to simplify management of the knowledge data repo.')
    parser.add_argument('--repo', action=ParseRepositories, help='The repository(ies) to use.',
                        default=os.environ.get('KNOWLEDGE_REPO', None))
    parser.add_argument('--knowledge-branch', dest='knowledge_branch',
                        help='The branch of the repository from which to source the knowledge_repo tools.',
                        default='master')
    parser.add_argument('--dev', action='store_true',
                        help='Whether to skip passing control to version of code checked out in knowledge repository.')
    parser.add_argument('--debug', action='store_true', help='Whether to enable debug mode.')
    parser.add_argument('--noupdate', dest='update', action='store_false',
                        help='Whether script should update the repository before performing actions.')
    parser.add_argument('--version', dest='version', action='store_true', help='Show version and exit.')
    parser.add_argument('-h', '--help', action='store_true', help='Show help and exit.')
    return parser


def handle_basic_args(parser: ArgumentParser, args: Namespace,
                      allow_exit: bool = False) -> KnowledgeRepository:
    # Show version and exit
    if args.version:
        print(f'Local version: {__version__}')
        print(f'Active version: {__version__}')
        raise SystemExit

    if args.repo is None:
        parser.print_help()
        raise ValueError("No repository specified. Please set the "
                         "--repo flag or the KNOWLEDGE_REPO environment "
                         "variable.")

    # Load repository for use in subsequent commands. It may not be possible to load
    # the repository for various reasons, such as it not existing. At this point,
    # that is okay. Later on the requirement that te repository be correctly
    # initialised will be enforced.
    try:
        repo = KnowledgeRepository.for_uri(args.repo)
    except (ValueError, GitError, ODBError):  # TODO: Generalise error to cater for all KnowledgeRepository instances.
        repo = None

    # Update repository so that we can ensure git repository configuration is up to date
    # We wrap this in a try/except block because failing to update a repository can
    # happen for all sorts of reasons that should not inhibit other actions
    # For example: if the repository does not exist and the action will be 'init'
    if repo is not None and args.update:
        if isinstance(repo, GitKnowledgeRepository):
            repo.update(branch=args.knowledge_branch)
        else:
            repo.update()

    # If not running in dev mode, and the current knowledge repository requests that
    # a specific tooling version be used, this script checks whether it is suitable
    # for running the .. the specified repo exists, along with a knowledge_repo
    # script in the .resources/scripts folder, pass execution to this script in the
    # knowledge data repo. If this *is* that script, do nothing. This still allows the `init`
    # action to be run by this script in any case. Instances of this script in a data repo
    # are assumed to be in the: '.resources/scripts/knowledge_repo', and be part of a checked
    # out instance of the complete "knowledge-repo" repository.
    if repo is not None and not args.dev and repo.config.required_tooling_version:
        required_version = repo.config.required_tooling_version
        if required_version.startswith('!'):  # Specific revision requested
            from knowledge_repo.utils.git import clone_kr_to_directory, CheckedOutRevision

            clone_kr_to_directory('~/.knowledge_repo/git')
            cmdline_args = ['--noupdate'] + [arg.replace(' ', r'\ ') if ' ' in arg else arg for arg in sys.argv[1:]]
            with CheckedOutRevision('~/.knowledge_repo/git', required_version[1:]) as script_path:
                p = os.path.join(script_path, 'scripts/knowledge_repo')
                rc = subprocess.call(f"{p} {' '.join(cmdline_args)}",
                                     shell=True)
                if rc and allow_exit:
                    sys.exit(rc)
                else:
                    raise SystemExit
        else:
            from knowledge_repo.utils.dependencies import check_dependencies

            check_dependencies([
                'knowledge_repo{}{}'.format(
                    '==' if required_version[0] not in ['<', '=', '>'] else '',
                    required_version
                )
            ])

    return repo


def create_subparser(args: Namespace, parser: ArgumentParser):
    # ---------------------------------------------------------------------------------------
    # Everything below this line pertains to actual actions to be performed on the repository
    # By now, we are guaranteed to be the script that is to perform actions on the repository,
    # so we have freedom to change and/or add options at whim, without affecting
    # interoperability.

    # Add the action parsers
    subparsers = parser.add_subparsers(help='sub-commands')

    init = subparsers.add_parser('init', help='Initialise a new knowledge repository for the specified repository.')
    init.set_defaults(action='init')

    create = subparsers.add_parser('create', help='Start a new knowledge post based on a template.')
    create.set_defaults(action='create')
    create.add_argument('--template', default=None, help='The template to use when creating the knowledge post.')
    create.add_argument('format', choices=['ipynb', 'Rmd', 'md'], help='The format of the knowledge post to be created.')
    create.add_argument('filename', help='Where this file should be created.')
    #
    drafts = subparsers.add_parser('drafts',
                                   help='Show the posts which have local work that has not been published upstream.')
    drafts.set_defaults(action='drafts')

    status = subparsers.add_parser('status',
                                   help='Provide information on the state of the repository. Useful mainly for debugging.')
    status.set_defaults(action='status')

    add = subparsers.add_parser('add',
                                help='Add a knowledge post to the repository based on the supplied file. Can be a *.ipynb, *.Rmd, or *.md file.')
    add.set_defaults(action='add')
    add.add_argument('filename', help='The filename to add.')
    add.add_argument('-p', '--path',
                     help='The path of the destination post to be added in the knowledge repo. Required if the knowledge post does not specify "path" in its headers.')
    add.add_argument('--update', action='store_true', help='Whether this should update an existing post of the same name.')
    add.add_argument('--branch',
                     help='The branch to use for this addition, if not the default (which is the path of the knowledge post).')
    add.add_argument('--squash', action='store_true',
                     help='Automatically suppress all previous commits, and replace it with this version.')
    add.add_argument('--submit', action='store_true', help='Submit newly added post')
    add.add_argument('-m', '--message', help='The commit message to be used when committing into the repo.')
    add.add_argument('--src', nargs='+', help='Specify additional source files to add to <knowledge_post>/orig_src.')

    submit = subparsers.add_parser('submit', help='Submit a knowledge post for review.')
    submit.set_defaults(action='submit')
    submit.add_argument('path', help='The path of the knowledge post to submit for review.')

    push = subparsers.add_parser('push', help='DEPRECATED: Use `submit` instead.')
    push.set_defaults(action='push')
    push.add_argument('path', help='The path of the knowledge post to submit for review.')

    preview = subparsers.add_parser('preview',
                                    help='Run the knowledge repo app, and preview the specified post. It is assumed it is available on the currently checked out branch.')
    preview.set_defaults(action='preview')
    preview.add_argument('path', help="The path of the knowledge post to preview.")
    preview.add_argument('--port', default=7000, type=int, help="Specify the port on which to run the web server")
    preview.add_argument('--dburi', help='The SQLAlchemy database uri.')
    preview.add_argument('--config', default=None)

    # Developer and server side actions
    runserver = subparsers.add_parser('runserver', help='Run the knowledge repo app.')
    runserver.set_defaults(action='runserver')
    runserver.add_argument('--port', default=7000, type=int, help="Specify the port on which to run the web server")
    runserver.add_argument('--dburi', help='The SQLAlchemy database uri.')
    runserver.add_argument('--config', default=None)

    deploy = subparsers.add_parser('deploy', help='Deploy the knowledge repo app using gunicorn.')
    deploy.set_defaults(action='deploy')
    deploy.add_argument('-p', '--port', default=7000, type=int, help="Specify the port on which to run the web server")
    deploy.add_argument('-w', '--workers', default=4, type=int, help="Number of gunicorn worker threads to spin up.")
    deploy.add_argument('-t', '--timeout', default=60, type=int,
                        help="Specify the timeout (seconds) for the gunicorn web server")
    deploy.add_argument('-db', '--dburi', help='The SQLAlchemy database uri.')
    deploy.add_argument('-c', '--config', default=None, help="The config file from which to read server configuration.")
    deploy.add_argument('--engine', default='gunicorn',
                        help='Which server engine to use when deploying; choose from: "flask", "gunicorn" (default) or "uwsgi".')

    db_upgrade = subparsers.add_parser('db_upgrade',
                                       help='Upgrade the database to the latest schema. Only necessary if you have disabled automatic migrations in your deployment.')
    db_upgrade.set_defaults(action='db_upgrade')
    db_upgrade.add_argument('-db', '--dburi', help='The SQLAlchemy database uri.')
    db_upgrade.add_argument('-c', '--config', default=None, help="The config file from which to read server configuration.")
    db_upgrade.add_argument('-m', '--message', help="The message to use for the database revision.")
    db_upgrade.add_argument('--autogenerate', action='store_true',
                            help="Whether alembic should automatically populate the migration script.")

    db_downgrade = subparsers.add_parser('db_downgrade',
                                         help='Downgrade the database to the schema identified by a revision number.')
    db_downgrade.set_defaults(action='db_downgrade')
    db_downgrade.add_argument('revision', help="The target database revision. Use '-1' for the previous version.")
    db_downgrade.add_argument('-db', '--dburi', help='The SQLAlchemy database uri.')
    db_downgrade.add_argument('-c', '--config', default=None,
                              help="The config file from which to read server configuration.")

    reindex = subparsers.add_parser('reindex',
                                    help='Update the index, updating all posts even if they exist in the database already; but will not lose post views and other usage metadata.')
    reindex.set_defaults(action='reindex')
    reindex.add_argument('-db', '--dburi', help='The SQLAlchemy database uri.')
    reindex.add_argument('-c', '--config', default=None, help="The config file from which to read server configuration.")

    # Only show db_migrate option if running in development mode, and in a git repository.
    if args.dev and os.path.exists(str(script_dir.parent.parent / '.git')):
        db_migrate = subparsers.add_parser('db_migrate', help='Create a new alembic revision.')
        db_migrate.set_defaults(action='db_migrate')
        db_migrate.add_argument('message', help="The message to use for the database revision.")
        db_migrate.add_argument('-db', '--dburi', help='The SQLAlchemy database uri.')
        db_migrate.add_argument('--autogenerate', action='store_true',
                                help="Whether alembic should automatically populate the migration script.")


def parse_args(args: Sequence[str] = None, allow_exit: bool = True):
    parser = create_args()
    parsedargs, remaining_args = parser.parse_known_args(args)
    try:
        repo = handle_basic_args(parser, parsedargs, allow_exit)
    except SystemExit:
        if allow_exit:
            sys.exit(0)
    else:
        create_subparser(parsedargs, parser)
        parsedargs = parser.parse_args(args)
        if not hasattr(parsedargs, 'action'):
            parser.print_help()
            if allow_exit:
                sys.exit(1)
            else:
                return

        return parsedargs, repo


def init(uri: str):
    assert not isinstance(uri, dict), "Only one repository can be initialised at a time."
    repo = KnowledgeRepository.create_for_uri(uri)
    if repo is not None:
        print("Knowledge repository successfully initialized for uri "
              f"`{repo.uri}`.")
    else:
        print("Something weird happened while creating repository for uri "
              f"`{uri}`. Please report!")


def create(format: str, filename: str, template: str = None):
    pkg = Path(__file__).parent.parent
    src = pkg/'templates'/f'knowledge_template.{format}'
    if template:
        src = template
    if not os.path.exists(src):
        raise ValueError(f"Template not found at {src}. Please choose a different template and try again.")
    if os.path.exists(filename):
        raise ValueError(f"File already exists at '{filename}'. Please choose a different filename and try again.")
    shutil.copy(src, filename)
    print(f"Created a {format} knowledge post template at '{filename}'.")


def drafts(repo: KnowledgeRepository):
    statuses = repo.post_statuses(
        repo.dir(status=[repo.PostStatus.DRAFT,
                         repo.PostStatus.SUBMITTED,
                         repo.PostStatus.UNPUBLISHED]),
        detailed=True,
    )
    print(tabulate(
        [[path, status.name, details]
         for path, (status, details) in statuses.items()],
        ['Post', 'Status', 'Details'],
        'fancy_grid'
    ))


def status(repo: KnowledgeRepository, uri: Union[str, dict]):
    status = repo.status_message
    if isinstance(uri, dict):
        print("\n-----\n".join([f'Repository: {name}\n{message}'
                                for name, message in status.items()]))
    else:
        print(status)


def add(repo: KnowledgeRepository, filename: str, path: str,
        update: bool = False, branch: str = None, message: str = None, squash: bool = False, src: List[str] = None):
    kp = KnowledgePost.from_file(filename, src_paths=src)
    repo.add(kp, path=path, update=update, branch=branch, message=message,
             squash=squash)


def serve(action: str, repo: KnowledgeRepository, uri: str, debug: bool,
          dburi: str, config: str, port: int, preview_path: str = None,
          engine: str = 'flask', workers: int = None, timeout: int = None):
    app_builder = get_app_builder(
        uri,
        debug=debug,
        db_uri=dburi,
        config=config,
        INDEXING_ENABLED=action != 'preview'
    )

    if action == 'preview':
        kp_path = repo._kp_path(preview_path)
        repo.set_active_draft(kp_path)  # TODO: Deprecate
        url = f'http://127.0.0.1:{port}/post/{kp_path}'
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()

    server_kwargs = dict()
    if workers is not None:
        server_kwargs['workers'] = workers

    if timeout is not None:
        server_kwargs['timeout'] = timeout

    run_kwargs = dict()
    if engine == 'flask':
        run_kwargs['use_reloader'] = debug and action != 'preview'

    return KnowledgeDeployer.using(engine)(
        app_builder,
        host='0.0.0.0',
        port=port,
        **server_kwargs
    ).run(**run_kwargs)


def db_migrate(repo: KnowledgeRepository, debug: bool, dburi: str,
               message: str, autogenerate: bool):
    app = repo.get_app(debug=debug, db_uri=dburi)
    app.db_migrate(message, autogenerate=autogenerate)


def reindex(app: KnowledgeFlask):
    app.db_update_index(check_timeouts=False, force=True, reindex=True)


def repo_app(repo: KnowledgeRepository, dburi: str = None, debug: bool = False,
             config: str = None):
    return repo.get_app(db_uri=dburi, debug=debug, config=config)


def handle_args(args: Namespace, repo: KnowledgeRepository):
    uri = args.repo
    action = args.action

    # If init, use this code to create a new repository.
    if action == 'init':
        init(uri)
        raise SystemExit

    # All subsequent actions perform an action on the repository, and so we
    # enforce that `repo` is not None.
    if repo is None:
        raise RuntimeError(
            f"Could not initialise knowledge repository for uri `{uri}`."
            " Please check the uri, and try again."
        )

    # Create a new knowledge post from a template
    if action == 'create':
        create(args.format, args.filename, args.template)
        raise SystemExit

    # # Check which branches have local work
    if action == 'drafts':
        drafts(repo)
        raise SystemExit

    if action == 'status':
        status(repo, uri)
        raise SystemExit

    # Add a document to the data repository
    if action == 'add':
        add(repo, args.filename, path=args.path, update=args.update,
            branch=args.branch, message=args.message, squash=args.squash,
            src=args.src)
        if not args.submit:
            raise SystemExit

    if action in ('submit', 'push') or (action == 'add' and args.submit):
        if args.action == 'push':
            print("WARNING: The `push` action is deprecated, and you are "
                  "encouraged to use `knowledge_repo submit <path>` instead.")
        repo.submit(path=args.path)
        raise SystemExit

    # Everything below this point has to do with running and/or managing the web app
    if action in ['preview', 'runserver', 'deploy']:
        engine = args.engine if action == 'deploy' else 'flask'
        serve(action, repo, uri, args.debug, args.dburi, args.config,
              args.port, args.path, engine, args.workers, args.timeout)
        raise SystemExit

    if action == 'db_migrate':
        db_migrate(repo, debug=args.debug, db_uri=args.dburi,
                   message=args.message, autogenerate=args.autogenerate)
        raise SystemExit

    app = repo_app(repo, args.dburi, args.debug, args.config)
    if action == 'db_upgrade':
        app.db_upgrade()

    elif action == 'db_downgrade':
        app.db_downgrade(revision=args.revision)

    elif action == 'reindex':
        reindex(app)


def process(args: Sequence[str] = None, allow_exit: bool = False):
    x = parse_args(args, allow_exit)
    if x:
        try:
            return handle_args(*x)
        except SystemExit:
            if allow_exit:
                sys.exit(0)


def main():
    # Register handler for SIGTERM, so we can run cleanup code if terminated
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    process(allow_exit=True)


if __name__ == '__main__':
    main()
