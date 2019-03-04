import click
import itertools as it

import xml.dom.minidom as xml
from typing import List, Tuple, Dict, Generator, Iterator, Any
from collections import OrderedDict


class ParseError(Exception):
    pass


@click.command()
@click.argument('xmlfile', type=click.File(mode='r'))
@click.argument('paramfile', type=click.File(mode='r'), required=False)
@click.option('--param', '-p', multiple=True, help='ParameterCode of parameter to display')
@click.option('--nonzero', '-z', is_flag=True, help='Display all parameter values, including 0')
def cli(xmlfile, paramfile, **kwargs):  # param, nonzero, all_):
    """
        Parameter analyzer for CICU


    """

    filterparams = paramfile or kwargs['param']

    # Get all parameterCodes of interest
    paramnames = loadparams(paramfile)
    paramnames.extend(kwargs['param'])

    try:
        dom = loadxml(xmlfile)
    except ParseError as ex:
        print(f'Could not parse xml file. {ex}')
        return

    xmlparamnodes = {}
    for param in dom.getElementsByTagName('Parameter'):
        name = param.attributes['parameterCode'].value
        xmlparamnodes[name] = param

    if filterparams:
        # Assert all supplied parameterCodes exists
        for name in paramnames:
            if name not in xmlparamnodes:
                print(f'Parameter {name} not found')
                return

    parameters = {}
    for code, xmlnode in xmlparamnodes.items():
        try:
            param = parseparameter(xmlnode)

        except ParseError as ex:
            print(f'Error parsing parameter {code}: {ex}')
            return

        parameters[code] = param

    if filterparams:
        for code in paramnames:
            param = parameters[code]
            showparameter(param, code, **kwargs)
    else:
        for code, param in parameters:
            showparameter(param, code, **kwargs)


def parseparameter(xmlnode):
    return parseNode(xmlnode.firstChild.firstChild)


def showparameter(parameter, name, **kwargs):
    if parameter.hasData() or kwargs['nonzero']:
        if isinstance(parameter, ContainerParameter):
            for indices, value in parameter.getindicesandvalues():

                if value.hasData() or kwargs['nonzero']:
                    print(f'{name}: [{",".join(map(str, indices))}] = {value.data}')
        else:
            print(f'{name}: {parameter}')


def loadparams(paramfile) -> List[str]:
    result = []
    for line in paramfile:
        line = line.strip()
        if line:
            result.append(line)
    return result


def loadxml(file):
    try:
        dom = xml.parse(file)

    except Exception as ex:
        raise ParseError(str(ex))

    def remove_empty_nodes(node):
        for child in node.childNodes:
            if child.nodeType == xml.Node.TEXT_NODE:
                if child.nodeValue:
                    child.nodeValue = child.nodeValue.strip()
            elif child.nodeType == xml.Node.ELEMENT_NODE:
                remove_empty_nodes(child)

    remove_empty_nodes(dom)
    dom.normalize()
    return dom


def parseNode(node) -> 'Parameter':
    mapping = {'Scalar': ScalarParameter,
               'Boolean': BooleanParameter,
               'String': PrimitiveParameter,
               'Array': MatrixParameter,
               'Struct': StructParameter,
               'Identifier': PrimitiveParameter,
               'Enum': EnumParameter,
               'Value': PrimitiveParameter,
               }

    nodename = node.tagName
    if not nodename or nodename not in mapping:
        raise ParseError(f'Cannot parse a node with name: {nodename}')

    return mapping[nodename](node)


class Parameter:

    def hasData(self) -> bool:
        return True


class PrimitiveParameter(Parameter):
    def __init__(self, node):
        self.data = str(node.firstChild.data) if node.firstChild else ''

    def hasData(self):
        return self.data

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
    def getindicesandvalues(self) -> Generator[Tuple[Iterator[Any], PrimitiveParameter], None, None]:
        raise NotImplementedError


class MatrixParameter(ContainerParameter):
    def __init__(self, node):
        self.values: List[Parameter] = []

        self.parse(node)
        self.ismatrix = False

    @staticmethod
    def validateElement(element):
        if element.tagName != 'Element':
            raise ParseError('Childnodes of array expected to be of type Element')
        if len(element.childNodes) != 1:
            raise ParseError('Expected Element to have 1 child only')

    def parse(self, node):

        for element in node.childNodes:
            self.validateElement(element)
            value = element.childNodes[0]
            child = parseNode(value)

            if isinstance(child, ContainerParameter):
                if self.values and not self.ismatrix:
                    raise ParseError(f'Trying to create a non-rectangular array')

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
            raise ParseError('Childnodes of struct expected to be of type Element')
        if len(element.childNodes) != 2:
            raise ParseError('Expected Element to have 2 children')

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


def format2darray(array: Iterator[Iterator[Any]]):
    output = [list(row) for row in array]

    columnwidths = [2 + max(map(len, column)) for column in zip(*output)]
    for row in output:
        for (columnindex, value), width in zip(enumerate(row), columnwidths):
            row[columnindex] = value.ljust(width, ' ')

    rows = [''.join(row) for row in output]

    return '\n'.join(rows)


if __name__ == '__main__':
    cli()
