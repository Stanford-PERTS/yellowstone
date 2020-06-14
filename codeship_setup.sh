#!/bin/bash

# Commands to be run during a codeship build.
# In a codeship project, in the Setup Commands window, enter this:

# chmod +x codeship_setup.sh && ./codeship_setup.sh

# This ensures that lines which have an error cause this whole script to
# exit with an error.
# http://stackoverflow.com/questions/3474526/stop-on-first-error
set -e

if [ "$CI" = "true" ]
then
  # Codeship checks out the HEAD of the request branch directly, rather than
  # checking out the branch name, which results in a detached HEAD state. This
  # makes other git commands and git-related grunt tasks (e.g. githash) not
  # work nicely. Fix it by explicitly checking out the requested branch.
  git checkout $CI_BRANCH

  # Tell Codeship to cache globally-installed dependencies, so it doesn't take
  # too long to update npm.
  # https://documentation.codeship.com/basic/languages-frameworks/nodejs/#dependency-cache
  npm config set cache "${HOME}/cache/npm/"
  export PATH="${HOME}/cache/npm/bin/:${PATH}"
  export PREFIX="${HOME}/cache/npm/"
fi

# Run a custom python script to compile branch-specific config files.
pip install --user 'ruamel.yaml<0.15'
pip install --user webtest
python branch_environment.py

# Codeship does not automatically keep npm up to date; update it here.
# https://documentation.codeship.com/basic/languages-frameworks/nodejs/#dependencies
npm install -g npm@latest

# Install all the node stuff, faster, based on package-lock.json, omitting
# things mentioned in `devDependencies`.
# https://blog.npmjs.org/post/171556855892/introducing-npm-ci-for-faster-more-reliable
npm ci --only=production

npm run sass:build
