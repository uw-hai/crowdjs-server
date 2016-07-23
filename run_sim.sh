# run controller simulation from project root dir, command-line args can be passed in
ENV_FILE=.env
env $(cat $ENV_FILE | xargs) python -m alt_simulator $@
