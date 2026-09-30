# -*- coding: utf-8 -*-

"""Picture templates drawn with Flowchart Maker (draw.io).

Adapted from pibooth-picture-template 1.1.0 by Vincent Verdeil and Antoine
Rousseaux (https://github.com/pibooth/pibooth-picture-template), distributed
under the GNU General Public License v3.
"""

import zlib
import base64
from io import BytesIO
from urllib.parse import unquote
from xml.etree import ElementTree
from PIL import Image, ImageDraw, ImageFont

from pibooth import fonts
from pibooth.utils import LOGGER
from pibooth import pictures
from pibooth.pictures.factory import PilPictureFactory


def px(cin, dpi=600):
    """Convert a dimension in centiinch into pixels.

    :param cin: dimension in centiinch
    :type cin: str, float, int
    :param dpi: dot-per-inch
    :type dpi: int
    """
    return int(float(cin) * dpi / 100)


class TemplateParserError(Exception):
    pass


class TemplateParser(object):

    """Class to parse a picture template.

    A template is based on a XML file generated with Flowchart Maker (formerly draw.io)
    at https://app.diagrams.net.
    """

    def __init__(self, filename):
        self.filename = filename
        self.data = self.parse()

    def inflate(self, data, b64=False):
        """Decompress the data using zlib.

        In ~2016 Flowchart Maker started compressing 'using standard deflate'
        https://about.draw.io/extracting-the-xml-from-mxfiles
        """
        if b64:  # Optional, additionally base64 decode
            data = base64.b64decode(data)
        return unquote(zlib.decompress(data, -15).decode('utf8'))

    def parse(self):
        """Parse the XML template file.

        :return: data dictionary
        :rtype: dict
        """
        data = {}
        LOGGER.info('Parsing pictures template file: %s', self.filename)
        doc = ElementTree.parse(self.filename).getroot()

        for diagram in doc.iter('diagram'):

            if not list(diagram) and diagram.text.strip():  # Compressed
                template = ElementTree.fromstring(
                    self.inflate(diagram.text, True))
            else:
                template = diagram.find('mxGraphModel')

            template.set('name', diagram.get('name'))
            dpi = int(template[0][0].get('dpi', 600))
            size = (px(template.attrib['pageWidth'], dpi), px(
                template.attrib['pageHeight'], dpi))
            orientation = pictures.PORTRAIT if size[0] < size[1] else pictures.LANDSCAPE

            shapes = []
            distinct_capture_count = set()
            for cell in template.iter('mxCell'):
                shape = TemplateShapeParser(cell, dpi)

                if shape.type == TemplateShapeParser.TYPE_UNKNOWN:
                    continue

                if shape.type == TemplateShapeParser.TYPE_CAPTURE:
                    # Take only captures with a correct number
                    if shape.text in ("1", "2", "3", "4"):
                        shapes.append(shape)
                        distinct_capture_count.add(shape.text)
                    else:
                        LOGGER.warning("Template capture holder with text '%s' ignored", shape.text)

                elif shape.type == TemplateShapeParser.TYPE_TEXT:
                    # Take only text with a correct number
                    if shape.text in ("1", "2", "footer_text1", "footer_text2"):
                        shape.text = shape.text[-1]  # Keep ony index value
                        shapes.append(shape)
                    else:
                        LOGGER.warning("Template text holder with text '%s' ignored", shape.text)

                else:
                    shapes.append(shape)

                # If shape is on the left or the right of the page
                if shape.x + shape.width <= 0 or shape.x >= size[0]:
                    LOGGER.warning("Template shape '%s' X-position out of bounds, try to auto-adjust", shape.text)
                    shape.x = shape.x % size[0]

                # If shape is above or below the page
                if shape.y + shape.height <= 0 or shape.y >= size[1]:
                    LOGGER.warning("Template shape '%s' Y-position out of bounds, try to auto-adjust", shape.text)
                    shape.y = shape.y % size[1]

            # Create template parameters dictionary
            subdata = data.setdefault(orientation, {}).setdefault(
                len(distinct_capture_count), {})
            if subdata:
                raise TemplateParserError(
                    "Several templates with {} captures are defined".format(len(distinct_capture_count)))
            subdata['shapes'] = shapes
            subdata['size'] = size
            subdata['orientation'] = orientation

            # Calculate the orientation majority for this template
            captures = [shape for shape in shapes if shape.type ==
                        TemplateShapeParser.TYPE_CAPTURE]
            texts = [shape for shape in shapes if shape.type ==
                     TemplateShapeParser.TYPE_TEXT]
            portraits = [
                shape for shape in shapes if shape.width < shape.height]
            if len(portraits) * 1.0 / len(captures) >= 0.5:
                subdata['captures_orientation'] = pictures.PORTRAIT
            else:
                subdata['captures_orientation'] = pictures.LANDSCAPE

            LOGGER.info("Found template '%s': %s captures - %s texts - %s others", template.get('name'),
                        len(captures), len(texts), len(shapes) - (len(captures) + len(texts)))

        if not data:
            raise TemplateParserError(
                "No template found in '{}'".format(self.filename))
        return data

    def get(self, key, capture_number, orientation=pictures.PORTRAIT):
        """Return the value of the 'key' info for the given caputures numbers and orientation.

        :param key: key info to get
        :type key: str
        :param capture_number: number of captures to assemble
        :type capture_number: int
        :param orientation: 'portrait' or 'landscape'
        :type orientation: str
        """
        assert orientation in (pictures.PORTRAIT, pictures.LANDSCAPE)
        if orientation not in self.data:
            raise TemplateParserError(
                "No template for '{}' orientation".format(orientation))
        if capture_number not in self.data[orientation]:
            raise TemplateParserError(
                "No template for '{}' captures (orientation={})".format(capture_number, orientation))
        return self.data[orientation][capture_number][key]

    def get_best_orientation(self, captures):
        """Return the best orientation (PORTRAIT or LANDSCAPE), depending on the
        orientation of the given captures and available templates.

        It use the size of the first capture to determine the orientation (all captures
        of a same sequence should have the same orientation).

        :param captures: list of captures to concatenate
        :type captures: list
        :return: orientation PORTRAIT or LANDSCAPE
        :rtype: str
        """
        nbr = len(captures)
        if captures[0].size[0] < captures[0].size[1]:
            captures_orientation = pictures.PORTRAIT
        else:
            captures_orientation = pictures.LANDSCAPE

        for orientation in self.data:
            if nbr in self.data[orientation]:
                if self.data[orientation][nbr]['captures_orientation'] == captures_orientation:
                    return orientation

        for orientation in self.data:
            if nbr in self.data[orientation]:
                return orientation

        return pictures.PORTRAIT

    def get_size(self, capture_number, orientation=pictures.PORTRAIT):
        """Return total size of the final picture in pixels.

        :param capture_number: number of captures to assemble
        :type capture_number: int
        :param orientation: 'portrait' or 'landscape'
        :type orientation: str
        """
        return self.get('size', capture_number, orientation)

    def get_rects(self, capture_number, orientation=pictures.PORTRAIT):
        """Return the list of top-left coordinates and max size rectangle.

        :param capture_number: number of captures to assemble
        :type capture_number: int
        :param orientation: 'portrait' or 'landscape'
        :type orientation: str
        """
        return self.get('shapes', capture_number, orientation)

    def get_capture_rects(self, capture_number, orientation=pictures.PORTRAIT):
        """Return the list of top-left coordinates and max size rectangle.

        :param capture_number: number of captures to assemble
        :type capture_number: int
        :param orientation: 'portrait' or 'landscape'
        :type orientation: str
        """
        return [shape for shape in self.get_rects(capture_number, orientation) if shape.type == TemplateShapeParser.TYPE_CAPTURE]

    def get_text_rects(self, capture_number, orientation=pictures.PORTRAIT):
        """Return the list of top-left coordinates and max size rectangle.

        :param capture_number: number of captures to assemble
        :type capture_number: int
        :param orientation: 'portrait' or 'landscape'
        :type orientation: str
        """
        return [shape for shape in self.get_rects(capture_number, orientation) if shape.type == TemplateShapeParser.TYPE_TEXT]


