import click
import itertools as it
import copy
import xml.dom.minidom as xml
from xml.dom.minidom import Node

from typing import List, Tuple

from functools import wraps


@click.command()
@click.argument('xmlfile', type=click.File())
@click.argument('paramfile', type=click.File(), required=False)
@click.option('--params', '-p', multiple=True)
def cli(xmlfile, paramfile, params):
    paramnames = list(params)

    if paramfile:
        paramnames.extend([line.strip() for line in paramfile])

    paramnames = set(map(str.lower, paramnames))

    dom = xml.parse(xmlfile)
    remove_blanks(dom)

    for param in dom.getElementsByTagName('Parameter'):

        paramname = param.attributes['parameterCode'].value

        # if paramnames and paramname not in ['P1AFT']:# paramnames:
        #    continue

        # TODO
        if param.attributes['parameterCode'].value != 'P1OLL':
            continue

        valueElement = param.firstChild.firstChild

        print(parseNode(valueElement))


def remove_blanks(node):
    for x in node.childNodes:
        if x.nodeType == Node.TEXT_NODE:
            if x.nodeValue:
                x.nodeValue = x.nodeValue.strip()
        elif x.nodeType == Node.ELEMENT_NODE:
            remove_blanks(x)

    node.normalize()


def parseNode(node):
    mapping = {'Scalar': PrimitiveParameter,
               'Boolean': PrimitiveParameter,
               'String': PrimitiveParameter,
               'Array': MatrixParameter,
               'Struct': StructParameter,
               'Identifier': PrimitiveParameter,
               }

    obj = mapping.get(node.tagName, None)
    if not obj:
        raise ValueError

    return obj(node)


class PrimitiveParameter:
    def __init__(self, node):
        self.data = str(node.firstChild.data)

    def __str__(self):
        return self.data


class MatrixParameter:
    def __init__(self, node):
        self.values: List[List[str]] = []
        self.columns, self.rows = 0, 0

        self.parse(node)
        self.calculatesize()

    @staticmethod
    def validateElement(element):
        if element.tagName != 'Element':
            raise ValueError('Expected Element')
        if len(element.childNodes) != 1:
            raise ValueError('Expected Element to have 1 child')

    def parse(self, node):

        current = []

        for element in node.childNodes:
            self.validateElement(element)
            value = element.childNodes[0]
            if value.tagName != 'Array':
                current.append(parseNode(value))
            else:
                if current:
                    raise ValueError()  # TODO
                self.values.append(self.parseRow(value))

        if current:
            if self.values:
                raise ValueError()  # TODO
            self.values = [current]

    def parseRow(self, node):
        result = []
        for element in node.childNodes:
            self.validateElement(element)
            value = parseNode(element.childNodes[0])
            if type(value) is not PrimitiveParameter:
                raise ValueError  # TODO
            result.append(value)
        return result

    def calculatesize(self):
        cols = len(self.values[0])
        for row in self.values:
            if len(row) != cols:
                raise ValueError('Matrix is not rectangular')

        self.columns = cols
        self.rows = len(self.values)

    def __str__(self):

        output = [[f'({column + 1})' for column in range(len(self.values[0]))]]
        output.extend(list(map(str, row)) for row in self.values)
        for index, row in enumerate(output, ):
            row.insert(0, f'({index})' if index != 0 else '')

        return format2darray(output)


class StructParameter:

    def __init__(self, node):
        self.values: List[Tuple[str, PrimitiveParameter]] = []

        self.parse(node)

    @staticmethod
    def validateElement(element):
        if element.tagName != 'Element':
            raise ValueError('Expected Element')
        if len(element.childNodes) != 2:
            raise ValueError('Expected Element to have 2 child')

    def parse(self, node):

        for element in node.childNodes:
            self.validateElement(element)
            value = str(parseNode(element.childNodes[0]))

            name = str(parseNode(element.childNodes[1].childNodes[0]))

            self.values.append((name, value))

    def __str__(self):
        array = list(zip(*self.values))
        return format2darray(array)


def format2darray(array):
    output = [list(row) for row in array]

    columnswidth = [2 + max(map(len, column)) for column in zip(*output)]
    for row in output:
        for (columnindex, value), width in zip(enumerate(row), columnswidth):
            row[columnindex] = value.ljust(width, ' ')

    rows = [''.join(row) for row in output]

    return '\n'.join(rows)


if __name__ == '__main__':
    cli()
