from parsimonious.nodes import Node, NodeVisitor

from .actions import ActionsEnum
from .grammar import commands_grammar


class CommandParser(NodeVisitor):
    grammar = commands_grammar

    def visit_command(self, node: Node, visited_children: list):
        return visited_children[1][0]

    def visit_show_list(self, node: Node, visited_children: list):
        return {'action': ActionsEnum.SHOW_LIST}

    def visit_add_rooms(self, node: Node, visited_children: list):
        return {'action': ActionsEnum.ADD_ROOMS, 'rooms': visited_children[1]}

    def visit_remove_rooms(self, node: Node, visited_children: list):
        return {'action': ActionsEnum.REMOVE_ROOMS, 'rooms': visited_children[1]}

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

    def visit_set_room(self, node: Node, visited_children: list):
        return {
            'action': ActionsEnum.SET_ROOM,
            'room': visited_children[0]
        }

    def visit_get_duty_date(self, node: Node, visited_children: list):
        return {
            'action': ActionsEnum.GET_DUTY_DATE,
            'room': visited_children[-1]
        }

    def visit_int(self, node: Node, visited_children: list):
        return int(node.text)

    def generic_visit(self, node: Node, visited_children: list):
        return visited_children or node