class TemplateShapeParser(object):

    TYPE_CAPTURE = 'capture'
    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_UNKNOWN = 'unknown'

    def __init__(self, mxcell_node, dpi):
        self.text = self.parse_text(mxcell_node)
        self.style = self.parse_style(mxcell_node)
        self.image = self.style.get('image')
        self.rotation = -int(self.style.get('rotation', 0))
        self.x, self.y, self.width, self.height = self.parse_geometry(mxcell_node, dpi)

        # Define shape type
        if mxcell_node.get('vertex') == "1" and mxcell_node.get('style').startswith('shape=image'):
            self.type = self.TYPE_IMAGE
        elif mxcell_node.get('vertex') == "1" and mxcell_node.get('style').startswith('text;'):
            self.type = self.TYPE_TEXT
        elif mxcell_node.get('vertex') == "1" and not mxcell_node.get('style').startswith('text;'):
            self.type = self.TYPE_CAPTURE
        else:
            self.type = self.TYPE_UNKNOWN

    def __repr__(self):
        return f"Shape(text='{self.text}', type={self.type})"

    def parse_text(self, mxcell_node):
        """Extarct text.

        :param mxcell_node: 'mxCell' node
        :type mxcell_node: :py:class:`ElementTree.Element`
        """
        try:
            # XML format for font/style can be set in the value
            value = ElementTree.fromstring(str(mxcell_node.get('value'))).text
        except ElementTree.ParseError:
            value = mxcell_node.get('value') or ''
        return value

    def parse_style(self, mxcell_node):
        """Extract style data.

        :param mxcell_node: 'mxCell' node
        :type mxcell_node: :py:class:`ElementTree.Element`
        """
        styledict = {'name': ''}
        if 'style' in mxcell_node.attrib:
            style = [p for p in mxcell_node.attrib['style'].split(';') if p.strip()]
            if '=' not in style[0]:
                styledict['name'] = style.pop(0)
            for key_value in style:
                key, value = key_value.split('=', 1)
                styledict[key] = value
        return styledict

    def parse_geometry(self, mxcell_node, dpi=600):
        """Extract geometry data.

        :param mxcell_node: 'mxCell' node
        :type mxcell_node: :py:class:`ElementTree.Element`
        :param dpi: dot-per-inch
        :type dpi: int
        """
        geometry = mxcell_node.find('mxGeometry')
        if geometry is None:
            x, y, width, height = 0, 0, 0, 0
        else:
            x = px(geometry.get('x', 0), dpi)
            y = px(geometry.get('y', 0), dpi)
            width = px(geometry.attrib.get('width', 0), dpi)
            height = px(geometry.attrib.get('height', 0), dpi)
        return x, y, width, height


