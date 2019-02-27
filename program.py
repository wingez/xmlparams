import click
import itertools as it
import xml.dom.minidom as xml
from xml.dom.minidom import Node
from typing import List, Tuple, Dict
from collections import OrderedDict


@click.command()
@click.argument('xmlfile', type=click.File())
@click.argument('paramfile', type=click.File(), required=False)
@click.option('--params', '-p', multiple=True)
@click.option('--nonzero', '-z', is_flag=True)
def cli(xmlfile, paramfile, params, nonzero):
    paramnames = list(params)
    if paramfile:
        paramnames.extend([line.strip() for line in paramfile])

    paramnames = set(map(str.lower, paramnames))

    dom = xml.parse(xmlfile)
    remove_blanks(dom)

    for xmlparam in dom.getElementsByTagName('Parameter'):
        parametername = xmlparam.attributes['parameterCode'].value

        if paramnames and parametername.lower() not in paramnames:
            continue

        parameter = parseNode(xmlparam.firstChild.firstChild)

        if parameter.hasData() or nonzero:
            if isinstance(parameter, ContainerParameter):
                for indices, value in parameter.getindicesandvalues():

                    if value.hasData() or nonzero:
                        print(f'{parametername}: [{",".join(map(str, indices))}] = {value.data}')
            else:
                print(f'{parametername}: {parameter.data}')


def remove_blanks(node):
    for x in node.childNodes:
        if x.nodeType == Node.TEXT_NODE:
            if x.nodeValue:
                x.nodeValue = x.nodeValue.strip()
        elif x.nodeType == Node.ELEMENT_NODE:
            remove_blanks(x)

    node.normalize()


def parseNode(node):
    mapping = {'Scalar': ScalarParameter,
               'Boolean': BooleanParameter,
               'String': PrimitiveParameter,
               'Array': MatrixParameter,
               'Struct': StructParameter,
               'Identifier': PrimitiveParameter,
               'Enum': EnumParameter,
               'Value': PrimitiveParameter,
               }

    obj = mapping.get(node.tagName, None)
    if not obj:
        raise ValueError

    return obj(node)


class Parameter:

    def hasData(self):
        return True


class PrimitiveParameter(Parameter):
    def __init__(self, node):
        self.data = str(node.firstChild.data) if node.firstChild else ''

    def hasData(self):
        return bool(self.data)

    def __str__(self):
        return self.data


class ScalarParameter(PrimitiveParameter):
    def hasData(self):
        return float(self.data)


class BooleanParameter(PrimitiveParameter):
    def hasData(self):
        return self.data.lower() == 'true'


class EnumParameter(PrimitiveParameter):
    def __init__(self, node):
        self.value = parseNode(node.childNodes[0])
        super(EnumParameter, self).__init__(node.childNodes[1].childNodes[0])

    def hasData(self):
        return self.value.hasData()


class ContainerParameter(Parameter):
    def getindicesandvalues(self) -> Tuple[List[int], PrimitiveParameter]:
        raise NotImplementedError


class MatrixParameter(ContainerParameter):
    def __init__(self, node):
        self.values: List[Parameter] = []

        self.parse(node)
        self.ismatrix = False

    @staticmethod
    def validateElement(element):
        if element.tagName != 'Element':
            raise ValueError('Expected Element')
        if len(element.childNodes) != 1:
            raise ValueError('Expected Element to have 1 child')

    def parse(self, node):

        for element in node.childNodes:
            self.validateElement(element)
            value = element.childNodes[0]
            child = parseNode(value)

            if isinstance(child, ContainerParameter):
                if self.values and not self.ismatrix:
                    raise ValueError()  # TODO
                self.ismatrix = True

            self.values.append(parseNode(value))

    def hasData(self):
        return any(param.hasData() for param in self.values)

    def getindicesandvalues(self):

        for index, value in enumerate(self.values):

            if isinstance(value, ContainerParameter):

                for indices, v in value.getindicesandvalues():
                    yield [index] + indices, v
            else:
                yield [index], value


class StructParameter(ContainerParameter):

    def __init__(self, node):
        self.values: Dict[str, Parameter] = OrderedDict()

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
            value = parseNode(element.childNodes[0])

            name = str(parseNode(element.childNodes[1].childNodes[0]))

            self.values[name] = value

    def hasData(self):
        return any(param.hasData() for param in self.values.values())

    def getindicesandvalues(self):

        for key, value in self.values.items():

            if isinstance(value, ContainerParameter):
                for indices, v in value.getindicesandvalues():
                    yield [key] + indices, v
            else:
                yield [key], value


# def format2darray(array):
#     output = [list(row) for row in array]
#
#     columnswidth = [2 + max(map(len, column)) for column in zip(*output)]
#     for row in output:
#         for (columnindex, value), width in zip(enumerate(row), columnswidth):
#             row[columnindex] = value.ljust(width, ' ')
#
#     rows = [''.join(row) for row in output]
#
#     return '\n'.join(rows)


if __name__ == '__main__':
    cli()
