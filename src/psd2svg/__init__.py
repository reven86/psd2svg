# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from logging import getLogger
import os
from tkinter import SE
import svgwrite
from psd_tools import PSDImage
from psd2svg.converter.adjustments import AdjustmentsConverter
from psd2svg.converter.core import LayerConverter
from psd2svg.converter.effects import EffectsConverter
from psd2svg.converter.io import PSDReader, SVGWriter
from psd2svg.converter.shape import ShapeConverter
from psd2svg.converter.text import TextConverter
from psd2svg.version import __version__


logger = getLogger(__name__)


def psd2svg(input, output=None, **kwargs):
    converter = PSD2SVG(**kwargs)

    if os.path.isdir(input):
        try:
            if output:            
                os.makedirs(output)            
        except:
            pass                    
        for filename in os.listdir(input):
            if filename[-4:] == '.psd':
                converter.convert(os.path.join(input, filename), os.path.join(output or '', filename[:-4] + '.svg'))
        return
    
    return converter.convert(input, output)


class PSD2SVG(AdjustmentsConverter, EffectsConverter, LayerConverter,
              PSDReader, ShapeConverter, SVGWriter, TextConverter):
    """PSD to SVG converter

    input_url - url, file-like object, PSDImage, or any of its layer.
    output_url - url or file-like object to export svg. if None, return data.
    export_resource - use dataURI to embed bitmap (default True)
    """
    def __init__(self, resource_path=None, shapes_only=False, compact=False, padding=None, remove_color=False):
        self.resource_path = resource_path
        self.shapes_only = shapes_only
        self.compact = compact
        self.padding = padding
        self.remove_color = remove_color

    def reset(self):
        """Reset the converter."""
        self._psd = None
        self._white_filter = None
        self._identity_filter = None
        svgwrite.utils.AutoID._set_value(0)

    def convert(self, layer, output=None):
        """Convert the given PSD to SVG."""
        self.reset()
        self._set_input(layer)
        self._set_output(output)

        layer = self._layer
        bbox = layer.viewbox if hasattr(layer, 'viewbox') else layer.bbox
        if bbox == (0, 0, 0, 0):
            bbox = self._psd.viewbox

        if self.padding:
            viewbox = bbox
            bbox = (bbox[0] - self.padding[0], bbox[1] - self.padding[1], bbox[2] + self.padding[2], bbox[3] + self.padding[3])

        self._dwg = svgwrite.Drawing(
            size=(bbox[2] - bbox[0], bbox[3] - bbox[1]),
            viewBox='%d %d %d %d' % (
                bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]
            ),
        )

        container = self._dwg.g() if self.padding else self._dwg

        if layer.is_group():
            self.create_group(layer, container)
        else:
            container.add(self.convert_layer(layer))
            
        if self.padding:
            self._dwg.add(container)
            
            # clip element using original viewbox
            clip_path = self._dwg.defs.add(self._dwg.clipPath())
            clip_path.add(self._dwg.rect(
                insert=(viewbox[0], viewbox[1]),
                size=(viewbox[2] - viewbox[0],
                        viewbox[3] - viewbox[1]),
                ))

            container['clip-path'] = clip_path.get_funciri()
                    
        # Layerless PSDImage.
        if (
            isinstance(layer, PSDImage) and len(layer) == 0 and
            layer.has_preview()
        ):
            self._dwg.add(self._dwg.image(
                self._get_image_href(layer.topil()),
                insert=(0, 0),
                size=(layer.width, layer.height),
                debug=False
            ))
        return self._save_svg()

    @property
    def width(self):
        return self._psd.width if hasattr(self, '_psd') else None

    @property
    def height(self):
        return self._psd.height if hasattr(self, '_psd') else None