class TemplatePictureFactory(PilPictureFactory):

    def __init__(self, template, orientation, *images):
        self.template = template
        self.orientation = orientation
        size = self.template.get_size(len(images), self.orientation)
        super(TemplatePictureFactory, self).__init__(size[0], size[1], *images)

    def _iter_images_rects(self):
        raise NotImplementedError("Not applicable for template")

    def _iter_texts_rects(self, interline=None):
        raise NotImplementedError("Not applicable for template")

    def _image_paste(self, image, dest_image, pos_x, pos_y, angle=None):
        """Paste an image onto an other one with the given rotation angle.

        :param image: PIL image to draw on
        :type image: :py:class:`PIL.Image`
        :param dest_image: PIL image to draw on
        :type dest_image: :py:class:`PIL.Image`
        :param pos_x: X-axis position from left
        :type pos_x: int
        :param pos_y: Y-axis position from top
        :type pos_y: int
        :param angle: rotation angle in degree
        :type angle: int
        """
        width, height = image.size
        if angle:
            image = image.rotate(angle, expand=True)
        dest_image.paste(image,
                         (pos_x + (width - image.width)//2,
                          pos_y + (height - image.height)//2),
                         image if angle is not None else None)

    def _build_matrix(self, image):
        """Draw all shape in the order defined in the template.

        :param image: image to draw on
        :type image: :py:class:`PIL.Image`
        :return: drawn image
        :rtype: :py:class:`PIL.Image`
        """
        for shape in self.template.get_rects(len(self._images), self.orientation):
            if shape.type == TemplateShapeParser.TYPE_CAPTURE:
                index = int(shape.text) - 1
                if len(self._images) <= index:
                    continue  # No image available for this index

                src_image = self._images[index]
                src_image, width, height = self._image_resize_keep_ratio(src_image,
                                                                         shape.width,
                                                                         shape.height,
                                                                         self._crop)
                rect = Image.new('RGBA', (shape.width, shape.height), (255, 0, 0, 0))
                self._image_paste(src_image, rect, (shape.width - width) // 2, (shape.height - height) // 2)
                self._image_paste(rect, image, shape.x, shape.y, shape.rotation)

            elif shape.type == TemplateShapeParser.TYPE_TEXT:
                index = int(shape.text) - 1
                if len(self._texts) <= index:
                    continue  # No text available for this index

                text, font_name, color, align = self._texts[index]
                rect = Image.new('RGBA', (shape.width, shape.height), (255, 0, 0, 0))
                draw = ImageDraw.Draw(rect)
                font = fonts.get_pil_font(text, font_name, shape.width, shape.height)
                # getbbox exists from Pillow 8 and replaces getsize, removed in Pillow 10
                left, top, right, bottom = font.getbbox(text)
                text_width, text_height = right - left, bottom - top

                x = 0
                if align == self.CENTER:
                    x += (shape.width - text_width) // 2
                elif align == self.RIGHT:
                    x += (shape.width - text_width)

                draw.text((x - left, (shape.height - text_height) // 2 - top), text, color, font=font)
                self._image_paste(rect, image, shape.x, shape.y, shape.rotation)

            elif shape.type == TemplateShapeParser.TYPE_IMAGE:
                data = base64.b64decode(shape.image.split(',', 1)[1])
                src_image = Image.open(BytesIO(data))
                src_image = src_image.resize((shape.width, shape.height))
                rect = Image.new('RGBA', (shape.width, shape.height), (255, 0, 0, 0))
                self._image_paste(src_image, rect, 0, 0)
                self._image_paste(rect, image, shape.x, shape.y, shape.rotation)

        return image

    def _build_texts(self, image):
        pass  # Texts are drawn with capture matrix to preserve order defined in template

    def _build_outlines(self, image):
        """Draw outlines for captures and texts which is useful to investigate
        position issues.

        :param image: PIL image to draw on
        :type image: :py:class:`PIL.Image`
        """
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        for shape in self.template.get_rects(len(self._images), self.orientation):
            rect = Image.new('RGBA', (shape.width, shape.height), (255, 0, 0, 0))
            draw = ImageDraw.Draw(rect)
            draw.rectangle(((0, 0), (shape.width - 1, shape.height - 1)), outline='red')
            draw.text((10, 10), shape.text, 'red', font)
            self._image_paste(rect, image, shape.x, shape.y, shape.rotation)
