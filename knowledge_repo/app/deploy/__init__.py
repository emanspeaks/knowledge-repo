import logging  # noqa: F401

from .common import KnowledgeDeployer, get_app_builder  # noqa: F401

# The following subclasses of KnowledgeDeployer must be
# imported in order to be registered as a deployer and hence
# made accessible using `KnowledgeDeployer.using(..)`.
from .flask import FlaskDeployer  # noqa: F401
from .uwsgi import uWSGIDeployer  # noqa: F401

# Wrap the gunicorn deployer in a try/except block, as it
# has a hard dependency on gunicorn which does not work on
# non-POSIX systems, or if it is not installed.
try:
    from .gunicorn import GunicornDeployer  # noqa: F401
except ImportError:
    pass
