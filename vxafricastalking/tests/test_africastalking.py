import json
import mock

from twisted.internet.defer import inlineCallbacks, succeed
from vumi.tests.helpers import VumiTestCase
from vumi.transports.httprpc.tests.helpers import HttpRpcTransportHelper
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from treq.content import content

from vxafricastalking.africastalking import AfricasTalkingTransport


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
        print ack
        self.assertEqual(ack['event_type'], 'ack')
        self.assertEqual(ack['user_message_id'], msg['message_id'])

    @inlineCallbacks
    def test_outbound_nack_ok(self):
        response = mock.Mock(
            code=404,
            content=content(json.dumps({
                'description': 'bad request'
            })),
            headers=Headers({
                'content-type': 'application/json',
            }))
        self.agent_factory.request.return_value = succeed(response)
        msg = yield self.helper.make_dispatch_outbound('hi')
        [nack] = yield self.helper.wait_for_dispatched_events(1)
        print nack
        self.assertEqual(nack['event_type'], 'ack')
        self.assertEqual(nack['user_message_id'], msg['message_id'])


