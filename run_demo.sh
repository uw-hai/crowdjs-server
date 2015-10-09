# usage: ./run_demo.sh .env <server_address:port>
env $(cat $1 | xargs) python populate_db.py ${@:2}
