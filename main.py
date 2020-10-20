#!/usr/bin/env python
import cherrypy
import random
import string
import time

TOKEN_LENGTH = 20
TOKEN_DURATION = 60 * 10 # 5 minutes
CHECKIN_DURATION = 60 * 1 # 1 minutes
HOSTNAME = cherrypy.url()
VALID_TOKEN_CHARS = string.ascii_letters + string.digits


class Token(object):
    def __init__(self, value: str, roles: list):
        self.value = value
        self.roles = roles
        self.roles_remaining = roles.copy()
        self.time_created = time.time()
        self.checkins = {}
        self.checkins_locked = False

    def lock_checkins(self):
        self.checkins_locked = True

    def checkins_complete(self):
        # If the checkins are locked then people should be able to go back to the /join page
        # and see there role again (as long as they haven't quit the session)
        # So until the token expires they're checkin should stay locked to this token
        # and never get removed
        if not self.checkins_locked:
            # Filter out any expired checkins
            self.checkins = {checkin_str: checkin for checkin_str, checkin in self.checkins.items() if
                             not checkin.is_timedout()}

        if len(self.checkins.values()) < len(self.roles):
            print("Not all players have joined")
            return False
        elif len(self.checkins.values()) > len(self.roles):
            print("More than expected number of players have joined")
            return False
        print("Checkins complete")

        self.lock_checkins()
        return True

    def is_token_expired(self):
        return self.time_created + TOKEN_DURATION < time.time()

    def get_role(self, checkin_id: str):
        if self.checkins.get(checkin_id) is None:
            raise ValueError(f"No checkin_id {checkin_id} for this token.")

        # If this user hasn't been assigned a role yet then assign them one
        if self.checkins[checkin_id].role_assignment is None:
            print("Assigning role")
            self.checkins[checkin_id].role_assignment = self.pop_role()

        # Return the role they've been assigned
        return self.checkins[checkin_id].role_assignment

    def pop_role(self):
        # Scramble and pop
        random.shuffle(self.roles_remaining)
        return self.roles_remaining.pop()

class Checkin(object):
    def __init__(self, id: str):
        self.id = id
        self.last_checkin = time.time()
        self.role_assignment = None

    def checkin(self):
        self.last_checkin = time.time()

    def is_timedout(self):
        return self.last_checkin + CHECKIN_DURATION < time.time()



class HelloWorld(object):
    def __init__(self):
        self.openTokens = {}

    @cherrypy.expose
    def index(self):
        return "Hello World!"

    def generate_checkin_id(self):
        checkin_str = ''.join(random.choices(VALID_TOKEN_CHARS, k=20))
        return checkin_str

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
            url = f"join?token={token.value}"
            return f"<a href={url}>{HOSTNAME}/{url}</a>"

    @cherrypy.expose
    def checkin(self, token=None):
        if token is None:
            return '{"everyone_ready": false, "role": "unknown", "status":"token not found", "hint": "accessing this url manually isn\'t very helpful"}'
        if token not in self.openTokens:
            return '{"everyone_ready": false, "role": "unknown", "status":"token invalid", "hint": "maybe you missed some of the token when copying?"}'
        token_obj = self.openTokens[token]

        if token_obj.is_token_expired():
            return '{"everyone_ready": false, "role": "unknown", "status":"token expired", "hint": "you took too long to join the lobby :("}'

        checkin_id = cherrypy.session.get('checkin_id')
        # If this user doesn't have a checkin_id yet then give them one
        if checkin_id is None:
            # If the checkins are already done than this lobby is full
            # Maybe this user quit their session and has opened a new one
            # If so, too bad :(
            if token_obj.checkins_complete():
                return '{"everyone_ready": true, "role": "None", "status":"all roles taken", "hint": "perhaps you closed your browser and tried to reopen a link? (you can only see your role again if you have the same browser session open)"}'
            checkin_id = self.generate_checkin_id()
            cherrypy.session['checkin_id'] = checkin_id

        # If this user hasn't checked in for this token yet then create a checkin for them in this token
        if token_obj.checkins.get(checkin_id) is None:
            token_obj.checkins[checkin_id] = Checkin(checkin_id)

        checkin_obj = token_obj.checkins[checkin_id]
        checkin_obj.checkin()

        # If everyone has checked in then we can return the roles to everyone
        if token_obj.checkins_complete():
            return f'{{"everyone_ready": true, "role":"{token_obj.get_role(checkin_id)}", "status": "done", "hint": "none"}}'

        return '{"everyone_ready": false, "role": "unknown", "status": "waiting", "hint": "none"}'

    @cherrypy.expose
    def join(self, token=None):
        if token == None:
            return "You need to join using a token. You can generate one <a href=generate>here</a>"
        if token in self.openTokens:
            token_obj = self.openTokens[token]
            if not token_obj.is_token_expired():
                with open("join.html", 'r') as f:
                    return  f.read()
            else:
                return "Token expired"
        else:
            return "Invalid token :("
conf = {
    'global': {
        'server.socket_host': '0.0.0.0'
    },
    '/': {
        'tools.sessions.on': True,
    }
}
instance = HelloWorld()
cleanup = cherrypy.process.plugins.BackgroundTask(5, instance.cleanup_expired_tokens)
cleanup.start()
cherrypy.quickstart(instance, '/', conf)
