IF NOT DEFINED PYTHON (SET PYTHON=python)

REM Run pep8 tests
%PYTHON%\\python.exe -m pycodestyle knowledge_repo scripts tests setup.py --exclude knowledge_repo/app/migrations,tests/test_repo --ignore=E501,E722,W504

REM Create fake repository and add some sample posts.
%PYTHON%\\python.exe prep_tests.py

REM "Running regression test suite"
%PYTHON%\\python.exe -m nose --with-coverage --cover-package=knowledge_repo --verbosity=1
