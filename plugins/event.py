# encoding:utf-8

from enum import Enum


class Event(Enum):
    ON_RECEIVE_MESSAGE = 1  
    """
    e_context = {  "channel": message channel, "context": this message's context}
    """

    ON_HANDLE_CONTEXT = 2  
    """
    e_context = {  "channel": message channel, "context": this message's context, "reply": current reply, initially empty}
    """

    ON_DECORATE_REPLY = 3  
    """
    e_context = {  "channel": message channel, "context": this message's context, "reply": current reply}
    """

    ON_SEND_REPLY = 4  
    """
    e_context = {  "channel": message channel, "context": this message's context, "reply": current reply}
    """

    


class EventAction(Enum):
    CONTINUE = 1  
    BREAK = 2  
    BREAK_PASS = 3  


class EventContext:
    def __init__(self, event, econtext=dict()):
        self.event = event
        self.econtext = econtext
        self.action = EventAction.CONTINUE

    def __getitem__(self, key):
        return self.econtext[key]

    def __setitem__(self, key, value):
        self.econtext[key] = value

    def __delitem__(self, key):
        del self.econtext[key]

    def is_pass(self):
        return self.action == EventAction.BREAK_PASS

    def is_break(self):
        return self.action == EventAction.BREAK or self.action == EventAction.BREAK_PASS
