import os

class Config(object):
    DEBUG = False
    TESTING = False

    mongolab_uri = os.environ['MONGOLAB_URI'].split('/')
    (dbuser, dbpass_host, port) = mongolab_uri[2].split(':')
    (dbpass, host) = dbpass_host.split('@')
    dbname = mongolab_uri[3]

    MONGODB_SETTINGS = {    
        'db': dbname,
        'host': host,
        'port': int(port),
        'username' : dbuser,
        'password' : dbpass}

    SECRET_KEY = 'super-secret'

class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True

class Production(Config):
    DEBUG = False
