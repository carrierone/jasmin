from twisted.web.resource import Resource
from twisted.internet import defer
import json
import logging

class ConversationWebhook(Resource):
    isleaf = True

    def __init__(self, config, RouterPB, stats, log):
        Resource.__init__(self)
        self.config = config
        self.RouterPB = RouterPB
        self.stats = stats
        self.log = log

    @defer.inlineCallbacks
    def render_POST(self, request):
        """Handle webhook callbacks from Twilio"""
        self.log.debug("Handling webhook callback from %s", request.getClientIP())

        try:
            # Parse webhook payload
            content = json.loads(request.content.read())
            
            # Validate webhook signature if configured
            if not self._validate_webhook_signature(request):
                request.setResponseCode(401)
                return b'Invalid signature'

            # Handle different webhook types
            event_type = content.get('EventType')
            if event_type == 'onMessageAdded':
                response = yield self._handle_message_added(content)
            elif event_type == 'onConversationUpdated':
                response = yield self._handle_conversation_updated(content)
            else:
                self.log.warning("Unhandled webhook event type: %s", event_type)
                response = {'status': 'ignored'}

            request.setResponseCode(200)
            return json.dumps(response).encode()

        except Exception as e:
            self.log.error("Error processing webhook: %s", str(e))
            request.setResponseCode(500)
            return b'Internal Server Error'

    def _validate_webhook_signature(self, request):
        """Validate Twilio webhook signature"""
        if not self.config.twilio_auth_token:
            return True

        signature = request.getHeader('X-Twilio-Signature')
        if not signature:
            return False

        # TODO: Implement proper Twilio signature validation
        return True

    @defer.inlineCallbacks
    def _handle_message_added(self, content):
        """Handle new message webhook"""
        # Extract message details
        conversation_sid = content.get('ConversationSid')
        message = content.get('Message', {})
        
        # Store message in conversation thread
        yield self.RouterPB.perspective_store_message(
            conversation_sid=conversation_sid,
            message_body=message.get('Body'),
            author=message.get('Author')
        )
        
        return {'status': 'processed'}

    @defer.inlineCallbacks
    def _handle_conversation_updated(self, content):
        """Handle conversation update webhook"""
        # Update conversation state
        conversation_sid = content.get('ConversationSid')
        attributes = content.get('Attributes', {})
        
        yield self.RouterPB.perspective_update_conversation(
            conversation_sid=conversation_sid,
            attributes=attributes
        )
        
        return {'status': 'updated'}
