from gzip import GzipFile
from lxml.etree import parse, register_namespace, SubElement

DEFAULT_NAMESPACE_KEY = 'DEFAULT'


class XmlDocument(object):

    def __init__(self, filename, out, namespaces={}, rootElementPath=None):
        self.out = out
        self.out.put('Loading %s...' % filename)
        self.filename = filename
        self.namespaces = namespaces

        self.registerNamespaces(namespaces)

        try:
            self.tree = parse(self.filename)
        except Exception as e:
            # it's probably compressed
            zippedXmlFile = GzipFile(self.filename)
            self.tree = parse(zippedXmlFile)
        if rootElementPath:
            self.root = self.tree.find(rootElementPath, namespaces)
        else:
            self.root = self.tree.getroot()

        try:
            self.namespaces[DEFAULT_NAMESPACE_KEY] = self.root.nsmap[self.root.prefix]
        except:
            self.namespaces[DEFAULT_NAMESPACE_KEY] = self.root.nsmap[None]

    def registerNamespaces(self, namespaces):
        'so that newly created nodes can use the sytax <nskey:element>'
        for prefix in namespaces.keys():
            uri = namespaces[prefix]
            register_namespace(prefix, uri)

    def subElement(self, tag, parent=None, namespace=None, **kwargs):
        '''pass in a namespace of '' if you don't want the tag prefixed'''
        if parent is None:
            parent = self.root

        if namespace is None:
            namespace = self.namespaces[DEFAULT_NAMESPACE_KEY]
        else:
            namespace = self.namespaces.get(namespace, '')

        if namespace:
            node = SubElement(parent, '{%s}%s' % (namespace, tag), **kwargs)
        else:
            node = SubElement(parent, tag, **kwargs)

        return node

    def xpath(self, path, namespaceKey=None, root=None):
        if path.startswith('/'):
            path = '.' + path

        if root is None:
            root = self.tree

        if path.find(':') == -1 or namespaceKey is not None:
            if namespaceKey is None:
                namespaceKey = DEFAULT_NAMESPACE_KEY
            if namespaceKey != '':
                namespaceKey += ':'

            if path.startswith('.//'):
                path = ('.//', path[3:])
            elif path.startswith('./'):
                path = ('./', path[2:])
            else:
                path = ('', path)
            path = path[0] + namespaceKey + path[1]  # ex: ".//html:tr"

        self.out.debug('find(): searching for xpath query "%s"' % path)
        return root.xpath(path, namespaces=self.namespaces)

    def save(self):
        self.saveAs(self.filename)

    def saveAs(self, filename):  # filename may be file-like object
        self.out.put("Saving XML to %s..." % self.filename)
        self.tree.write(filename, encoding="utf-8", xml_declaration=True)
