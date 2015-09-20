crowdjs-server
==============

## Development configuration
- Create and activate a Python virtual environment. https://github.com/yyuu/pyenv and https://github.com/yyuu/pyenv-virtualenv are useful tools for this.
- Load application dependencies into the Python virtual environment by running `pip install -r requirements.txt`.
- Set up a MongoDB database. One option is to create a free Heroku instance with a MongoLab sandbox add-on.
- Create a `.env` file in the root directory with the following lines (substitute `db_user`, `db_password`, `host`, and `port` with details of your development MongoDB connection; substitute `zmdp` with the alias for running the ZMDP solver):
```
MONGOLAB_URI=mongodb://db_user:db_password@host:port
APP_SETTINGS='config.DevelopmentConfig'
ZMDP_ALIAS=zmdp
```

## Additional configuration
To set up Heroku environment to run ZMDP, add the following buildpacks, using the toolbelt command `heroku buildpacks add` or equivalent:

1. https://github.com/heroku/heroku-buildpack-python
2. https://github.com/jbragg/heroku-buildpack-zmdp.git

## Run instructions
- Run the application using either `heroku local` (if using Heroku) or `./run.sh .env -b host:port`.
- Run tests using either `heroku local -f Procfile.test` (if using Heroku) or `./run_tests.sh .env`.
