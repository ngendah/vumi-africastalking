import mock

from twisted.internet.defer import inlineCallbacks, returnValue, DeferredQueue
from vumi.tests.helpers import VumiTestCase
from twisted.web.client import Agent
from vumi.transports.httprpc.tests.helpers import HttpRpcTransportHelper

from vxafricastalking.africastalking import AfricasTalkingTransport


class TestAfricasTalkingTransport(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.config = {
            'username': 'sandbox',
            'api_key': 'test',
            'web_path': '/at',
        }
        self.helper = self.add_helper(
            HttpRpcTransportHelper(AfricasTalkingTransport)
        )
        self.helper.agent_factory = mock.Mock(Agent)
        self.transport = yield self.helper.get_transport(self.config)
        self.mbp_patcher = mock.patch('treq.multipart.MultiPartProducer')
        self.MultiPartProducer = self.mbp_patcher.start()
        self.addCleanup(self.mbp_patcher.stop)

    @inlineCallbacks
    def test_outbound(self):
        msg = yield self.helper.make_dispatch_outbound('hi')
        import pdb; pdb.set_trace()

