# deployment-template-argocd
A template for deploying services using argocd

## To create a new deployment repository

Activate a Python virtual environment, then:

```bash
pip install copier
# this will create a new folder MY_REPO_NAME:
copier copy gh:epics-containers/deployment-template-argocd --trust MY_REPO_NAME
```
You will be asked for a few details and the resulting project is ready to push.

## To update an existing deployment repo

Again you will need a virtual environment with `copier` installed.
cd into the project you wish to update and execute the following:

```bash
copier update --trust .
```
