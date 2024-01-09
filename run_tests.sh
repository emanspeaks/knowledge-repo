#!/usr/bin/env bash

echo
echo "Setting up test environment"
echo "---------------------------"
echo

echo "Removing artifacts from previous testing..."
rm tests/knowledge.db &> /dev/null
rm -f .coverage &> /dev/null

# Exit script if any command returns a non-zero status hereonin
set -e

# Run pep8 tests
pycodestyle knowledge_repo scripts tests setup.py --exclude knowledge_repo/app/migrations,tests/test_repo --ignore=E203,E501,E722,W503,W504

python prep_tests.py

echo
echo "Running regression test suite"
echo "-----------------------------"
echo
nosetests --with-coverage --cover-package=knowledge_repo --verbosity=1 -a '!notest'
