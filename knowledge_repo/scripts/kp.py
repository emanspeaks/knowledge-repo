#!/usr/bin/env python

import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import cooked_input as ci


def main():
    # If this script is being run out of a checked out `knowledge-repo` repository,
    # we need to make sure the appropriate knowledge_repo package is being used. To
    # do this, we add the parent directory of the folder containing this script if
    # it contains a python package named "knowledge_repo".
    script_dir = Path(__file__).parent
    if script_dir.parent.name == 'knowledge_repo':
        sys.path.insert(0, str(script_dir.parent.parent))

    import knowledge_repo  # nopep8
    from knowledge_repo import KnowledgePost  # nopep8

    # Build argparser

    parser = argparse.ArgumentParser(add_help=False,
                                     description='Tooling to aid with the authoring and submission of knowledge posts.')
    parser.add_argument('--version', dest='version', action='store_true', help='Show version and exit.')
    parser.add_argument('--non-interactive', dest='interactive', action='store_false',
                        help='Run scripts in non-interactive mode.')
    parser.add_argument('-h', '--help', action='store_true', help='Show help and exit.')

    args, remaining_args = parser.parse_known_args()

    if args.version:
        print('{}'.format(knowledge_repo.__version__))
        sys.exit(0)

    # ------------------------------------------------------------------------------
    # Everything below this line pertains to actions to be performed on a specific
    # knowledge post.

    parser.add_argument('post_path', help='The path of an existing knowledge post, or the target for a new knowledge post.')

    # Add the action parsers
    subparsers = parser.add_subparsers(help='actions')

    from_ = subparsers.add_parser('from', help='Create a knowledge post from an existing document.')
    from_.set_defaults(action='from')
    from_.add_argument('source', help='The path or url of the source file.')
    from_.add_argument('--format',
                       help='The format to assume for the source file (overriding default detection algorithms).')
    from_.add_argument('--src', nargs='+', help='Specify additional files to be added as source files.')
    from_.add_argument('--overwrite', action='store_true', help='Overwrite any existing knowledge post.')

    to = subparsers.add_parser('to', help='Export a knowledge post as another format.')
    to.set_defaults(action='to')
    to.add_argument('target', help='The path or url of the target location.')
    to.add_argument('--format', help='The target format (overrides default detection algorithms).')

    preview = subparsers.add_parser('preview', help='Preview a knowledge post in a local web server.')
    preview.set_defaults(action='preview')

    submit = subparsers.add_parser('submit', help='Submit a knowledge post to a nominated repository.')
    submit.set_defaults(action='submit')
    submit.add_argument(
        'repo', nargs='?', default=os.environ.get('KNOWLEDGE_REPO'),
        help=(
            "The repository into which the post should be submitted. (Defaults to "
            "$KNOWLEDGE_REPO, which is currently {})".format(
                os.environ['KNOWLEDGE_REPO'].__repr__() if 'KNOWLEDGE_REPO' in os.environ else 'unset'
            )
        )
    )
    submit.add_argument(
        'path', help="The path of the post within the repository."
    )
    submit.add_argument('--update', action='store_true',
                        help='Whether this post should replace existing posts at the same path.')
    submit.add_argument('--message', help="A commit message describing this post and/or its changes.")

    args = parser.parse_args()

    if args.help:
        parser.print_help()
        sys.exit(0)

    if not args.post_path.endswith('.kp'):
        args.post_path += '.kp'

    if args.action == 'from':
        if not args.overwrite and os.path.exists(args.post_path):
            if args.interactive:
                args.overwrite = ci.get_boolean(
                    prompt="File already exists at '{}'. Do you want to overwrite it? (y/n)".format(args.post_path))
            if not args.overwrite:
                raise RuntimeError(
                    "File already exists at '{}', but the `overwrite` flag is not set.".format(args.post_path))
        kp = KnowledgePost.from_file(args.source, format=args.format, src_paths=args.src, interactive=args.interactive)
        kp.to_file(args.post_path, format='kp')
        sys.exit(0)

    # ------------------------------------------------------------------------------
    # Everything below this line requires the knowledge post to already exist to
    # actions to be performed on a specific knowledge post.
    if not os.path.exists(args.post_path):
        raise IOError("Knowledge post does not exist at '{}'.".format(os.path.abspath(args.post_path)))

    kp = KnowledgePost.from_file(args.post_path, format='kp', interactive=args.interactive)

    if args.action == 'to':
        kp.to_file(args.target, format=args.format)
        sys.exit(0)

    if args.action == 'preview':
        from knowledge_repo.app.deploy import KnowledgeDeployer, get_app_builder

        def get_available_port():
            s = socket.socket()
            s.bind(("", 0))
            free_port = s.getsockname()[1]
            s.close()
            return free_port

        port = get_available_port()

        post_path = os.path.abspath(args.post_path)
        repo_dir = os.path.dirname(post_path)
        post_path = os.path.basename(post_path)

        app_builder = get_app_builder('file://' + repo_dir,
                                      debug=False,
                                      db_uri='sqlite:///:memory:',
                                      config=None,
                                      INDEXING_ENABLED=False)

        url = 'http://localhost:{}/post/{}'.format(port, post_path)
        print(
            f"Previewing knowledge post at: {url}\n\n"
            "If you are using `kp` locally, a browser window will shortly open at "
            "this address. Otherwise, please replace `localhost` with the hostname "
            "of the server upon which you are running this script, and manually "
            "point your browser at the resulting url.\n\n"
            "When you are ready to exit the preview, simply kill this process using "
            "`<Ctrl> + C`.\n"
        )
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()

        KnowledgeDeployer.using('flask')(
            app_builder,
            host='0.0.0.0',
            port=port
        ).run()
        sys.exit(0)

    if args.action == 'submit':
        if not args.repo:
            raise RuntimeError("Repository not specified.")
        repo = knowledge_repo.KnowledgeRepository.for_uri(args.repo)

        repo.add(kp, path=args.path, update=args.update, message=args.message)
        repo.submit(args.path)
        sys.exit(0)


if __name__ == '__main__':
    main()
