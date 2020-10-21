#!/usr/bin/env python
import cherrypy
import random
import string
import time

TOKEN_LENGTH = 20
TOKEN_DURATION = 60 * 60 * 2 # 2 hours
VALID_TOKEN_CHARS = string.ascii_letters + string.digits


class Token(object):
    def __init__(self, value: str, roles: list):
        self.value = value
        self.roles = roles
        self.roles_remaining = roles.copy()
        self.time_created = time.time()
        self.role_assignments = {}

    def is_roles_remaining(self):
        return len(self.role_assignments) < len(self.roles)

    def is_token_expired(self):
        return self.time_created + TOKEN_DURATION < time.time()

    def get_role(self, session_id: str):
        # If there are roles left and this session_id is new to us than assign him one
        if self.is_roles_remaining() and self.role_assignments.get(session_id) is None:
            self.role_assignments[session_id] = self.pop_role()
            return self.role_assignments[session_id]

        # Returns this users role if they have on already
        # or None if this user doesn't have one still
        return self.role_assignments.get(session_id)

    def pop_role(self):
        # Scramble and pop
        random.shuffle(self.roles_remaining)
        return self.roles_remaining.pop()

class HelloWorld(object):
    def __init__(self):
        self.openTokens = {}

    @cherrypy.expose
    def index(self):
        return '<script>window.location.replace("/generate");</script>'

    def generate_session_id(self):
        session_str = ''.join(random.choices(VALID_TOKEN_CHARS, k=20))
        return session_str

    def generate_token(self, length: int, roles: list):
        token_str = ''.join(random.choices(VALID_TOKEN_CHARS, k=length))
        token = Token(token_str, roles)
        return token

    def cleanup_expired_tokens(self):
        expired_tokens = {token_str: token for token_str, token in self.openTokens.items() if
                           token.is_token_expired()}
        print(f"Cleaning up tokens. Expired tokens {expired_tokens}")
        print(f"len(self.openTokens) = {len(self.openTokens)}")
        self.openTokens = {token_str: token for token_str, token in self.openTokens.items() if not token.is_token_expired()}

    @cherrypy.expose
    def generate(self, roles=None):
        if roles == None:
            with open("generate_form.html", 'r') as f:
                return f.read()
        else:
            roles_list = roles.split(',')
            print(roles_list)
            token = self.generate_token(TOKEN_LENGTH, roles_list)
            self.openTokens[token.value] = token
            url = f"landing?token={token.value}"
            hostname = cherrypy.request.base
            return f"Share this link with the other players. It work for 2 hours. <a href={url}>{hostname}/{url}</a>"

    @cherrypy.expose
    def landing(self, token=None):
        with open("landing.html") as f:
            return f.read()

    @cherrypy.expose
    def join(self, token=None):
        if token is None:
            return '{"message": "token not found. You have to connect to /join?token=yourTokenHere. Go to /generate to create one."}'
        if token not in self.openTokens:
            return '{"message": "token invalid. Maybe you missed some of the token when copying?"}'
        token_obj = self.openTokens[token]

        if token_obj.is_token_expired():
            return '{"message":"token expired :("}'

        session_id = cherrypy.session.get('session_id')
        # If this user doesn't have a session_id yet then give them one
        if session_id is None:
            session_id = self.generate_session_id()
            cherrypy.session['session_id'] = session_id

        role = token_obj.get_role(session_id)

        # If role is none then all roles have been used
        # Maybe this user quit their session and has opened a new one
        # If so, too bad :(
        if role is None:
            return '{"message":"all roles taken. Perhaps you closed your browser and tried to reopen a link? (you can only see your role again if you have the same browser session open)"}'
        else:
            return f'{{"message": "Your role is {role}."}}'

conf = {
    'global': {
        'server.socket_host': '0.0.0.0'
    },
    '/': {
        'tools.sessions.on': True,
    }
}
instance = HelloWorld()
# Every minute
cleanup = cherrypy.process.plugins.BackgroundTask(60, instance.cleanup_expired_tokens)
cleanup.start()
cherrypy.quickstart(instance, '/', conf)
