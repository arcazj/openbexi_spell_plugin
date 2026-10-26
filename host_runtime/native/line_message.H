// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_LINE_MESSAGE_H
#define OPENBEXI_V08_LINE_MESSAGE_H

// The checked native line-notification method overwrites every computed field
// before sending. Only its immutable one-field prototype may use this cache.
// No callbacks, command grants or acknowledgements are cached.
struct V08LineScratch {
    SPELLipcMessage message;
    bool busy=false, compatible=false;
};
class V08LineLease {
    V08LineScratch local;
    V08LineScratch& scratch;
public:
    V08LineLease(V08LineScratch& cached,const SPELLipcMessage& prototype):
        scratch(cached.busy ? local : cached)
    {
        scratch.busy=true;
        try {
        const auto& fields=prototype.v08Fields();
        const bool compatible=fields.size()==1 && fields.count(MessageField::FIELD_PROC_ID)
            && prototype.getId()==MessageId::MSG_ID_NOTIFICATION
            && prototype.getType()==MSG_TYPE_NOTYPE && prototype.getKey()==-1
            && prototype.getSequence()==-1 && !prototype.getCompressed()
            && prototype.getSender()==MessageId::GENERIC_ID
            && prototype.getReceiver()==MessageId::GENERIC_ID;
        if (!compatible || !scratch.compatible) scratch.message=prototype;
        else {
            const auto& value=fields.find(MessageField::FIELD_PROC_ID)->second;
            const auto& old=scratch.message.v08Fields();
            const auto found=old.find(MessageField::FIELD_PROC_ID);
            if (found==old.end() || found->second!=value)
                scratch.message.set(MessageField::FIELD_PROC_ID,value);
        }
        if (compatible) {
            // The owned-send path mutates key/sequence/sender/receiver. Restore
            // prototype metadata before preparing the next independent line.
            scratch.message.setId(MessageId::MSG_ID_NOTIFICATION);
            scratch.message.setSender(MessageId::GENERIC_ID);
            scratch.message.setReceiver(MessageId::GENERIC_ID);
            scratch.message.setKey(-1); scratch.message.setSequence(-1);
            scratch.message.setType(MSG_TYPE_NOTYPE); scratch.message.setCompressed(false);
        }
        scratch.compatible=compatible;
        } catch (...) {scratch.busy=false;throw;}
    }
    ~V08LineLease() {
        size_t capacity=0;
        bool oversized=scratch.message.v08Fields().size()>64;
        for (const auto& field:scratch.message.v08Fields()) {
            if (field.first.capacity()>64*1024-capacity) {oversized=true;break;}
            capacity+=field.first.capacity();
            if (field.second.capacity()>64*1024-capacity) {oversized=true;break;}
            capacity+=field.second.capacity();
        }
        if (oversized) {scratch.message=SPELLipcMessage();scratch.compatible=false;}
        scratch.busy=false;
    }
    SPELLipcMessage& message() { return scratch.message; }
    V08LineLease(const V08LineLease&)=delete;
    V08LineLease& operator=(const V08LineLease&)=delete;
};
#endif
