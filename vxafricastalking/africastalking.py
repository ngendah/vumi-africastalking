import json
from treq.client import HTTPClient

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import http
from twisted.web.client import Agent

from vumi.config import ConfigText
from vumi.transports.httprpc.httprpc import (
    HttpRpcTransport,
    HttpRpcTransportConfig,
)

REQUEST_FAILURE = 'Failure'
REQUEST_SUCCESS = 'success'


class AfricasTalkingTransportConfig(HttpRpcTransportConfig):
    api_key = ConfigText('API key', static=True, required=True)
    username = ConfigText('User name', static=True, required=True)
    send_sms_api_endpoint = ConfigText(
        'API endpoint', static=True, default='/version1/messaging')
    outbound_sandbox_url = ConfigText(
        'Sandbox URL', static=True,
        default='https://api.sandbox.africastalking.com'
    )
    outbound_production_url = ConfigText(
        'Production URL', static=True,
        default='https://api.africastalking.com'
    )


class JsonDecoder:
    @staticmethod
    def decode(content_length, content):
        return json.load(content) if content_length else dict()


class TextDecoder:
    @staticmethod
    def decode(content_length, content):
        return dict(content=content.read() if content_length else '')


class ContentDecoder(object):
    def __init__(self, request):
        self.content = request.content
        self.headers = request.requestHeaders
        self.decoder = self._decoder(self.headers)

    @staticmethod
    def _decoder(headers):
        content_decoders = {
            'application/json': JsonDecoder,
        }
        content_type = headers.getRawHeaders('content-type')
        c_type = content_type[0] if type(
            content_type) is list else content_type
        if ';' in c_type:
            c_type = c_type.split(';')[0]
        return content_decoders.get(c_type, TextDecoder)

    def values(self):
        content_length = int(self.headers.getRawHeaders('content-length')[0])
        return self.decoder.decode(content_length, self.content)


class AfricasTalkingTransport(HttpRpcTransport):
    transport_type = 'sms'
    transport_name = 'at_transport'

    CONFIG_CLASS = AfricasTalkingTransportConfig

    EXPECTED_FIELDS = {'date', 'to', 'from', 'text'}
    OPTIONAL_FIELDS = {'id', 'linkId', 'networkCode'}

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
    def handle_raw_inbound_message(self, message_id, request):
        values, errors = self.get_field_values(
            request,
            self.EXPECTED_FIELDS
        )
        if errors:
            self.emit('Invalid message: %s' % (errors,))
            yield self.finish_request(message_id, json.dumps(errors), code=400)
            return
        yield self.publish_message(
            message_id=message_id,
            date=values['date'],
            content=values['text'],
            to_addr=values['to'],
            from_addr=values['from'],
            transport_type=self.transport_type,
            transport_metadata={
                'id': values.get('id'),
                'network_code': values.get('networkCode'),
                'link_id': values.get('linkId'),
            },
        )
        yield self.finish_request(
            message_id,
            json.dumps({'message_id': message_id})
        )

    def get_field_values(self, request, expected_fields,
                         ignored_fields=frozenset()):
        if request.method == 'GET':
            return super(AfricasTalkingTransport, self).get_field_values(
                request,
                expected_fields,
                ignored_fields
            )
        values = {}
        errors = {}
        content_values = ContentDecoder(request).values()
        for field in content_values.keys():
            if field not in (expected_fields | ignored_fields):
                if self._validation_mode == self.STRICT_MODE:
                    errors.setdefault('unexpected_parameter', []).append(field)
            else:
                values[field] = content_values.get(field)
        for field in expected_fields:
            if field not in values:
                errors.setdefault('missing_parameter', []).append(field)
        return values, errors

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
