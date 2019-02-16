from treq.client import HTTPClient

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import http
from twisted.web.client import Agent

from vumi.config import ConfigText
from vumi.transports.httprpc.httprpc import HttpRpcTransport, HttpRpcTransportConfig

REQUEST_FAILURE = 'Failure'
REQUEST_SUCCESS = 'success'


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

    CONFIG_CLASS = AfricasTalkingTransportConfig

    @property
    def agent_factory(self):
        agent_factory = Agent(reactor)
        if 'agent_factory' in self.config:
            agent_factory = self.config['agent_factory']
        return agent_factory

    @inlineCallbacks
    def setup_transport(self):
        config = self.get_static_config()
        self.outbound_url = config.outbound_production_url
        if config.username == 'sandbox':
            self.outbound_url = config.outbound_sandbox_url
        self.outbound_url += config.send_sms_api_endpoint
        self.headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'User-Agent': 'africastalking-vumi/0.1.0',
            'apikey': config.api_key,
        }
        self.username = config.username
        yield super(AfricasTalkingTransport, self).setup_transport()

    def emit(self, msg):
        super(AfricasTalkingTransport, self).emit(
            "AfricasTalkingTransport {}".format(msg)
        )

    @inlineCallbacks
    def handle_outbound_message(self, message):
        # The transport does not make any attempt to
        # interpret AfricasTalking responses
        self.emit("consuming %s" % message)
        message_id = message['message_id']
        missing_fields = self.ensure_message_values(
            message, ['to_addr', 'content']
        )
        if missing_fields:
            returnValue(self.reject_message(message, missing_fields))
        outbound_msg = {
            'username': self.username,
            'to': ','.join(message.payload['to_addr']),
            'message': message.payload['content'].encode('utf-8'),
            'bulkSMSMode': 1,
        }
        self.emit("outbound message {}".format(outbound_msg))
        http_client = HTTPClient(self.agent_factory)
        args = dict(
            url=self.outbound_url,
            data=outbound_msg,
            headers=self.headers,
            allow_redirects=False
        )
        response = yield http_client.post(**args)
        validate = yield self.validate_outbound(response)
        validate['message_id'] = message_id
        yield self.outbound_status(**validate)

    @inlineCallbacks
    def validate_outbound(self, response):
        self.emit("response {}".format(response.__dict__))
        if response.code == http.OK:
            result = yield response.json()
            returnValue({
                'status': REQUEST_SUCCESS,
                'message': result,
            })
        else:
            result = yield response.text()
            returnValue({
                'status': REQUEST_FAILURE,
                'message': result,
            })

    @inlineCallbacks
    def outbound_status(self, status, message, message_id):
        if status == REQUEST_SUCCESS:
            self.add_status(
                status='ok',
                component='africastalking_outbound',
                type='good_outbound_request',
                message=message,
            )
            yield self.publish_ack(message_id, message)
        else:
            self.add_status(
                status='down',
                component='africastalking_outbound',
                type='bad_outbound_request',
                message=message,
            )
            yield self.publish_nack(message_id, message)
