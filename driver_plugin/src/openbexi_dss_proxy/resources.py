# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.resources import ResourceInterface
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import PackValue,UnpackValue
from .connection import call
from .common import settings


class Resources(ResourceInterface):
    def _setLink(self,name,enable,config=None):
        return call('RSC','SetLink',p.LinkRequest(name=name,status=enable,config=settings(config))).value

    def _checkLink(self,name,config=None):
        return call('RSC','CheckLink',p.LinkRequest(name=name,config=settings(config))).value

    def _setResource(self,name,value,isLocal,config=None):
        if isLocal:
            raise DriverException('This driver provides shared simulator resources only')
        return call('RSC','SetResource',p.ResourceRequest(name=name,value=PackValue(value),config=settings(config))).value

    def _getResource(self,name,isLocal,config=None):
        if isLocal:
            raise DriverException('This driver provides shared simulator resources only')
        return UnpackValue(call('RSC','GetResource',p.ResourceRequest(name=name,config=settings(config))).value)

    def _getResources(self,isLocal,config=None):
        if isLocal:
            raise DriverException('This driver provides shared simulator resources only')
        return UnpackValue(call('RSC','GetResources',p.ResourcesRequest(config=settings(config))).value)

    def _getResourceStatus(self,name,config=None):
        return UnpackValue(call('RSC','GetResourceStatus',p.ResourceRequest(name=name,config=settings(config))).value)

    def _isResourceOK(self,name,config=None):
        return call('RSC','IsResourceOK',p.ResourceRequest(name=name,config=settings(config))).value


RSC = Resources()
