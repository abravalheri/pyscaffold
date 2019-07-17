#!/bin/bash
# This script is meant to be called by the "install" step defined in
# .travis.yml. See http://docs.travis-ci.com/ for more details.
# The behavior of the script is controlled by environment variabled defined
# in the .travis.yml in the top level folder of the project.
#
# This script is inspired by Scikit-Learn (http://scikit-learn.org/)
#

set -e -x

if [[ "${TRAVIS_OS_NAME}" == "osx" ]]; then
    export HOMEBREW_LOGS="${TRAVIS_BUILD_DIR}/var/log"
    export HOMEBREW_TEMP="${TRAVIS_BUILD_DIR}/var/tmp"
    export PYTHON_BUILD_CACHE_PATH="$HOME/.cache/pyenv"
    mkdir -p "${HOMEBREW_LOGS}" "${HOMEBREW_TEMP}" "${PYTHON_BUILD_CACHE_PATH}"
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    version=$(pyenv install --list | grep -e "^\s\+${PYTHON_VERSION}" | sort | awk 'END{print $1}')
    pyenv install --skip-existing "${version}"
    pyenv global "${version}"
    pyenv rehash
    python -m pip install --user virtualenv
    virtualenv testenv
    source testenv/bin/activate
fi

if [[ "${DISTRIB}" == "conda" ]]; then
    # Deactivate the travis-provided virtual environment and setup a
    # conda-based environment instead
    deactivate

    if [[ -f "$HOME/miniconda/bin/conda" ]]; then
        echo "Skip install conda [cached]"
    else
        # By default, travis caching mechanism creates an empty dir in the
        # beginning of the build, but conda installer aborts if it finds an
        # existing folder, so let's just remove it:
        rm -rf "$HOME/miniconda"

        # Use the miniconda installer for faster download / install of conda
        # itself
        wget http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
            -O miniconda.sh
        chmod +x miniconda.sh && ./miniconda.sh -b -p $HOME/miniconda
    fi
    export PATH=$HOME/miniconda/bin:$PATH
    # Make sure to use the most updated version
    conda update --yes conda

    # Configure the conda environment and put it in the path using the
    # provided versions
    # (prefer local venv, since the miniconda folder is cached)
    conda create -p ./.venv --yes python="${PYTHON_VERSION}" pip virtualenv
    source activate ./.venv
    conda list
fi

# for all
pip install -U pip setuptools
pip install sphinx
pip install tox

if [[ "${COVERAGE}" == "true" ]]; then
    pip install -U pytest-cov pytest-virtualenv coverage coveralls flake8 pre-commit
fi

travis-cleanup() {
    printf "Cleaning up environments ... "  # printf avoids new lines
    if [[ "$DISTRIB" == "conda" ]]; then
        # Force the env to be recreated next time, for build consistency
        source deactivate
        conda remove -p ./.venv --all --yes
        rm -rf ./.venv
    fi
    echo "DONE"
}
