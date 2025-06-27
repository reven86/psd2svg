# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from logging import getLogger
from psd_tools.constants import TaggedBlockID
from psd2svg.converter.constants import BLEND_MODE


logger = getLogger(__name__)


class ShapeConverter(object):

    def _group_elements(self, elements, mask, clip_path):
        if not elements:
            assert not mask and not clip_path, "Mask and clip_path specified for no path elements"
            return None

        if len(elements) == 1:
            container = elements[0]
        else:
            container = self._dwg.g()
            for el in elements:
                container.add(el)

        if mask:
            container['mask'] = mask.get_funciri()

        if clip_path:
            clip_path_element = self._dwg.defs.add(self._dwg.clipPath())
            clip_path_element.add(clip_path)
            clip_path_element['clip-rule'] = 'evenodd'
            container['clip-path'] = clip_path_element.get_funciri()

        container['fill-rule'] = 'evenodd'
        return container

    def convert_shape(self, layer, initial_elements=None):
        """Convert each path in vector_mask as individual path element. Groups the together."""

        elements = []
        if initial_elements:
            elements.extend(initial_elements)

        # preprocess paths, link path with operation == -1 to the previous one
        path_set = []
        for path in layer.vector_mask.paths:
            if len(path) == 0:
                continue
            
            if path.operation == -1:
                assert path_set
                path_set[-1].append(path)
            else:
                path_set.append([path])
            
        mask = None
        clip_path = None
        for path_list in path_set:            
            operation = path_list[0].operation
            element = self._dwg.path(d=self._generate_path(path_list))
            
            if operation == 1 or operation == 0:   # standard "or" operation
                if layer.vector_mask.initial_fill_rule != 0:
                    logger.warn(f'initial_fill_rule != 0 not implemented yet, layer {layer}')
                if mask or clip_path:
                    # combine mask with previous elements before drawing new path
                    elements = [self._group_elements(elements, mask, clip_path)]
                    mask = None
                    clip_path = None
                
                elements.append(element)
            elif operation == 2:   # subtraction, applies only to previous paths
                if not mask:
                    mask = self._dwg.defs.add(self._dwg.mask())
                    mask.add(self._dwg.rect(
                        insert=(self._psd.bbox[0], self._psd.bbox[1]),
                        size=(self._psd.bbox[2] - self._psd.bbox[0],
                              self._psd.bbox[3] - self._psd.bbox[1]),
                        fill='white'))

                element['fill'] = 'black'
                mask.add(element)
            elif operation == 3:   # intersection
                if not elements:
                    # this means there is only one preceding element with "and" operation, combine then two
                    elements.append(element)
                else:
                    # 'and' operations should apply one after other, can't combine several paths into clip_path attribute
                    # because it will apply intersection in a wrong way

                    if clip_path:
                        # apply intersection for preceding "and" path
                        elements = [self._group_elements(elements, mask, clip_path)]
                        mask = None
                    clip_path = element
            else:
                logger.error(f'Unsupported path operation {operation} layer {layer}')

        return self._group_elements(elements, mask, clip_path)


    def _generate_path(self, path_list, command='C'):
        """Sequence generator for SVG path constructor."""

        for path in path_list:
            assert len(path)

            # Initial point.
            yield 'M'
            yield path[0].anchor[1] * self.width
            yield path[0].anchor[0] * self.height
            yield command

            # Closed path or open path
            points = (zip(path, path[1:] + path[0:1]) if path.is_closed()
                        else zip(path, path[1:]))

            # Rest of the points.
            for p1, p2 in points:
                yield p1.leaving[1] * self.width
                yield p1.leaving[0] * self.height
                yield p2.preceding[1] * self.width
                yield p2.preceding[0] * self.height
                yield p2.anchor[1] * self.width
                yield p2.anchor[0] * self.height

            if path.is_closed():
                yield 'Z'


    def add_stroke_style(self, layer, element):
        """Add stroke style to the path element."""
        if not layer.has_stroke():
            return element

        stroke = layer.stroke
        if not stroke.enabled:
            return element

        if stroke.line_alignment == 'inner':
            clippath = self._dwg.defs.add(self._dwg.clipPath())
            clippath['class'] = 'psd-stroke stroke-inner'
            clippath.add(self.convert_shape(layer.vector_mask))     # not tested, could be vector_mask is already has subtract path operations
            element['stroke-width'] = stroke.line_width.value * 2
            element['clip-path'] = clippath.get_funciri()
        # elif stroke.line_alignment == 'outer':
        #     mask = self._dwg.defs.add(self._dwg.mask())
        #     mask['class'] = 'psd-stroke stroke-outside'
        #     mask.add(self._dwg.rect(
        #         insert=(layer.left, layer.top),
        #         size=(layer.width, layer.height),
        #         fill='white'))
        #     mask.add(self.convert_shape(layer.vector_mask), fill='black'))
        #     element['stroke-width'] = stroke.line_width * 2
        #     element['mask'] = mask.get_funciri()
        else:
            element['stroke-width'] = stroke.line_width.value
        # element['stroke-alignment'] = stroke.line_alignment

        if stroke.content.name == 'patternoverlay':
            pattern = self.create_pattern(
                stroke.content, insert=(layer.left, layer.top))
            element['stroke'] = pattern.get_funciri()
        elif stroke.content.name == 'gradientoverlay':
            gradient = self.create_gradient(
                stroke.content, size=(layer.width, layer.height))
            element['stroke'] = gradient.get_funciri()
        elif stroke.content.classID == b'solidColorLayer':
            element['stroke'] = self.create_solid_color(
                stroke.content['Clr ']
            )

        if not stroke.fill_enabled:
            element['fill-opacity'] = 0

        element['stroke-opacity'] = stroke.opacity.value / 100.0
        element['stroke-linecap'] =  stroke.line_cap_type
        element['stroke-linejoin'] = stroke.line_join_type
        if stroke.line_dash_set:
            element['stroke-dasharray'] = ",".join(
                [str(x.value * stroke.line_width.value)
                 for x in stroke.line_dash_set])
            element['stroke-dashoffset'] = stroke.line_dash_offset.value
        self.add_blend_mode(element, stroke.blend_mode)

        return element


    def add_stroke_content_style(self, layer, element):
        """Add stroke content (fill) style to the path element."""
        if not layer.has_stroke_content():
            return element

        effect = layer.stroke_content
        if not effect.enabled:
            return element

        if effect.name == 'patternoverlay':
            pattern = self.create_pattern(
                effect, insert=(layer.left, layer.top))
            element['fill'] = pattern.get_funciri()
        elif effect.name == 'gradientoverlay':
            gradient = self.create_gradient(
                effect, size=(layer.width, layer.height))
            element['fill'] = gradient.get_funciri()
        if effect.name == 'coloroverlay':
            element['fill'] = self.create_solid_color(effect)

        return element
