from twisted.web.resource import Resource
from twisted.internet import defer
from jasmin.protocols.http.stats import HttpAPIStatsCollector
from jasmin.protocols.http.validation import UrlArgsValidator, HttpAPICredentialValidator
import json
import logging
import base64

class Conversations(Resource):
    isleaf = True

    def __init__(self, config, RouterPB, SMPPClientManagerPB, stats, log, interceptor=None):
        Resource.__init__(self)
        self.config = config
        self.RouterPB = RouterPB
        self.SMPPClientManagerPB = SMPPClientManagerPB
        self.stats = stats
        self.log = log
        self.interceptor = interceptor

    @defer.inlineCallbacks
    def render_POST(self, request):
        """Handle Twilio Conversations API requests"""
        self.log.debug("Handling Conversations API request from %s", request.getClientIP())
        
        # Validate Twilio credentials
        auth = request.getHeader('Authorization')
        if not auth or not self._validate_twilio_auth(auth):
            request.setResponseCode(401)
            return b'Unauthorized'

        try:
            # Parse JSON body
            content = json.loads(request.content.read())
            
            # Handle different Conversations operations
            operation = request.args.get(b'operation', [b'send'])[0].decode()
            
            if operation == 'send':
                response = yield self._handle_send(content)
            elif operation == 'receive':
                response = yield self._handle_receive(content)
            else:
                request.setResponseCode(400)
                return b'Invalid operation'

            request.setResponseCode(200)
            return json.dumps(response).encode()

        except Exception as e:
            self.log.error("Error processing Conversations request: %s", str(e))
            request.setResponseCode(500)
            return b'Internal Server Error'

    def _validate_twilio_auth(self, auth):
        """Validate Twilio credentials using Basic Auth"""
        try:
            if not auth.startswith('Basic '):
                return False
                
            decoded = base64.b64decode(auth[6:]).decode('utf-8')
            account_sid, auth_token = decoded.split(':')
            
            return (account_sid == self.config.twilio_account_sid and 
                    auth_token == self.config.twilio_auth_token)
        except:
            return False

    @defer.inlineCallbacks
    def _handle_send(self, content):
        """Handle sending messages via Conversations API"""
        required_fields = ['to', 'from', 'body']
        if not all(field in content for field in required_fields):
            raise ValueError("Missing required fields")

        # Convert Twilio format to Jasmin format
        message = {
            'to': content['to'],
            'from': content['from'],
            'content': content['body'],
            'coding': 0,
        }

        # Use existing RouterPB to send message
        yield self.RouterPB.perspective_submit_sm(
            message=message,
            connector='twilio_connector'
        )

        return {
            'status': 'queued',
            'sid': 'JA' + base64.b32encode(os.urandom(10)).decode('ascii')
        }

    @defer.inlineCallbacks
    def _handle_receive(self, content):
        """Handle receiving messages via Conversations API"""
        # This would typically be called by Jasmin when receiving a message
        # For now just acknowledge receipt
        return {'status': 'received'}
