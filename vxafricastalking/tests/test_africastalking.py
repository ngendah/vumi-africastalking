import mock

from twisted.internet.defer import inlineCallbacks, succeed
from vumi.tests.helpers import VumiTestCase
from vumi.transports.httprpc.tests.helpers import HttpRpcTransportHelper
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from treq.client import _Response

from vxafricastalking.africastalking import AfricasTalkingTransport


class FakeResponse(object):
    def __init__(self, code, headers, data):
        self.code = code
        self.data = data
        self.length = len(data)
        self.headers = headers
        self.previousResponse = None

    def deliverBody(self, protocol):
        class ResponseDone(object):
            def check(self, object):
                return True
        protocol.dataReceived(self.data)
        protocol.connectionLost(ResponseDone())

    def setPreviousResponse(self, response):
        self.previousResponse = response


class TestAfricasTalkingTransport(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.agent_factory = mock.Mock(Agent)
        self.config = {
            'username': 'sandbox',
            'api_key': 'test',
            'web_path': '/at',
            'agent_factory': self.agent_factory,
        }
        self.helper = self.add_helper(
            HttpRpcTransportHelper(AfricasTalkingTransport)
        )
        self.transport = yield self.helper.get_transport(self.config)
        self.transport_url = self.transport.get_transport_url()

    @inlineCallbacks
    def test_outbound_ack_ok(self):
        response = mock.Mock(
            code=200,
            content={},
            headers=Headers({}))
        self.agent_factory.request.return_value = succeed(response)
        msg = yield self.helper.make_dispatch_outbound('hi')
        [ack] = yield self.helper.wait_for_dispatched_events(1)
        self.assertEqual(ack['event_type'], 'ack')
        self.assertEqual(ack['user_message_id'], msg['message_id'])

    @inlineCallbacks
    def test_outbound_nack_ok(self):
        content = b'{"description": "bad request"}'
        headers = Headers({
            b'Content-Type': [b'application/json; charset=utf-8']
        })
        response = _Response(FakeResponse(404, headers, content), None)
        self.agent_factory.request.return_value = succeed(response)
        msg = yield self.helper.make_dispatch_outbound('hi')
        [nack] = yield self.helper.wait_for_dispatched_events(1)
        self.assertEqual(nack['event_type'], 'nack')
        self.assertEqual(nack['user_message_id'], msg['message_id'])

    @inlineCallbacks
    def test_outbound_with_list_phones_ack_ok(self):
        response = mock.Mock(
            code=200,
            content={},
            headers=Headers({}))
        self.agent_factory.request.return_value = succeed(response)
        msg = yield self.helper.make_dispatch_outbound(
            'hi',
            to_addr=['+254745009876', '+254796008123'],
            to_addr_type='list',
        )
        [ack] = yield self.helper.wait_for_dispatched_events(1)
        self.assertEqual(ack['event_type'], 'ack')
        self.assertEqual(ack['user_message_id'], msg['message_id'])

    @inlineCallbacks
    def test_request_headers_ok(self):
        response = mock.Mock(
            code=200,
            content={},
            headers=Headers({
                b'Content-Type': [b'application/json; charset=utf-8']
            })
        )
        fbp_patcher = mock.patch('treq.client.FileBodyProducer')
        FileBodyProducer = fbp_patcher.start()
        self.addCleanup(fbp_patcher.stop)
        self.agent_factory.request.return_value = succeed(response)
        yield self.helper.make_dispatch_outbound('hi')
        self.agent_factory.request.assert_called_once_with(
            b'POST',
            b'https://api.sandbox.africastalking.com/version1/messaging',
            Headers({
                'apikey': ['test'],
                'content-type': ['application/json'],
                'accept-encoding': ['gzip'],
                'accept': ['application/json'],
                'user-agent': ['africastalking-vumi/0.1.0']
            }),
            FileBodyProducer.return_value
        )
