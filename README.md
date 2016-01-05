crowdjs-server
==============

## Development configuration
- Create and activate a Python virtual environment. https://github.com/yyuu/pyenv and https://github.com/yyuu/pyenv-virtualenv are useful tools for this.
- Load application dependencies into the Python virtual environment by running `pip install -r requirements.txt`.
- This repository contains git submodules. Run `git submodule init` and `git submodule update` to fetch these.
- Set up a MongoDB database. One option is to create a free Heroku instance with a MongoLab sandbox add-on.
- Create a `.env` file in the root directory with the following lines (substitute `db_user`, `db_password`, `host`, and `port` with details of your development MongoDB connection; install zmdp using the zmdp submodule, and substitute `zmdp` with the alias for running the ZMDP solver. ):
```
MONGOLAB_URI=mongodb://db_user:db_password@host:port
APP_SETTINGS='config.DevelopmentConfig'
ZMDP_ALIAS=zmdp
```
- Create a production version `.production-env` that uses the production configuration.
```
APP_SETTINGS='config.Production'
```

## Additional configuration
To set up Heroku environment to run ZMDP, add the following buildpacks, using the toolbelt command `heroku buildpacks:add` or equivalent:

1. https://github.com/heroku/heroku-buildpack-python
2. https://github.com/jbragg/heroku-buildpack-zmdp.git

## Run instructions
- Run the application using either `heroku local` (if using Heroku) or `./run.sh .env -b host:port`.

## Testing instructions
- Use `heroku local -f Procfile.test` (if using Heroku) or
- Be sure to run both `./run_tests.sh .env` AND `./run_tests.sh .production-env` to test both dev and production environments.
