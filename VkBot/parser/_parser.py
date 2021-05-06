__author__ = 'kranonetka'

from parsimonious.nodes import Node, NodeVisitor

from ._grammar import message_grammar
from ._mention import Mention
from ._message import Message
from .commands import RemoveRoomsCommand, AddRoomsCommand, ShowListCommand, NotifyTodayCommand, \
    GetDutyDateCommand, HelpCommand, SetRoomsCommand, AddAdmins, RemoveAdmins


class MessageParser(NodeVisitor):
    grammar = message_grammar

    def parse(self, text, pos=0):
        """
        :rtype: Message
        """
        return super(MessageParser, self).parse(text.lower(), pos)

    def visit_message(self, node: Node, visited_children: list):
        message = Message(visited_children[2])

        if not isinstance(prefix := visited_children[0], Node):  # if present
            message.mention = prefix[0][0]

        return message

    def visit_command(self, node: Node, visited_children: list):
        return visited_children[0]

    def visit_mention(self, node: Node, visited_children: list):
        return Mention(
            type=node.children[1].text,
            id=visited_children[2]
        )

    def visit_id(self, node: Node, visited_children: list):
        return int(node.text)

    def visit_help(self, node: Node, visited_children: list):
        return HelpCommand()

    def visit_mentions(self, node: Node, visited_children: list):
        mentions = [visited_children[0]]
        if not isinstance(other_mentions := visited_children[1], Node):  # If others exists
            for _, mention in other_mentions:  # type: (_, Mention)
                mentions.append(mention)
        return mentions

    def visit_add_admins(self, node: Node, visited_children: list):
        user_ids = []

        mentions = visited_children[2]
        for mention in mentions:  # type: Mention
            if mention.type == 'id':
                user_ids.append(mention.id)

        return AddAdmins(user_ids)

    def visit_remove_admins(self, node: Node, visited_children: list):
        user_ids = []

        mentions = visited_children[2]
        for mention in mentions:  # type: Mention
            if mention.type == 'id':
                user_ids.append(mention.id)

        return RemoveAdmins(user_ids)

    def visit_show_list(self, node: Node, visited_children: list):
        return ShowListCommand()

    def visit_notify_today(self, node: Node, visited_children: list):
        return NotifyTodayCommand()

    def visit_add_rooms(self, node: Node, visited_children: list):
        return AddRoomsCommand(visited_children[-1])

    def visit_remove_rooms(self, node: Node, visited_children: list):
        return RemoveRoomsCommand(visited_children[-1])

    def visit_set_rooms(self, node: Node, visited_children: list):
        rooms = [visited_children[0]]

        if not isinstance(other_rooms := visited_children[1], Node):  # If others exists
            for _, room in other_rooms:
                rooms.append(room)

        return SetRoomsCommand(rooms)

    def visit_get_duty_date(self, node: Node, visited_children: list):
        return GetDutyDateCommand(visited_children[-1])

    def visit_room_set(self, node: Node, visited_children: list):
        room_set: set = visited_children[0]

        if not isinstance(subsets := visited_children[1], Node):  # If others exists
            for _, subset in subsets:
                room_set.update(subset)

        return room_set

    def visit_room_subset(self, node: Node, visited_children: list):
        return visited_children[0]

    def visit_room_range(self, node: Node, visited_children: list):
        return set(range(visited_children[0], visited_children[2] + 1))

    def visit_single_room(self, node: Node, visited_children: list):
        return {visited_children[0]}

    def visit_int(self, node: Node, visited_children: list):
        return int(node.text)

    def generic_visit(self, node: Node, visited_children: list):
        return visited_children or node
