import falcon
from wsgiref import simple_server
import json
import uuid
import logging
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import shortuuid
import os
from utils.utils import bib_to_json

class SessionResource():

    sessions = []

    @dataclass_json
    @dataclass
    class SessionInterface():
        session_guid: str
        local_path: str = None
        author: str = "unknown"
        meta: str = "unknown"
        location: str = None

        def create_local_path(self):
            root_path = shared_config.root_path
            self.local_path = os.path.join(root_path, self.session_guid)
            os.makedirs(self.local_path)

    def __init__(self):
        self.logger = logging.getLogger('reviz.' + __name__)

    def on_post(self, req, resp):
        self.logger.debug(req)
        session_guid = shortuuid.uuid()
        session = self.SessionInterface(session_guid)
        session.location = f"/session/{session_guid}"
        if req.params.get("author"):
            session.author = req.params.get("author")
        if req.params.get("meta"):
            session.meta = req.params.get("meta")
        session.create_local_path()
        self.sessions.append(session.to_dict())
        resp.body = session.to_json()
        resp.location = session.location
        resp.status = falcon.HTTP_201

    def on_get(self, req, resp, sess_guid=None):
        if sess_guid:
            fs = [s for s in self.sessions if s['session_guid'] == sess_guid]
            self.logger.debug(fs)
            if any(fs):
                resp.body = fs[0]
                resp.location = fs[0].location
            else:
                raise falcon.HTTPNotFound()
                resp.status = falcon.HTTP_404
                resp.body = f"a session {sess_guid} was not found"
        else:
            resp.body = json.dumps(self.sessions)

def get_session_or_error(req, resp):
    session = req.params.get("session")
    if not session:
        resp.status = falcon.HTTP_400
        resp.body = "a session parameter is required for this method!"
    elif not os.path.isdir(os.path.join(shared_config.root_path, session)):
        res.status = falcon.HTTP_400
        resp.body = "this session is unknown!"
        session = None
    return session, resp

def call_method_in_out_file(method, in_file, out_file, *args):
    logging.getLogger('reviz.' + "call_method").debug(f"method {method}, {in_file} -> {out_file}, with *args {args}")
    method(in_file, out_file, *args)

def file_name_in_session(session, extension):
    return os.path.join(shared_config.root_path, session, f"{shortuuid()}.{extension}")

def read_body_to_input_file(session, req):
    fn = os.path.join(shared_config.root_path, session, "infile")
    with open(fn, "w") as fs:
        m = req.media
        fs.write(json.dumps(m))

class Bib2JsonResource():
    def on_post(self, req, resp):
        session, resp = get_session_or_error(req, resp)
        if not session:
            return
        in_file = read_body_to_input_file(session, req)
        out_file = file_name_in_session(session, ".json")
        call_method_in_out_file(bib_to_json, in_file, out_file)

@dataclass
class SharedConfig():
    root_path: str
    sessions = []

shared_config = SharedConfig(root_path = "/tmp/reviz")

class FalconAPI:
    def __init__(self):
        logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s",level=logging.DEBUG)
        self.logger = logging.getLogger('reviz.' + __name__)
        self.logger.info("starting API log")
        self.api = falcon.API()
        session_resource = SessionResource()
        self.api.add_route('/session', session_resource)
        self.api.add_route('/session/{sess_guid}', session_resource)

        bib2json_resource = Bib2JsonResource()
        self.api.add_route('/bib2json', bib2json_resource)

    def execute_hook(self, port=9090):
        self.logger.info(f"Listening on 127.0.0.1:{port}")
        httpd = simple_server.make_server('127.0.0.1', port, self.api)
        httpd = httpd.serve_forever()
