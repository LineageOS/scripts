# LineageOS Gitlab issues cleanup script

Cleans up Gitlab issues based on some factors:
- Keeps all issues labeled "platform" and "platform-atv"
- Closes all issues for devices which don't receive any builds
- Closes all issues for older branches than the current one a device gets built for

## Setup

Login to Gitlab, go to your account settings and choose `Access tokens`.
Create a new token with scope `API` and store it in an environment variable named `GITLAB_TOKEN` or assign it temporarily with

```export GITLAB_TOKEN=<your Token>```

before calling the script

## Usage

usage: cleanup.py


