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
    SECURITY_REGISTERABLE = True
    SECURITY_PASSWORD_HASH = 'sha512_crypt'
    SECURITY_PASSWORD_SALT = 'abcde'

class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    TESTING = True

class Production(Config):
    DEBUG = False
