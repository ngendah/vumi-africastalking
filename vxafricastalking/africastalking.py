import json

from treq.client import HTTPClient

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import http
from twisted.web.client import Agent

from vumi.config import ConfigText
from vumi.transports.httprpc.httprpc import HttpRpcTransport, HttpRpcTransportConfig


class AfricasTalkingTransportConfig(HttpRpcTransportConfig):
    api_key = ConfigText('API key', static=True, required=True)
    username = ConfigText('User name', static=True, required=True)
    send_sms_api_endpoint = ConfigText('API endpoint', static=True, default='/version1/messaging')
    outbound_sandbox_url = ConfigText(
        'Sandbox URL', static=True,
        default='https://api.sandbox.africastalking.com'
    )
    outbound_production_url = ConfigText(
        'Production URL', static=True,
        default='https://api.africastalking.com'
    )


class AfricasTalkingTransport(HttpRpcTransport):
    transport_type = 'sms'
    transport_name = 'at_transport'
    agent_factory = Agent(reactor)

    CONFIG_CLASS = AfricasTalkingTransportConfig

    @inlineCallbacks
    def setup_transport(self):
        config = self.get_static_config()
        self.outbound_url = config.outbound_production_url
        if config.username == 'sandbox':
            self.outbound_url = config.outbound_sandbox_url
        self.outbound_url += config.send_sms_api_endpoint
        self.headers = {
            'Content-Type': ['application/json'],
            'Accept': 'application/json',
            'User-Agent': 'africastalking-vumi/0.1.0',
            'ApiKey': config.api_key,
        }
        self.username = config.username
        yield super(AfricasTalkingTransport, self).setup_transport()

    @inlineCallbacks
    def handle_outbound_message(self, message):
        self.emit("HttpRpcTransport consuming %s" % (message))
        message_id = message['message_id']
        missing_fields = self.ensure_message_values(
            message, ['to_addr', 'content']
        )
        if missing_fields:
            returnValue(self.reject_message(message, missing_fields))
        outbound_msg = {
            'username': self.username,
            'to': message.payload['to_addr'],
            'message': message.payload['content'].encode('utf-8'),
            'bulkSMSMode': 0,
        }
        http_client = HTTPClient(self.agent_factory)
        r = yield http_client.post(
            url=self.outbound_url,
            data=json.dumps(outbound_msg),
            headers=self.headers,
            allow_redirects=False,
        )
        validate = yield self.validate_outbound(r)
        if validate['success']:
            yield self.outbound_success(message_id)
        else:
            yield self.outbound_failure(
                message_id=message_id,
                message='Message not sent: %s' % validate['message'],
                status_type=validate['status'],
                details=validate['details'],
            )

    @inlineCallbacks
    def validate_outbound(self, response):
        if response.code == http.OK:
            returnValue({'success': True})
        else:
            res = yield response.json()
            returnValue({
                'success': False,
                'message': 'bad response from AfricasTalking',
                'status': 'bad_response',
                'details': {
                    'error': res['description'],
                    'res_code': response.code,
                },
            })

    @inlineCallbacks
    def outbound_failure(self, status_type, message_id, message, details):
        yield self.publish_nack(message_id, message)
        yield self.add_status_bad_outbound(status_type, message, details)

    @inlineCallbacks
    def outbound_success(self, message_id):
        yield self.publish_ack(message_id, message_id)
        yield self.add_status_good_outbound()

    def add_status_bad_outbound(self, status_type, message, details):
        return self.add_status(
            status='down',
            component='africastalking_outbound',
            type=status_type,
            message=message,
            details=details,
        )

    def add_status_good_outbound(self):
        return self.add_status(
            status='ok',
            component='africastalking_outbound',
            type='good_outbound_request',
            message='Outbound request successful',
        )
