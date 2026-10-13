# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.memory import MemInterface
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2 as p
from spell.utils.grpc_utils import UnpackValue
from .connection import call
from .common import settings


class Memory(MemInterface):
    def _generateReport(self,image,report_type,begin,end,source,config=None):
        return call('MEM','GenerateReport',p.MemoryReportRequest(image=image,report_type=report_type,
            begin=begin,end=end,source=source,config=settings(config))).value

    def _compareImages(self,image1,image2,report_type,begin,end,source,config=None):
        return call('MEM','CompareImages',p.CompareMemoryReportRequest(image1=image1,image2=image2,
            report_type=report_type,begin=begin,end=end,source=source,config=settings(config))).value

    def _createGoldenImage(self,scp,filename,config=None):
        return call('MEM','CreateGoldenImage',p.GoldenImageRequest(scp=scp,filename=filename,config=settings(config))).value

    def _memoryLookup(self,name,address,image,report_type,source,config=None):
        return UnpackValue(call('MEM','MemoryLookup',p.MemoryLookupRequest(name=name,address=address,
            image=image,report_type=report_type,source=source,config=settings(config))))

    def _dataObjectLookup(self,name,ltype,config=None):
        return UnpackValue(call('MEM','DataObjectLookup',p.DataObjectLookupRequest(name=name,type=ltype,config=settings(config))))

    def _dataItemLookup(self,name,ltype,source,valueFormat,config=None):
        return UnpackValue(call('MEM','DataItemLookup',p.DataItemLookupRequest(name=name,type=ltype,
            source=source,valformat=valueFormat,config=settings(config))))

    def _getObjectIDs(self,*args,**kwargs):
        raise DriverException('Original SPELLDriver.proto has no GetObjectIDs RPC')


MEM = Memory()
