import os
import subprocess

__all__ = [
    "__author__",
    "__author_email__",
    "__version__",
    "__git_uri__",
    "__dependencies__",
    "__optional_dependencies__",
]

__author__ = """
    Erik Ritter (maintainer),
    Henry Wu,
    Jing Guo,
    Mengting Li,
    John Bodley,
    Bill Ulammandakh,
    Naoya Kanai,
    Robert Chang,
    Dan Frank,
    Chetan Sharma,
    Matthew Wardrop,
    Randy Eckman
    """

__author_email__ = """
    erik.ritter@airbnb.com,
    henry.wu@airbnb.com,
    jing.guo@airbnb.com,
    mengting.li@airbnb.com,
    john.bodley@airbnb.com,
    bill.ulammandakh@airbnb.com,
    naoya.kanai@airbnb.com,
    robert.chang@airbnb.com,
    dan.frank@airbnb.com,
    chetan.sharma@airbnb.com,
    mpwardrop@gmail.com,
    emanspeaks _at_ gmail.com
    """

__version__ = "1.0.0"

try:
    with open(os.devnull, "w") as devnull:
        __version__ += "_" + subprocess.check_output(
            ["git", "rev-parse", "HEAD"], shell=False, stderr=devnull
        ).decode("utf-8").replace("\n", "")
except Exception as e:
    print(f"Exception encountered: {e}")
    pass

__git_uri__ = "https://github.com/emanspeaks/knowledge-repo.git"

# These are the core dependencies, and should include all packages needed
# for accessing repositories and running a non-server-side instance of the
# flask application. Optional dependencies for converters/etc should be
# defined elsewhere.
__dependencies__ = [
    # Knowledge Repository Dependencies
    "pyyaml>=6.0",  # Yaml parser and utilities
    "markdown>=3.3.4",  # Markdown conversion utilities
    "pygments>=2.10.0",  # Code highlighting support in markdown
    "gitpython>=3.1",  # Git abstraction
    "tabulate>=0.8.9",  # Rendering prettily in knowledge_repo script
    "cooked_input",  # Used for interactive input from user in CLI tooling
    "requests",  # Used for downloading images
    "ipython_genutils",  # Used by Markdown conversion utilities
    "multiprocess",  # Temp solutuion to fix serilization issue
    "importlib-metadata",

    # Flask App Dependencies
    "flask",  # Main flask framework
    "flask_login",  # User management framework
    "flask_principal",  # Permissions management framework
    "flask_mail",  # Mail client and utilities
    "Flask-Migrate",  # Database migration utilities
    "sqlalchemy>=1.4.37",  # Database abstractions
    "jinja2>=2.7",  # Templating engine
    "werkzeug>=1.0",  # Development webserver
    "gunicorn",  # Deployed webserver
    "inflection",  # String transformation library
    "pillow",  # Image thumbnailing
    "weasyprint>=54.3",  # Post PDF download option
    "gcloud>=0.18.3",  # google cloud storage integration
    "botocore>=1.29.37",  # aws s3 integration
    "boto3>=1.26.37",  # aws s3 integration
    "s3path>=0.3.4",  # aws s3 path analysis
    "notion-client>=2.0.0",  # notion integration
]

__optional_dependencies__ = {
    # ipynb notebook conversion suport
    "ipynb": ["nbformat", "nbconvert[execute]", "traitlets"],

    # PDF to image conversion used by app
    "pdf": [
        "PyPDF2>=2.1.1",  # image for parsing PDFs to images
        "wand>=0.6.7",  # imagemagick integration for image uploading
    ],

    # Optional OAuth library for external authentication support
    "oauth": ["requests_oauthlib"],

    # Optional ldap library for ldap authentication
    "ldap": ["ldap3"],
    # Testing dependencies

    "dev": [
        "beautifulsoup4",  # HTML/XML parser
        "coverage",  # Documentation coverage tester
        "nose",  # Testing framework
        "pep8",  # PEP8
        "pycodestyle",  # PEP8 conformance
    ],
}

__optional_dependencies__["all"] = [
    dep for deps in __optional_dependencies__.values() for dep in deps
]
