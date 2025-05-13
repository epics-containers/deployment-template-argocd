# deployment-template-argocd
A template for deploying services using argocd

## To create a new deployment repository

Activate a Python virtual environment, then:

```bash
pip install copier
# this will create a new folder MY_REPO_NAME:
copier copy https://github.com/epics-containers/deployment-template-argocd MY_REPO_NAME
```
You will be asked for a few details and the resulting project is ready to push.
Make the first commit and push the repository.

```bash
cd MY_REPO_NAME
git init -b main
git add .
git commit -m "initial commit"
git remote add origin >>>>paste your repo ssh address here<<<<
git push -u origin main
```

## To update an existing deployment repo

Again you will need a virtual environment with `copier` installed.
cd into the project you wish to update and execute the following:

```bash
copier update .
```
