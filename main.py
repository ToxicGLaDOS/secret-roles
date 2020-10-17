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
    def __init__(self, value: str, num_players: int):
        self.value = value
        self.num_players = num_players
        self.time_created = time.time()
        self.checkins = {}

    def checkins_complete(self):
        if len(self.checkins.values()) != self.num_players:
            print("Not all players have joined")
            print(f"Num players: {len(self.checkins.values())}")
            print(f"Expected players: {type(self.num_players)}")
            return False
        for checkin in self.checkins.values():
            if checkin.is_timedout():
                print("A checkin is timed out")
                return False
        print("Checkins complete")
        return True

    def is_token_expired(self):
        return self.time_created + TOKEN_DURATION < time.time()

class Checkin(object):
    def __init__(self, id: str):
        self.id = id
        self.last_checkin = time.time()

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

    def generate_token(self, length: int, num_players: int):
        token_str = ''.join(random.choices(VALID_TOKEN_CHARS, k=length))
        token = Token(token_str, num_players)
        return token

    @cherrypy.expose
    def generate(self, num_players=None):
        if num_players == None:
            with open("/home/jeff/projects/secret-roles/generate_form.html", 'r') as f:
                return f.read()
        else:
            token = self.generate_token(TOKEN_LENGTH, int(num_players))
            self.openTokens[token.value] = token
            url = f"{HOSTNAME}/join?token={token.value}"
            return f"<a href={url}>{url}</a>"

    @cherrypy.expose
    def checkin(self, token=None):
        if token is None:
            return "You need to check in with a token!"
        if token not in self.openTokens:
            return "Invalid token"
        token_obj = self.openTokens[token]

        if token_obj.is_token_expired():
            return "Token has expired"

        checkin_id = cherrypy.session.get('checkin_id')

        if checkin_id is None:
            checkin_id = self.generate_checkin_id()
            cherrypy.session['checkin_id'] = checkin_id
            token_obj.checkins[checkin_id] = Checkin(checkin_id)

        checkin_obj = token_obj.checkins[checkin_id]
        checkin_obj.checkin()


        if token_obj.checkins_complete():
            return "Everyone has checked in. We can return the secret roles now."

        return "Waiting for others"

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
            return "You should join using a token!"
        if token in self.openTokens:
            token_obj = self.openTokens[token]
            if not token_obj.is_token_expired():
                return f"""You did it! Start checking in.
                        <a href=localhost:8080/checkin?token={token}>Check in here</a>
                """
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