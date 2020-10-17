import cherrypy
import random
import string
import time

TOKEN_LENGTH = 20
TOKEN_DURATION = 60 * 1 # 5 minutes
CHECKIN_DURATION = 60 * 1 # 1 minutes
HOSTNAME = "localhost:8080"
VALID_TOKEN_CHARS = string.ascii_letters + string.digits


class Token(object):
    def __init__(self, value: str, roles: list):
        self.value = value
        self.roles = roles
        self.roles_remaining = roles.copy()
        self.time_created = time.time()
        self.checkins = {}

    def checkins_complete(self):
        if len(self.checkins.values()) != len(self.roles):
            print("Not all players have joined")
            return False
        for checkin in self.checkins.values():
            if checkin.is_timedout():
                print("A checkin is timed out")
                return False
        print("Checkins complete")
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
            return '{"everyone_ready": false, "role": "unknown", "status":"token not found"}'
        if token not in self.openTokens:
            return '{"everyone_ready": false, "role": "unknown", "status":"token invalid"}'
        token_obj = self.openTokens[token]

        if token_obj.is_token_expired():
            return '{"everyone_ready": false, "role": "unknown", "status":"token expired"}'

        checkin_id = cherrypy.session.get('checkin_id')
        # If this user doesn't have a checkin_id yet then give them one
        if checkin_id is None:
            checkin_id = self.generate_checkin_id()
            cherrypy.session['checkin_id'] = checkin_id

        # If this user hasn't checked in for this token yet then create a checkin for them in this token
        if token_obj.checkins.get(checkin_id) is None:
            token_obj.checkins[checkin_id] = Checkin(checkin_id)

        checkin_obj = token_obj.checkins[checkin_id]
        checkin_obj.checkin()

        # If everyone has checked in then we can return the roles to everyone
        if token_obj.checkins_complete():
            return f'{{"everyone_ready": true, "role":"{token_obj.get_role(checkin_id)}", "status": "done"}}'

        return '{"everyone_ready": false, "role": "unknown", "status": "waiting"}'

    @cherrypy.expose
    def test(self):
        cherrypy.session['something'] = 'wow'
        return "<a href=localhost:8080/test1>here</a>"

    @cherrypy.expose
    def test1(self):
        return cherrypy.session['something']

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
        '/': {
            'tools.sessions.on': True
        }
    }
cherrypy.quickstart(HelloWorld(), '/', conf)